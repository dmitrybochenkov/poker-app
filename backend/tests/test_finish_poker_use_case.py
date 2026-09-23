import asyncio

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.use_cases.poker.finish_poker import (
    ActivePokerNotFoundError,
    FinishPokerNotAuthorizedError,
    FinishPokerUseCase,
)
from app.db.base import Base
from app.db.models.poker import Poker
from app.db.models.poker_data import PokerData
from app.db.models.poker_param import PokerParam
from app.db.models.poker_room_denied import PokerRoomDenied
from app.db.models.user import User
from app.services.finish_poker_flow import FinishPokerFlow


async def _session_factory(url: str = "sqlite+aiosqlite:///:memory:"):
    engine = create_async_engine(url)
    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all,
            tables=[
                User.__table__,
                PokerParam.__table__,
                Poker.__table__,
                PokerData.__table__,
                PokerRoomDenied.__table__,
            ],
        )
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed(session_factory, *, actor_approved=True, actor_admin=True):
    async with session_factory() as session:
        actor = User(
            name="Admin",
            telegram_id=1,
            notification_platform="tg",
            is_approved=actor_approved,
            is_admin=actor_admin,
        )
        player = User(
            name="Player",
            vk_id=2,
            notification_platform="vk",
            is_approved=True,
        )
        params = PokerParam(
            buyin_size_chips=200,
            buyin_size_kopecks=20_000,
            bb_size_chips=10,
            max_buyins=3,
        )
        session.add_all([actor, player, params])
        await session.flush()
        poker = Poker(params_id=int(params.row_id), is_going=True, is_bettable=True)
        session.add(poker)
        await session.flush()
        session.add_all(
            [
                PokerData(
                    date=poker.date,
                    player_id=int(actor.row_id),
                    player_name=actor.name,
                ),
                PokerData(
                    date=poker.date,
                    player_id=int(player.row_id),
                    player_name=player.name,
                ),
                PokerRoomDenied(user_row_id=int(player.row_id)),
            ]
        )
        await session.commit()
        return int(actor.row_id), int(player.row_id), int(poker.row_id)


@pytest.mark.asyncio
async def test_finish_poker_commits_flags_and_deny_cleanup_atomically() -> None:
    engine, session_factory = await _session_factory()
    actor_id, player_id, poker_id = await _seed(session_factory)

    async with session_factory() as session:
        result = await FinishPokerUseCase(session).execute(actor_user_id=actor_id)

    assert result.poker_id == poker_id
    assert result.recipient_user_ids == (actor_id, player_id)
    async with session_factory() as session:
        poker = await session.get(Poker, poker_id)
        assert poker is not None
        assert poker.is_going is False
        assert poker.is_bettable is False
        assert poker.is_ready_for_chips_entering is True
        assert await session.scalar(select(func.count()).select_from(PokerRoomDenied)) == 0
        assert await session.scalar(select(func.count()).select_from(PokerData)) == 2
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("seed_options", "actor_override"),
    [
        ({"actor_admin": False}, None),
        ({"actor_approved": False}, None),
        ({}, 999_999),
    ],
)
async def test_finish_poker_rejects_unauthorized_actor_without_mutation(
    seed_options,
    actor_override,
) -> None:
    engine, session_factory = await _session_factory()
    actor_id, _, poker_id = await _seed(session_factory, **seed_options)

    async with session_factory() as session:
        with pytest.raises(FinishPokerNotAuthorizedError):
            await FinishPokerUseCase(session).execute(
                actor_user_id=actor_override or actor_id
            )

    async with session_factory() as session:
        poker = await session.get(Poker, poker_id)
        assert poker is not None and poker.is_going is True
        assert await session.scalar(select(func.count()).select_from(PokerRoomDenied)) == 1
    await engine.dispose()


@pytest.mark.asyncio
async def test_finish_poker_repeated_execution_does_not_mutate_again() -> None:
    engine, session_factory = await _session_factory()
    actor_id, _, poker_id = await _seed(session_factory)

    async with session_factory() as session:
        await FinishPokerUseCase(session).execute(actor_user_id=actor_id)
    async with session_factory() as session:
        with pytest.raises(ActivePokerNotFoundError):
            await FinishPokerUseCase(session).execute(actor_user_id=actor_id)

    async with session_factory() as session:
        poker = await session.get(Poker, poker_id)
        assert poker is not None and poker.is_ready_for_chips_entering is True
    await engine.dispose()


@pytest.mark.asyncio
async def test_finish_poker_rolls_back_flags_when_deny_cleanup_fails() -> None:
    engine, session_factory = await _session_factory()
    actor_id, _, poker_id = await _seed(session_factory)

    async with session_factory() as session:
        use_case = FinishPokerUseCase(session)

        async def fail_cleanup():
            raise RuntimeError("cleanup failed")

        use_case.poker_room_denied_repository.clear_all_without_commit = fail_cleanup
        with pytest.raises(RuntimeError, match="cleanup failed"):
            await use_case.execute(actor_user_id=actor_id)

    async with session_factory() as session:
        poker = await session.get(Poker, poker_id)
        assert poker is not None
        assert poker.is_going is True
        assert poker.is_bettable is True
        assert poker.is_ready_for_chips_entering is False
        assert await session.scalar(select(func.count()).select_from(PokerRoomDenied)) == 1
    await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_finish_poker_has_one_success(tmp_path) -> None:
    engine, session_factory = await _session_factory(
        f"sqlite+aiosqlite:///{tmp_path / 'finish-poker.db'}"
    )
    actor_id, _, poker_id = await _seed(session_factory)

    async def execute():
        async with session_factory() as session:
            return await FinishPokerUseCase(session).execute(actor_user_id=actor_id)

    results = await asyncio.gather(execute(), execute(), return_exceptions=True)

    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(isinstance(result, ActivePokerNotFoundError) for result in results) == 1
    async with session_factory() as session:
        poker = await session.get(Poker, poker_id)
        assert poker is not None and poker.is_ready_for_chips_entering is True
        assert await session.scalar(select(func.count()).select_from(PokerRoomDenied)) == 0
    await engine.dispose()


@pytest.mark.asyncio
async def test_notification_failure_does_not_rollback_finished_poker() -> None:
    engine, session_factory = await _session_factory()
    actor_id, _, poker_id = await _seed(session_factory)

    class FailingNotifier:
        async def notify(self, *, recipient_user_ids):
            raise RuntimeError("network unavailable")

    result = await FinishPokerFlow(
        session_factory=session_factory,
        notifier=FailingNotifier(),
    ).execute(actor_user_id=actor_id)

    assert result.poker_id == poker_id
    async with session_factory() as session:
        poker = await session.get(Poker, poker_id)
        assert poker is not None and poker.is_ready_for_chips_entering is True
    await engine.dispose()
