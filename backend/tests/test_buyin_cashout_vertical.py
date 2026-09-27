import asyncio
import inspect
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.use_cases.poker.buyins import (
    AddBuyinUseCase,
    BuyinNotAuthorizedError,
    CorrectBuyinUseCase,
    InvalidBuyinCountError,
)
from app.bot.telegram.handlers.admin import buyins as tg_buyins
from app.bot.vk.handlers.admin import buyins as vk_buyins
from app.db.base import Base
from app.db.models.buyin_data import BuyinData
from app.db.models.poker import Poker
from app.db.models.poker_data import PokerData
from app.db.models.poker_param import PokerParam
from app.db.models.user import User
from app.db.repositories.buyin_data_repository import BuyinDataRepository
from app.db.repositories.poker_data_repository import PokerDataRepository


@pytest.fixture
async def buyin_sessions():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all,
            tables=[
                User.__table__,
                PokerParam.__table__,
                Poker.__table__,
                PokerData.__table__,
                BuyinData.__table__,
            ],
        )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    yield sessions
    await engine.dispose()


async def _seed(sessions, *, max_buyins=3, previous_winner=False):
    async with sessions() as session:
        admin = User(name="Admin", telegram_id=1, is_approved=True, is_admin=True)
        player = User(name="Player", vk_id=9002, is_approved=True)
        params = PokerParam(
            buyin_size_chips=200,
            buyin_size_kopecks=20_000,
            bb_size_chips=10,
            max_buyins=max_buyins,
            big_buyin=5,
            king_buyin=15,
            super_buyin=10,
        )
        session.add_all([admin, player, params])
        await session.flush()
        poker = Poker(params_id=int(params.row_id), cashier_id=int(admin.row_id))
        session.add(poker)
        await session.flush()
        pdata = PokerData(
            date=poker.date,
            player_id=int(player.row_id),
            player_name=player.name,
            is_prev_winner=previous_winner,
        )
        session.add(pdata)
        await session.commit()
        return int(admin.row_id), int(player.row_id), int(pdata.row_id), poker.date


@pytest.mark.asyncio
async def test_add_buyin_updates_player_and_appends_history(buyin_sessions):
    admin_id, player_id, pdata_id, _ = await _seed(buyin_sessions)
    async with buyin_sessions() as session:
        result = await AddBuyinUseCase(session).execute(
            actor_user_id=admin_id,
            target_user_id=player_id,
            buyins_count=2,
        )
    assert (result.total_buyins, result.big_buyin_count, result.super_buyin_count) == (2, 0, 0)
    async with buyin_sessions() as session:
        stored = await session.get(PokerData, pdata_id)
        history = (await session.execute(select(BuyinData))).scalars().all()
    assert stored is not None
    assert (stored.buyins, stored.big_buyin_count, stored.super_buyin_count) == (2, 0, 0)
    assert [(row.player_id, row.player_name, row.buyins_count) for row in history] == [
        (player_id, "Player", 2)
    ]


@pytest.mark.asyncio
async def test_repeated_buyin_adds_again_and_keeps_separate_history(buyin_sessions):
    admin_id, player_id, pdata_id, _ = await _seed(buyin_sessions)
    async with buyin_sessions() as session:
        await AddBuyinUseCase(session).execute(
            actor_user_id=admin_id, target_user_id=player_id, buyins_count=1
        )
    async with buyin_sessions() as session:
        await AddBuyinUseCase(session).execute(
            actor_user_id=admin_id, target_user_id=player_id, buyins_count=1
        )
    async with buyin_sessions() as session:
        stored = await session.get(PokerData, pdata_id)
        history = (await session.execute(select(BuyinData))).scalars().all()
    assert stored is not None and stored.buyins == 2
    assert [(row.buyins_count, row.operation_id) for row in history] == [(1, None), (1, None)]


@pytest.mark.asyncio
async def test_same_buyin_submission_is_applied_once(buyin_sessions):
    admin_id, player_id, pdata_id, _ = await _seed(buyin_sessions)

    async with buyin_sessions() as session:
        first = await AddBuyinUseCase(session).execute(
            actor_user_id=admin_id,
            target_user_id=player_id,
            buyins_count=1,
            operation_id="tg:callback-123",
        )
    async with buyin_sessions() as session:
        replay = await AddBuyinUseCase(session).execute(
            actor_user_id=admin_id,
            target_user_id=player_id,
            buyins_count=1,
            operation_id="tg:callback-123",
        )

    async with buyin_sessions() as session:
        stored = await session.get(PokerData, pdata_id)
        history = (await session.execute(select(BuyinData))).scalars().all()
    assert first.applied is True
    assert replay.applied is False
    assert stored is not None and stored.buyins == 1
    assert [(row.player_id, row.buyins_count, row.operation_id) for row in history] == [
        (player_id, 1, "tg:callback-123")
    ]


