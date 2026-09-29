import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.use_cases.poker.calculate_poker_result import (
    CalculatedPlayer,
    CalculatePokerNotAuthorizedError,
    CalculatePokerResultUseCase,
    MissingPlayerChipsError,
    PokerChipTotalMismatchError,
    PokerNotReadyForCalculationError,
    _calculate_transfers,
)
from app.db.base import Base
from app.db.models.bet import Bet
from app.db.models.bet_param import BetParam
from app.db.models.bet_tournament_param import BetTournamentParam
from app.db.models.poker import Poker
from app.db.models.poker_data import PokerData
from app.db.models.poker_param import PokerParam
from app.db.models.user import User


async def _setup(*, first_chips=0, second_chips=400):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        admin = User(name="Admin", telegram_id=1, is_approved=True, is_admin=True)
        first = User(name="First Player", telegram_id=2, is_approved=True)
        second = User(name="Second Player", vk_id=3, is_approved=True)
        params = PokerParam(
            buyin_size_chips=200,
            buyin_size_kopecks=20_000,
            bb_size_chips=10,
            max_buyins=3,
        )
        bet_params = BetParam(
            small_size_kopecks=10_000,
            small_score=2,
            small_score_combo=5,
            big_size_kopecks=40_000,
            big_score=4,
            big_score_combo=10,
        )
        session.add_all([admin, first, second, params, bet_params])
        await session.flush()
        session.add(BetTournamentParam(tournament_type="regular", bet_param_id=bet_params.row_id))
        poker = Poker(params_id=params.row_id, is_going=False, is_ready_for_chips_entering=True)
        session.add(poker)
        await session.flush()
        session.add_all([
            PokerData(poker_id=poker.row_id, date=poker.date, player_id=first.row_id, player_name=first.name,
                      buyins=1, chips=first_chips, money_kopecks=111),
            PokerData(poker_id=poker.row_id, date=poker.date, player_id=second.row_id, player_name=second.name,
                      buyins=1, chips=second_chips, money_kopecks=222),
            Bet(poker_id=poker.row_id, date=poker.date, better_id=admin.row_id, better_name=admin.name,
                amount_kopecks=10_000, params_id=bet_params.row_id,
                winner_name=second.name, loser_name=first.name, score=0),
        ])
        await session.commit()
        return engine, sessions, admin.row_id, poker.row_id


async def _assert_unchanged(sessions, poker_id):
    async with sessions() as session:
        poker = await session.get(Poker, poker_id)
        rows = sorted((await session.execute(select(PokerData))).scalars(), key=lambda x: x.row_id)
        bet = (await session.execute(select(Bet))).scalars().one()
        assert [row.money_kopecks for row in rows] == [111, 222]
        assert bet.score == 0
        assert poker.is_ready_for_chips_entering is True
        assert poker.winners is None and poker.loosers is None


@pytest.mark.asyncio
async def test_final_calculation_preserves_business_results_and_accepts_zero_chips():
    engine, sessions, admin_id, poker_id = await _setup()
    async with sessions() as session:
        result = await CalculatePokerResultUseCase(session).execute(actor_user_id=admin_id)

    assert result.winners == ("Second Player",)
    assert result.losers == ("First Player",)
    assert len(result.recipient_user_ids) == 3
    assert len(set(result.recipient_user_ids)) == 3
    assert [(row.player_name, row.money_kopecks) for row in result.players] == [
        ("First Player", -20_000), ("Second Player", 20_000)
    ]
    assert [
        (item.from_user_id, item.from_name, item.to_user_id, item.to_name, item.amount_kopecks)
        for item in result.transfers
    ] == [
        (result.players[0].player_id, "First Player", result.players[1].player_id, "Second Player", 20_000)
    ]
    async with sessions() as session:
        poker = await session.get(Poker, poker_id)
        rows = sorted((await session.execute(select(PokerData))).scalars(), key=lambda x: x.row_id)
        bet = (await session.execute(select(Bet))).scalars().one()
        assert [row.money_kopecks for row in rows] == [-20_000, 20_000]
        assert bet.score == 5
        assert poker.is_ready_for_chips_entering is False
        assert poker.winners == "Second Player" and poker.loosers == "First Player"
    await engine.dispose()


