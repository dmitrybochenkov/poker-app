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
from app.bot.vk.handlers.admin import routing as vk_admin_routing
from app.api.http import vk_webhook as vk_webhook_module


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("local_state", "local_context"),
    [
        (vk_state.WAITING_FOR_BET_PAYMENT_RECEIPT, {}),
        (None, {"betstat_mode": "personal", "betstat_selected_ids": "7"}),
    ],
)
async def test_routing_preserves_ephemeral_vk_state_without_durable_row(
    state_sessions, monkeypatch, local_state, local_context
):
    monkeypatch.setattr(vk_state, "SessionFactory", state_sessions)
    user_id = 101
    vk_state.vk_user_states.pop(user_id, None)
    if local_state is not None:
        vk_state.vk_user_states[user_id] = local_state
    vk_state.vk_user_contexts[user_id] = dict(local_context)

    async def consumer(**kwargs):
        assert vk_state.vk_user_states.get(user_id) == local_state
        assert vk_state.vk_user_contexts.get(user_id) == local_context
        return PlainTextResponse("consumed")

    monkeypatch.setattr(
        vk_admin_routing.registrations,
        "handle_admin_corrected_name_text",
        consumer,
    )

    response = await vk_admin_routing.handle_admin_text_commands(
        user_id=user_id, text="next"
    )

    assert response is not None and response.body == b"consumed"
    async with state_sessions() as session:
        assert await VkConversationStateRepository(session).get(vk_user_id=user_id) is None


@pytest.mark.asyncio
async def test_vk_start_clears_local_and_durable_state_without_resurrection(
    state_sessions, monkeypatch
):
    monkeypatch.setattr(vk_state, "SessionFactory", state_sessions)
    monkeypatch.setattr(vk_webhook_module, "SessionFactory", state_sessions)
    monkeypatch.setattr(vk_webhook_module, "send_vk_message", AsyncMock())
    monkeypatch.setattr(vk_webhook_module.settings, "vk_secret_key", "")
    user_id = 101
    await vk_state.replace_durable_vk_state(
        user_id,
        state_type=vk_state.WAITING_FOR_NEW_NAME,
        payload={"registration_name": "Stale"},
    )
    vk_state.vk_user_states[user_id] = vk_state.WAITING_FOR_NEW_NAME
    vk_state.vk_user_contexts[user_id] = {"registration_name": "Stale"}

    response = await vk_webhook_module.vk_webhook(
        {
            "type": "message_new",
            "object": {"message": {"from_id": user_id, "text": "/start"}},
        }
    )

    assert response.body == b"ok"
    assert user_id not in vk_state.vk_user_states
    assert user_id not in vk_state.vk_user_contexts
    async with state_sessions() as session:
        assert await VkConversationStateRepository(session).get(vk_user_id=user_id) is None

    await vk_state.hydrate_legacy_vk_state(user_id)
    assert user_id not in vk_state.vk_user_states
    assert user_id not in vk_state.vk_user_contexts


@pytest.mark.asyncio
async def test_vk_start_without_durable_state_is_idempotent(state_sessions, monkeypatch):
    monkeypatch.setattr(vk_state, "SessionFactory", state_sessions)
    monkeypatch.setattr(vk_webhook_module, "SessionFactory", state_sessions)
    monkeypatch.setattr(vk_webhook_module, "send_vk_message", AsyncMock())
    monkeypatch.setattr(vk_webhook_module.settings, "vk_secret_key", "")

    for _ in range(2):
        response = await vk_webhook_module.vk_webhook(
            {
                "type": "message_new",
                "object": {"message": {"from_id": 202, "text": "/start"}},
            }
        )
        assert response.body == b"ok"
