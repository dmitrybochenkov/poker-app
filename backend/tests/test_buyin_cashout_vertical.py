import inspect

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.use_cases.poker.buyins import (
    AddBuyinUseCase,
    BuyinNotAuthorizedError,
    CorrectBuyinUseCase,
    InvalidBuyinCountError,
)
from app.db.base import Base
from app.db.models.buyin_data import BuyinData
from app.db.models.poker import Poker
from app.db.models.poker_data import PokerData
from app.db.models.poker_param import PokerParam
from app.db.models.user import User
from app.db.repositories.buyin_data_repository import BuyinDataRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.bot.telegram.handlers.admin import buyins as tg_buyins
from app.bot.vk.handlers.admin import buyins as vk_buyins


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
        player = User(name="Player", vk_id=2, is_approved=True)
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
    assert [row.buyins_count for row in history] == [1, 1]


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
    money_kopecks = (
        (chips - buyins * buyin_size_chips) * buyin_size_kopecks
    ) // buyin_size_chips
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
async def test_add_buyin_rolls_back_player_when_history_write_fails(
    buyin_sessions, monkeypatch
):
    admin_id, player_id, pdata_id, _ = await _seed(buyin_sessions)
    async with buyin_sessions() as session:
        use_case = AddBuyinUseCase(session)

        async def fail_history(self, **kwargs):
            raise RuntimeError("history failed")

        monkeypatch.setattr(BuyinDataRepository, "add_buyin", fail_history)
        with pytest.raises(RuntimeError, match="history failed"):
            await use_case.execute(
                actor_user_id=admin_id, target_user_id=player_id, buyins_count=1
            )
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
    admin_id, player_id, _, _ = await _seed(
        buyin_sessions, max_buyins=2, previous_winner=True
    )
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
                actor_user_id=admin_id, target_user_id=player_id, buyins_count=1
            )
            raise RuntimeError("delivery failed")
    async with buyin_sessions() as session:
        stored = await session.get(PokerData, pdata_id)
        history = (await session.execute(select(BuyinData))).scalars().all()
    assert stored is not None and stored.buyins == 1
    assert [row.buyins_count for row in history] == [1]
