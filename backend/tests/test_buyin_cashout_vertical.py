from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.use_cases.poker.manage_players import ManagePokerPlayersUseCase
from app.db.base import Base
from app.db.models.buyin_data import BuyinData
from app.db.models.poker import Poker
from app.db.models.poker_data import PokerData
from app.db.models.poker_param import PokerParam
from app.db.models.user import User
from app.db.repositories.buyin_data_repository import BuyinDataRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository


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
async def test_current_add_buyin_updates_player_and_appends_history(buyin_sessions):
    _, player_id, pdata_id, poker_date = await _seed(buyin_sessions)
    async with buyin_sessions() as session:
        result = await ManagePokerPlayersUseCase(
            poker_repository=PokerRepository(session),
            poker_data_repository=PokerDataRepository(session),
            buyin_data_repository=BuyinDataRepository(session),
        ).add_buyin_to_active_player(
            player_id=player_id,
            buyins_count=2,
            big_buyin_count=1,
            super_buyin_count=0,
            poker_date=poker_date,
        )
    assert result is not None
    assert (result.buyins, result.big_buyin_count, result.super_buyin_count) == (2, 1, 0)
    async with buyin_sessions() as session:
        stored = await session.get(PokerData, pdata_id)
        history = (await session.execute(select(BuyinData))).scalars().all()
    assert stored is not None
    assert (stored.buyins, stored.big_buyin_count, stored.super_buyin_count) == (2, 1, 0)
    assert [(row.player_id, row.player_name, row.buyins_count) for row in history] == [
        (player_id, "Player", 2)
    ]


@pytest.mark.asyncio
async def test_current_repeated_buyin_adds_again_and_keeps_separate_history(buyin_sessions):
    _, player_id, pdata_id, poker_date = await _seed(buyin_sessions)
    async with buyin_sessions() as session:
        use_case = ManagePokerPlayersUseCase(
            poker_repository=PokerRepository(session),
            poker_data_repository=PokerDataRepository(session),
            buyin_data_repository=BuyinDataRepository(session),
        )
        await use_case.add_buyin_to_active_player(
            player_id=player_id, buyins_count=1, poker_date=poker_date
        )
        await use_case.add_buyin_to_active_player(
            player_id=player_id, buyins_count=1, poker_date=poker_date
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
        await repository.add_buyins(
            date=poker_date,
            player_id=player_id,
            buyins_count=10,
            big_buyin_count=1,
            super_buyin_count=1,
        )
        corrected = await repository.add_buyins(
            date=poker_date,
            player_id=player_id,
            buyins_count=-7,
            big_buyin_count=0,
            super_buyin_count=0,
        )
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
