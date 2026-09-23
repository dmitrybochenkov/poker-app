import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.use_cases.poker.start_betting import (
    ActivePokerNotFoundError,
    BettingAlreadyOpenError,
    PokerAwaitingChipsError,
    StartBettingNotAuthorizedError,
    StartBettingUseCase,
)
from app.db.base import Base
from app.db.models.poker import Poker
from app.db.models.poker_param import PokerParam
from app.db.models.user import User
from app.services.start_betting_flow import StartBettingFlow


async def _session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all,
            tables=[User.__table__, PokerParam.__table__, Poker.__table__],
        )
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed(
    session_factory,
    *,
    actor_approved: bool = True,
    actor_admin: bool = True,
    active_poker: bool = True,
    chip_input: bool = False,
    betting_open: bool = False,
) -> tuple[int, int | None, tuple[int, int]]:
    async with session_factory() as session:
        actor = User(
            name="Admin",
            telegram_id=1,
            notification_platform="tg",
            is_approved=actor_approved,
            is_admin=actor_admin,
        )
        tg_recipient = User(
            name="TG",
            telegram_id=2,
            notification_platform="tg",
            is_approved=True,
        )
        vk_recipient = User(
            name="VK",
            vk_id=3,
            notification_platform="vk",
            is_approved=True,
        )
        session.add_all(
            [
                actor,
                tg_recipient,
                vk_recipient,
                User(
                    name="Pending",
                    telegram_id=4,
                    notification_platform="tg",
                    is_approved=False,
                ),
                User(name="Legacy", vk_id=5, notification_platform=None, is_approved=True),
            ]
        )
        params = PokerParam(
            buyin_size_chips=200,
            buyin_size_kopecks=20_000,
            bb_size_chips=10,
            max_buyins=3,
        )
        session.add(params)
        await session.flush()
        poker = None
        if active_poker:
            poker = Poker(
                params_id=params.row_id,
                is_going=True,
                is_ready_for_chips_entering=chip_input,
                is_bettable=betting_open,
            )
            session.add(poker)
        await session.commit()
        return (
            int(actor.row_id),
            int(poker.row_id) if poker is not None else None,
            (int(actor.row_id), int(tg_recipient.row_id), int(vk_recipient.row_id)),
        )


@pytest.mark.asyncio
async def test_start_betting_commits_state_and_returns_canonical_recipients() -> None:
    engine, session_factory = await _session_factory()
    actor_id, poker_id, expected_recipients = await _seed(session_factory)

    async with session_factory() as session:
        result = await StartBettingUseCase(session).execute(actor_user_id=actor_id)

    assert result.poker_id == poker_id
    assert result.recipient_user_ids == expected_recipients
    async with session_factory() as verification_session:
        poker = await verification_session.scalar(select(Poker).where(Poker.row_id == poker_id))
        assert poker is not None
        assert poker.is_bettable is True
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("seed_options", "error_type"),
    [
        ({"actor_admin": False}, StartBettingNotAuthorizedError),
        ({"actor_approved": False}, StartBettingNotAuthorizedError),
        ({"active_poker": False}, ActivePokerNotFoundError),
        ({"chip_input": True}, PokerAwaitingChipsError),
        ({"betting_open": True}, BettingAlreadyOpenError),
    ],
)
async def test_start_betting_rejects_invalid_state_without_mutation(
    seed_options,
    error_type,
) -> None:
    engine, session_factory = await _session_factory()
    actor_id, poker_id, _ = await _seed(session_factory, **seed_options)

    async with session_factory() as session:
        with pytest.raises(error_type):
            await StartBettingUseCase(session).execute(actor_user_id=actor_id)

    if poker_id is not None:
        async with session_factory() as verification_session:
            poker = await verification_session.scalar(select(Poker).where(Poker.row_id == poker_id))
            assert poker is not None
            assert poker.is_bettable is seed_options.get("betting_open", False)
    await engine.dispose()


@pytest.mark.asyncio
async def test_start_betting_rejects_missing_actor() -> None:
    engine, session_factory = await _session_factory()
    await _seed(session_factory)

    async with session_factory() as session:
        with pytest.raises(StartBettingNotAuthorizedError):
            await StartBettingUseCase(session).execute(actor_user_id=999_999)

    await engine.dispose()


@pytest.mark.asyncio
async def test_notification_failure_does_not_rollback_opened_betting() -> None:
    engine, session_factory = await _session_factory()
    actor_id, poker_id, _ = await _seed(session_factory)

    class FailingNotifier:
        async def notify(self, *, user_ids):
            raise RuntimeError("network unavailable")

    result = await StartBettingFlow(
        session_factory=session_factory,
        notifier=FailingNotifier(),
    ).execute(actor_user_id=actor_id)

    assert result.poker_id == poker_id
    async with session_factory() as verification_session:
        poker = await verification_session.scalar(select(Poker).where(Poker.row_id == poker_id))
        assert poker is not None
        assert poker.is_bettable is True
    await engine.dispose()