@pytest.mark.asyncio
async def test_distinct_submissions_allow_identical_later_buyins(buyin_sessions):
    admin_id, player_id, pdata_id, _ = await _seed(buyin_sessions)

    for operation_id in ("vk:event-1", "vk:event-2"):
        async with buyin_sessions() as session:
            result = await AddBuyinUseCase(session).execute(
                actor_user_id=admin_id,
                target_user_id=player_id,
                buyins_count=1,
                operation_id=operation_id,
            )
            assert result.applied is True

    async with buyin_sessions() as session:
        stored = await session.get(PokerData, pdata_id)
        history = (
            (await session.execute(select(BuyinData).order_by(BuyinData.row_id))).scalars().all()
        )
    assert stored is not None and stored.buyins == 2
    assert [(row.player_id, row.buyins_count, row.operation_id) for row in history] == [
        (player_id, 1, "vk:event-1"),
        (player_id, 1, "vk:event-2"),
    ]


@pytest.mark.asyncio
async def test_current_buyin_correction_changes_total_only_without_history(buyin_sessions):
    _, player_id, pdata_id, poker_date = await _seed(buyin_sessions)
    async with buyin_sessions() as session:
        repository = PokerDataRepository(session)
        await repository.add_buyins_without_commit(
            date=poker_date,
            player_id=player_id,
            buyins_count=10,
            big_buyin_count=1,
            super_buyin_count=1,
        )
        corrected = await repository.add_buyins_without_commit(
            date=poker_date,
            player_id=player_id,
            buyins_count=-7,
            big_buyin_count=0,
            super_buyin_count=0,
        )
        await session.commit()
    assert corrected is not None
    assert (corrected.buyins, corrected.big_buyin_count, corrected.super_buyin_count) == (3, 1, 1)
    async with buyin_sessions() as session:
        stored = await session.get(PokerData, pdata_id)
        history = (await session.execute(select(BuyinData))).scalars().all()
    assert stored is not None and stored.buyins == 3
    assert history == []


def test_current_cashout_arithmetic_contract():
    chips = 500
    buyins = 2
    buyin_size_chips = 200
    buyin_size_kopecks = 20_000
    money_kopecks = ((chips - buyins * buyin_size_chips) * buyin_size_kopecks) // buyin_size_chips
    assert money_kopecks == 10_000


def test_field_null_and_zero_contracts():
    assert PokerData.__table__.c.buyins.nullable is False
    assert PokerData.__table__.c.big_buyin_count.nullable is False
    assert PokerData.__table__.c.super_buyin_count.nullable is False
    assert PokerData.__table__.c.chips.nullable is True
    assert PokerData.__table__.c.money_kopecks.nullable is False


@pytest.mark.asyncio
async def test_add_buyin_operation_commits_player_and_history_together(buyin_sessions):
    admin_id, player_id, pdata_id, _ = await _seed(buyin_sessions)
    async with buyin_sessions() as session:
        result = await AddBuyinUseCase(session).execute(
            actor_user_id=admin_id, target_user_id=player_id, buyins_count=2
        )
    assert (result.added_buyins, result.total_buyins) == (2, 2)
    async with buyin_sessions() as session:
        stored = await session.get(PokerData, pdata_id)
        history = (await session.execute(select(BuyinData))).scalars().all()
    assert stored is not None and stored.buyins == 2
    assert [row.buyins_count for row in history] == [2]


@pytest.mark.asyncio
async def test_player_can_add_own_buyin_but_not_another_players(buyin_sessions):
    _, player_id, pdata_id, _ = await _seed(buyin_sessions)
    async with buyin_sessions() as session:
        await AddBuyinUseCase(session).execute(
            actor_user_id=player_id, target_user_id=player_id, buyins_count=1
        )
    async with buyin_sessions() as session:
        with pytest.raises(BuyinNotAuthorizedError):
            await AddBuyinUseCase(session).execute(
                actor_user_id=None, target_user_id=player_id, buyins_count=1
            )
    async with buyin_sessions() as session:
        stored = await session.get(PokerData, pdata_id)
    assert stored is not None and stored.buyins == 1


