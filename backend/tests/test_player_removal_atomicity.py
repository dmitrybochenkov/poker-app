from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
import pytest

from app.application.use_cases.poker.manage_players import ManagePokerPlayersUseCase
from app.db.base import Base
from app.db.models.buyin_data import BuyinData
from app.db.models.poker import Poker
from app.db.models.poker_data import PokerData
from app.db.models.poker_param import PokerParam
from app.db.models.poker_room_denied import PokerRoomDenied
from app.db.models.user import User
from app.db.repositories.buyin_data_repository import BuyinDataRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.poker_room_denied_repository import PokerRoomDeniedRepository
from app.db.repositories.user_repository import UserRepository


@pytest.fixture
async def removal_store():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all,
            tables=[
                User.__table__, PokerParam.__table__, Poker.__table__,
                PokerData.__table__, BuyinData.__table__, PokerRoomDenied.__table__,
            ],
        )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    yield engine, sessions
    await engine.dispose()


async def _seed(sessions):
    async with sessions() as session:
        user = User(name="Player", telegram_id=10, is_approved=True)
        params = PokerParam(
            buyin_size_chips=200, buyin_size_kopecks=20_000,
            bb_size_chips=10, max_buyins=3, big_buyin=5,
            king_buyin=15, super_buyin=10,
        )
        session.add_all([user, params])
        await session.flush()
        poker = Poker(params_id=int(params.row_id), cashier_id=int(user.row_id))
        session.add(poker)
        await session.flush()
        session.add_all([
            PokerData(poker_id=int(poker.row_id), date=poker.date, player_id=int(user.row_id), player_name=user.name),
            BuyinData(
                poker_id=int(poker.row_id), poker_date=poker.date, player_id=int(user.row_id),
                player_name=user.name, buyins_count=2,
            ),
        ])
        await session.commit()
        return int(user.row_id), int(poker.row_id), poker.date


def _use_case(session):
    return ManagePokerPlayersUseCase(
        poker_repository=PokerRepository(session),
        poker_data_repository=PokerDataRepository(session),
        buyin_data_repository=BuyinDataRepository(session),
        poker_room_denied_repository=PokerRoomDeniedRepository(session),
        user_repository=UserRepository(session),
    )


async def _assert_original_state(sessions, *, player_id, poker_date):
    async with sessions() as session:
        assert await PokerDataRepository(session).get_player(
            date=poker_date, player_id=player_id
        ) is not None
        assert (await session.execute(select(BuyinData))).scalars().all()
        assert await PokerRoomDeniedRepository(session).get(user_row_id=player_id) is None


@pytest.mark.asyncio
async def test_remove_player_preserves_success_repeated_and_cashier_semantics(removal_store):
    _, sessions = removal_store
    player_id, poker_id, _ = await _seed(sessions)
    async with sessions() as session:
        assert await _use_case(session).remove_player_from_active_poker(
            player_id=player_id
        ) is True
        assert await _use_case(session).remove_player_from_active_poker(
            player_id=player_id
        ) is False
    async with sessions() as session:
        poker = await session.get(Poker, poker_id)
        assert poker is not None and poker.cashier_id == player_id
        assert (await session.execute(select(BuyinData))).scalars().all() == []
        assert await PokerRoomDeniedRepository(session).get(user_row_id=player_id) is not None


@pytest.mark.asyncio
async def test_remove_player_rolls_back_when_player_delete_fails(removal_store):
    engine, sessions = removal_store
    player_id, _, poker_date = await _seed(sessions)

    def fail_player_delete(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("DELETE FROM POKER_DATA"):
            raise RuntimeError("player delete failed")

    event.listen(engine.sync_engine, "before_cursor_execute", fail_player_delete)
    try:
        async with sessions() as session:
            with pytest.raises(RuntimeError, match="player delete failed"):
                await _use_case(session).remove_player_from_active_poker(player_id=player_id)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", fail_player_delete)
    await _assert_original_state(sessions, player_id=player_id, poker_date=poker_date)


@pytest.mark.asyncio
async def test_remove_player_rolls_back_when_deny_insert_fails(removal_store):
    engine, sessions = removal_store
    player_id, _, poker_date = await _seed(sessions)

    def fail_deny_insert(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("INSERT INTO POKER_ROOM_DENIED"):
            raise RuntimeError("deny insert failed")

    event.listen(engine.sync_engine, "before_cursor_execute", fail_deny_insert)
    try:
        async with sessions() as session:
            with pytest.raises(RuntimeError, match="deny insert failed"):
                await _use_case(session).remove_player_from_active_poker(player_id=player_id)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", fail_deny_insert)
    await _assert_original_state(sessions, player_id=player_id, poker_date=poker_date)
