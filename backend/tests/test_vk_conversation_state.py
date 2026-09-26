import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models.user import User
from app.db.models.vk_conversation_state import VkConversationState
from app.db.repositories.vk_conversation_state_repository import (
    VkConversationStateRepository,
)


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
