from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models.user import User
from app.db.models.vk_conversation_state import VkConversationState
from app.db.repositories.vk_conversation_state_repository import (
    VkConversationStateRepository,
)
from app.bot.vk import state as vk_state
from app.bot.vk.handlers.admin import buyins as vk_buyins


@pytest.fixture
async def state_sessions():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all,
            tables=[User.__table__, VkConversationState.__table__],
        )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    yield sessions
    await engine.dispose()


@pytest.mark.asyncio
async def test_state_survives_repository_and_session_recreation(state_sessions):
    async with state_sessions() as session, session.begin():
        await VkConversationStateRepository(session).replace_without_commit(
            vk_user_id=101,
            user_row_id=None,
            state_type="waiting_for_new_name",
            payload={"linked_user_row_id": 7},
        )

    async with state_sessions() as restarted_session:
        restored = await VkConversationStateRepository(restarted_session).get(
            vk_user_id=101
        )

    assert restored is not None
    assert restored.state_type == "waiting_for_new_name"
    assert restored.payload == {"linked_user_row_id": 7}


@pytest.mark.asyncio
async def test_state_replacement_and_clear_are_durable(state_sessions):
    async with state_sessions() as session, session.begin():
        repository = VkConversationStateRepository(session)
        await repository.replace_without_commit(
            vk_user_id=101,
            user_row_id=None,
            state_type="first",
            payload={"value": 1},
        )
        await repository.replace_without_commit(
            vk_user_id=101,
            user_row_id=None,
            state_type="second",
            payload={"value": 2},
        )
    async with state_sessions() as session, session.begin():
        assert await VkConversationStateRepository(session).clear_without_commit(
            vk_user_id=101
        )
    async with state_sessions() as session:
        assert await VkConversationStateRepository(session).get(vk_user_id=101) is None


@pytest.mark.asyncio
async def test_two_vk_users_have_isolated_parallel_states(state_sessions):
    async with state_sessions() as session, session.begin():
        repository = VkConversationStateRepository(session)
        await repository.replace_without_commit(
            vk_user_id=101, user_row_id=None, state_type="cashout", payload={"target": 1}
        )
        await repository.replace_without_commit(
            vk_user_id=202, user_row_id=None, state_type="cashout", payload={"target": 2}
        )
    async with state_sessions() as session:
        repository = VkConversationStateRepository(session)
        first = await repository.get(vk_user_id=101)
        second = await repository.get(vk_user_id=202)
    assert first is not None and first.payload["target"] == 1
    assert second is not None and second.payload["target"] == 2


@pytest.mark.asyncio
async def test_buyin_correction_resumes_after_process_local_state_loss(
    state_sessions, monkeypatch
):
    monkeypatch.setattr(vk_state, "SessionFactory", state_sessions)
    await vk_state.replace_durable_vk_state(
        101,
        state_type=vk_state.WAITING_FOR_ADMIN_BUYIN_CORRECT_AMOUNT,
        payload={
            "buyin_correct_player_id": 77,
            "buyin_correct_old_buyins": 4,
            "buyin_correct_player_name": "Target",
        },
    )
    vk_state.vk_user_states.clear()
    vk_state.vk_user_contexts.clear()
    send = AsyncMock()
    keyboard = object()
    monkeypatch.setattr(vk_buyins, "send_vk_message", send)
    monkeypatch.setattr(
        vk_buyins, "poker_buyin_correct_confirm_keyboard", Mock(return_value=keyboard)
    )

    response = await vk_buyins.handle_admin_buyin_correct_amount_text(
        user_id=101, text="6"
    )

    assert isinstance(response, PlainTextResponse)
    send.assert_awaited_once()
    assert send.await_args.kwargs["keyboard"] is keyboard
    assert send.await_args.kwargs["message"].endswith("6")


@pytest.mark.asyncio
async def test_legacy_registration_state_is_hydrated_and_persisted_between_workers(
    state_sessions, monkeypatch
):
    monkeypatch.setattr(vk_state, "SessionFactory", state_sessions)

    @vk_state.durable_vk_workflow
    async def first_worker(*, user_id: int):
        vk_state.vk_user_states[user_id] = vk_state.WAITING_FOR_NEW_NAME
        vk_state.vk_user_contexts[user_id] = {"linked_user_row_id": 77}

    await first_worker(user_id=101)
    vk_state.vk_user_states.clear()
    vk_state.vk_user_contexts.clear()

    @vk_state.durable_vk_workflow
    async def second_worker(*, user_id: int):
        assert vk_state.vk_user_states[user_id] == vk_state.WAITING_FOR_NEW_NAME
        assert vk_state.vk_user_contexts[user_id]["linked_user_row_id"] == 77
        vk_state.vk_user_states.pop(user_id)
        vk_state.vk_user_contexts.pop(user_id)

    await second_worker(user_id=101)
    async with state_sessions() as session:
        assert await VkConversationStateRepository(session).get(vk_user_id=101) is None