@pytest.mark.asyncio
async def test_add_buyin_rolls_back_player_when_history_write_fails(buyin_sessions, monkeypatch):
    admin_id, player_id, pdata_id, _ = await _seed(buyin_sessions)
    async with buyin_sessions() as session:
        use_case = AddBuyinUseCase(session)

        async def fail_history(self, **kwargs):
            raise RuntimeError("history failed")

        monkeypatch.setattr(BuyinDataRepository, "add_buyin", fail_history)
        with pytest.raises(RuntimeError, match="history failed"):
            await use_case.execute(actor_user_id=admin_id, target_user_id=player_id, buyins_count=1)
    async with buyin_sessions() as session:
        stored = await session.get(PokerData, pdata_id)
    assert stored is not None and stored.buyins == 0


@pytest.mark.asyncio
async def test_correct_buyin_preserves_special_counts_and_writes_no_history(buyin_sessions):
    admin_id, player_id, pdata_id, poker_date = await _seed(buyin_sessions)
    async with buyin_sessions() as session:
        await PokerDataRepository(session).add_buyins_without_commit(
            date=poker_date,
            player_id=player_id,
            buyins_count=10,
            big_buyin_count=1,
            super_buyin_count=1,
        )
        await session.commit()
    async with buyin_sessions() as session:
        result = await CorrectBuyinUseCase(session).execute(
            actor_user_id=admin_id, target_user_id=player_id, total_buyins=3
        )
    assert (result.previous_buyins, result.total_buyins) == (10, 3)
    assert (result.big_buyin_count, result.super_buyin_count) == (1, 1)
    async with buyin_sessions() as session:
        stored = await session.get(PokerData, pdata_id)
        history = (await session.execute(select(BuyinData))).scalars().all()
    assert stored is not None and stored.buyins == 3
    assert history == []


@pytest.mark.asyncio
async def test_special_buyin_validation_and_counters_are_preserved(buyin_sessions):
    admin_id, player_id, _, _ = await _seed(buyin_sessions, max_buyins=2, previous_winner=True)
    async with buyin_sessions() as session:
        result = await AddBuyinUseCase(session).execute(
            actor_user_id=admin_id, target_user_id=player_id, buyins_count=15
        )
    assert (result.big_buyin_count, result.super_buyin_count) == (1, 1)
    async with buyin_sessions() as session:
        with pytest.raises(InvalidBuyinCountError):
            await AddBuyinUseCase(session).execute(
                actor_user_id=admin_id, target_user_id=player_id, buyins_count=7
            )


@pytest.mark.parametrize(
    "handler",
    [tg_buyins.buyin_count_callback, vk_buyins.handle_poker_buyin_count_select_event],
)
def test_tg_vk_add_buyin_handlers_use_shared_atomic_operation(handler):
    source = inspect.getsource(handler)
    assert "AddBuyinUseCase" in source
    assert "operation_id=" in source
    assert "result.applied" in source


def test_tg_vk_add_buyin_handlers_use_transport_submission_identity():
    assert 'operation_id=f"tg:{callback.id}"' in inspect.getsource(tg_buyins.buyin_count_callback)
    assert 'operation_id=f"vk:{event_id}"' in inspect.getsource(
        vk_buyins.handle_poker_buyin_count_select_event
    )


