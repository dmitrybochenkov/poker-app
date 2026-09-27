import inspect

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.use_cases.poker.enter_player_chips import EnterPlayerChipsUseCase
from app.bot.telegram.handlers.admin import buyins as tg_admin_buyins
from app.bot.telegram.handlers.user import poker as tg_user_poker
from app.bot.vk.handlers.admin import cashier as vk_admin_cashier
from app.bot.vk.handlers.user import poker as vk_user_poker
from app.db.base import Base
from app.db.models.poker import Poker
from app.db.models.poker_data import PokerData
from app.db.models.poker_param import PokerParam
from app.db.models.user import User


async def _session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all,
            tables=[User.__table__, PokerParam.__table__, Poker.__table__, PokerData.__table__],
        )
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed(session_factory):
    async with session_factory() as session:
        admin = User(name="Admin", telegram_id=1, is_approved=True, is_admin=True)
        player = User(name="Player", vk_id=2, is_approved=True)
        params = PokerParam(
            buyin_size_chips=200,
            buyin_size_kopecks=20_000,
            bb_size_chips=10,
            max_buyins=3,
        )
        session.add_all([admin, player, params])
        await session.flush()
        poker = Poker(
            params_id=int(params.row_id),
            is_going=False,
            is_ready_for_chips_entering=True,
        )
        session.add(poker)
        await session.flush()
        poker_data = PokerData(
            date=poker.date,
            player_id=int(player.row_id),
            player_name=player.name,
            buyins=2,
            chips=100,
            money_kopecks=-10_000,
        )
        session.add(poker_data)
        await session.commit()
        return int(admin.row_id), int(player.row_id), int(poker_data.row_id)


@pytest.mark.asyncio
async def test_enter_player_chips_persists_chips_and_cashout_together():
    engine, session_factory = await _session_factory()
    admin_id, player_id, poker_data_id = await _seed(session_factory)

    async with session_factory() as session:
        result = await EnterPlayerChipsUseCase(session).execute(
            actor_user_id=admin_id,
            player_user_id=player_id,
            chips=500,
        )

    assert result.chips == 500
    assert result.money_kopecks == 10_000
    async with session_factory() as session:
        row = await session.get(PokerData, poker_data_id)
        assert row is not None
        assert row.chips == 500
        assert row.money_kopecks == 10_000
    await engine.dispose()


@pytest.mark.asyncio
async def test_player_can_atomically_enter_own_chips():
    engine, session_factory = await _session_factory()
    _, player_id, poker_data_id = await _seed(session_factory)

    async with session_factory() as session:
        result = await EnterPlayerChipsUseCase(session).execute(
            actor_user_id=player_id,
            player_user_id=player_id,
            chips=500,
        )

    assert result.player_id == player_id
    async with session_factory() as session:
        row = await session.get(PokerData, poker_data_id)
        assert row is not None
        assert (row.chips, row.money_kopecks) == (500, 10_000)
    await engine.dispose()


@pytest.mark.asyncio
async def test_enter_player_chips_rolls_back_both_values_when_atomic_mutation_fails():
    engine, session_factory = await _session_factory()
    admin_id, player_id, poker_data_id = await _seed(session_factory)

    async with session_factory() as session:
        use_case = EnterPlayerChipsUseCase(session)

        async def fail_after_chips(**kwargs):
            player = await use_case.poker_data_repository.get_player(
                date=kwargs["date"], player_id=kwargs["player_id"]
            )
            assert player is not None
            player.chips = int(kwargs["chips"])
            await session.flush()
            raise RuntimeError("cashout write failed")

        use_case.poker_data_repository.set_chips_and_cashout_without_commit = fail_after_chips
        with pytest.raises(RuntimeError, match="cashout write failed"):
            await use_case.execute(
                actor_user_id=admin_id,
                player_user_id=player_id,
                chips=500,
            )

    async with session_factory() as session:
        row = await session.get(PokerData, poker_data_id)
        assert row is not None
        assert row.chips == 100
        assert row.money_kopecks == -10_000
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["admin status refresh", "success response"])
async def test_post_commit_delivery_failure_does_not_undo_chip_entry(failure):
    engine, session_factory = await _session_factory()
    admin_id, player_id, poker_data_id = await _seed(session_factory)

    with pytest.raises(RuntimeError, match=failure):
        async with session_factory() as session:
            await EnterPlayerChipsUseCase(session).execute(
                actor_user_id=admin_id,
                player_user_id=player_id,
                chips=500,
            )
            raise RuntimeError(failure)

    async with session_factory() as session:
        row = await session.get(PokerData, poker_data_id)
        assert row is not None
        assert row.chips == 500
        assert row.money_kopecks == 10_000
    await engine.dispose()


@pytest.mark.parametrize(
    ("handler", "operation_count"),
    [
        (tg_user_poker.process_chips_input, 1),
        (vk_user_poker.handle_chips_input_text, 1),
        (tg_admin_buyins.cashout_select_callback, 1),
        (tg_admin_buyins.cashout_amount_input, 1),
        (vk_admin_cashier.handle_poker_cashout_select_event, 1),
        (vk_admin_cashier.handle_admin_cashout_amount_text, 1),
    ],
)
def test_chip_entry_transport_uses_atomic_operation(handler, operation_count):
    source = inspect.getsource(handler)

    assert source.count("EnterPlayerChipsUseCase") == operation_count