@pytest.mark.asyncio
async def test_null_chips_rejected_before_mutation_even_when_aggregate_would_match():
    engine, sessions, admin_id, poker_id = await _setup(first_chips=None)
    async with sessions() as session:
        with pytest.raises(MissingPlayerChipsError) as error:
            await CalculatePokerResultUseCase(session).execute(actor_user_id=admin_id)
    assert error.value.player_names == ("First Player",)
    await _assert_unchanged(sessions, poker_id)
    await engine.dispose()


@pytest.mark.asyncio
async def test_final_calculation_rejects_non_admin_without_mutation():
    engine, sessions, admin_id, poker_id = await _setup()
    async with sessions() as session:
        admin = await session.get(User, admin_id)
        admin.is_admin = False
        await session.commit()
    async with sessions() as session:
        with pytest.raises(CalculatePokerNotAuthorizedError):
            await CalculatePokerResultUseCase(session).execute(actor_user_id=admin_id)
    await _assert_unchanged(sessions, poker_id)
    await engine.dispose()


@pytest.mark.asyncio
async def test_final_calculation_rejects_invalid_poker_state_without_mutation():
    engine, sessions, admin_id, poker_id = await _setup()
    async with sessions() as session:
        poker = await session.get(Poker, poker_id)
        poker.is_ready_for_chips_entering = False
        await session.commit()
    async with sessions() as session:
        with pytest.raises(PokerNotReadyForCalculationError):
            await CalculatePokerResultUseCase(session).execute(actor_user_id=admin_id)
    await engine.dispose()


@pytest.mark.asyncio
async def test_final_calculation_rejects_chip_total_mismatch_without_mutation():
    engine, sessions, admin_id, poker_id = await _setup(second_chips=395)
    async with sessions() as session:
        with pytest.raises(PokerChipTotalMismatchError) as error:
            await CalculatePokerResultUseCase(session).execute(actor_user_id=admin_id)
    assert error.value.diff == -5
    await _assert_unchanged(sessions, poker_id)
    await engine.dispose()


@pytest.mark.asyncio
async def test_repeated_final_calculation_does_not_apply_results_twice():
    engine, sessions, admin_id, _ = await _setup()
    async with sessions() as session:
        await CalculatePokerResultUseCase(session).execute(actor_user_id=admin_id)
    async with sessions() as session:
        with pytest.raises(PokerNotReadyForCalculationError):
            await CalculatePokerResultUseCase(session).execute(actor_user_id=admin_id)
    await engine.dispose()


def test_transfer_dto_preserves_canonical_ids_when_names_are_equal():
    transfers = _calculate_transfers(
        [
            CalculatedPlayer(player_id=10, player_name="Алексей", money_kopecks=-10_000),
            CalculatedPlayer(player_id=20, player_name="Алексей", money_kopecks=10_000),
        ]
    )

    assert len(transfers) == 1
    assert transfers[0].from_user_id == 10
    assert transfers[0].to_user_id == 20


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_point", ["participant", "scoring", "final_state"])
async def test_final_calculation_rolls_back_every_mutation(failure_point):
    engine, sessions, admin_id, poker_id = await _setup()
    async with sessions() as session:
        use_case = CalculatePokerResultUseCase(session)
        if failure_point == "participant":
            original = use_case.poker_data_repository.set_cashout_without_commit
            calls = 0
            async def fail_second(**kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise RuntimeError("participant failed")
                return await original(**kwargs)
            use_case.poker_data_repository.set_cashout_without_commit = fail_second
        elif failure_point == "scoring":
            async def fail_scoring(**kwargs):
                raise RuntimeError("scoring failed")
            use_case.bet_scores.execute_without_commit = fail_scoring
        else:
            async def fail_final_state(**kwargs):
                raise RuntimeError("final state failed")
            use_case.poker_repository.finish_chips_entering_without_commit = fail_final_state
        with pytest.raises(RuntimeError, match=failure_point.replace("_", " ")):
            await use_case.execute(actor_user_id=admin_id)
    await _assert_unchanged(sessions, poker_id)
    await engine.dispose()