class _HandlerSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _handler_result(*, applied: bool):
    return SimpleNamespace(
        poker_date=date(2026, 9, 27),
        cashier_user_id=1,
        player_user_id=2,
        player_name="Player",
        added_buyins=1,
        total_buyins=1,
        applied=applied,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("applied", [True, False])
async def test_tg_add_buyin_wires_callback_identity_and_skips_replay_fanout(monkeypatch, applied):
    execute = AsyncMock(return_value=_handler_result(applied=applied))

    class UseCase:
        def __init__(self, session):
            pass

    UseCase.execute = execute

    notify = AsyncMock()
    monkeypatch.setattr(tg_buyins, "SessionFactory", lambda: _HandlerSession())
    monkeypatch.setattr(tg_buyins, "AddBuyinUseCase", UseCase)
    monkeypatch.setattr(tg_buyins, "resolve_telegram_user_id", AsyncMock(return_value=10))
    monkeypatch.setattr(tg_buyins, "_clear_inline_keyboard", AsyncMock())
    monkeypatch.setattr(tg_buyins, "_notify_about_buyin", notify)
    callback = SimpleNamespace(
        id="callback-77",
        data="pokerbuyincount:2:1",
        from_user=SimpleNamespace(id=100),
        message=None,
        answer=AsyncMock(),
    )

    await tg_buyins.buyin_count_callback(callback)

    execute.assert_awaited_once_with(
        actor_user_id=10,
        target_user_id=2,
        buyins_count=1,
        operation_id="tg:callback-77",
    )
    assert notify.await_count == int(applied)


@pytest.mark.asyncio
@pytest.mark.parametrize("applied", [True, False])
async def test_vk_add_buyin_wires_event_identity_and_skips_replay_fanout(monkeypatch, applied):
    execute = AsyncMock(return_value=_handler_result(applied=applied))

    class UseCase:
        def __init__(self, session):
            pass

    UseCase.execute = execute

    notify = AsyncMock()
    monkeypatch.setattr(vk_buyins, "SessionFactory", lambda: _HandlerSession())
    monkeypatch.setattr(vk_buyins, "AddBuyinUseCase", UseCase)
    monkeypatch.setattr(vk_buyins, "resolve_vk_user_id", AsyncMock(return_value=10))
    monkeypatch.setattr(vk_buyins, "_notify_about_buyin", notify)
    monkeypatch.setattr(vk_buyins, "send_vk_message_event_answer", AsyncMock())
    monkeypatch.setattr(vk_buyins, "_clear_event_inline_keyboard_if_possible", AsyncMock())
    monkeypatch.setattr(vk_buyins, "send_vk_message", AsyncMock())

    await vk_buyins.handle_poker_buyin_count_select_event(
        admin_user_id=100,
        peer_id=100,
        event_id="event-88",
        conversation_message_id=5,
        callback_payload={"player_id": 2, "count": 1},
        action="poker_buyin_count_select",
        handle_admin_text_commands=AsyncMock(),
    )

    execute.assert_awaited_once_with(
        actor_user_id=10,
        target_user_id=2,
        buyins_count=1,
        operation_id="vk:event-88",
    )
    assert notify.await_count == int(applied)


@pytest.mark.parametrize(
    "handler",
    [
        tg_buyins.buyin_correct_confirm_callback,
        vk_buyins.handle_buyin_correction_confirmation_event,
    ],
)
def test_tg_vk_correction_handlers_use_shared_atomic_operation(handler):
    source = inspect.getsource(handler)
    assert "CorrectBuyinUseCase" in source


@pytest.mark.asyncio
async def test_post_commit_delivery_failure_does_not_undo_buyin(buyin_sessions):
    admin_id, player_id, pdata_id, _ = await _seed(buyin_sessions)
    with pytest.raises(RuntimeError, match="delivery failed"):
        async with buyin_sessions() as session:
            await AddBuyinUseCase(session).execute(
                actor_user_id=admin_id,
                target_user_id=player_id,
                buyins_count=1,
                operation_id="tg:lost-response",
            )
            raise RuntimeError("delivery failed")
    async with buyin_sessions() as session:
        replay = await AddBuyinUseCase(session).execute(
            actor_user_id=admin_id,
            target_user_id=player_id,
            buyins_count=1,
            operation_id="tg:lost-response",
        )
    async with buyin_sessions() as session:
        stored = await session.get(PokerData, pdata_id)
        history = (await session.execute(select(BuyinData))).scalars().all()
    assert stored is not None and stored.buyins == 1
    assert [row.buyins_count for row in history] == [1]
    assert replay.applied is False


@pytest.mark.asyncio
async def test_concurrent_same_operation_is_applied_once(tmp_path):
    database_path = tmp_path / "buyin-replay.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all,
            tables=[
                User.__table__,
                PokerParam.__table__,
                Poker.__table__,
                PokerData.__table__,
                BuyinData.__table__,
            ],
        )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    admin_id, player_id, pdata_id, _ = await _seed(sessions)

    async def submit():
        async with sessions() as session:
            return await AddBuyinUseCase(session).execute(
                actor_user_id=admin_id,
                target_user_id=player_id,
                buyins_count=1,
                operation_id="vk:concurrent-event",
            )

    first, second = await asyncio.gather(submit(), submit())
    async with sessions() as session:
        stored = await session.get(PokerData, pdata_id)
        history = (await session.execute(select(BuyinData))).scalars().all()
    await engine.dispose()

    assert sorted((first.applied, second.applied)) == [False, True]
    assert stored is not None and stored.buyins == 1
    assert [(row.buyins_count, row.operation_id) for row in history] == [(1, "vk:concurrent-event")]
