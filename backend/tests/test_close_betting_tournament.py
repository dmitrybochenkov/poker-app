import asyncio
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.use_cases.poker.close_betting_tournament import (
    CloseBettingTournamentUseCase,
    calculate_payouts,
)
from app.application.use_cases.poker.stat import StatUseCases
from app.db.base import Base
from app.db.models.bet import Bet
from app.db.models.bet_param import BetParam
from app.db.models.bet_tournament import BetTournament
from app.db.models.bet_tournament_param import BetTournamentParam
from app.db.models.bet_tournament_result import BetTournamentResult
from app.db.models.bet_tournament_role_result import BetTournamentRoleResult
from app.db.models.poker import Poker
from app.db.models.poker_data import PokerData
from app.db.models.poker_param import PokerParam
from app.db.models.user import User
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.bet_tournament_repository import BetTournamentRepository
from app.db.repositories.bet_tournament_param_repository import BetTournamentParamRepository
from app.db.repositories.bet_tournament_result_repository import BetTournamentResultRepository
from app.db.repositories.bet_tournament_role_result_repository import BetTournamentRoleResultRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.user_repository import UserRepository


def _amounts(result):
    return {item.player_name: item.amount_kopecks for item in result.payouts}


def test_two_way_tie_occupies_first_and_second_places():
    result = calculate_payouts(
        bank_kopecks=832_000,
        scores_by_user_id={1: 7, 2: 7, 3: 6},
        names_by_user_id={1: "A", 2: "B", 3: "C"},
        prize_percents=(50, 33, 17),
    )
    assert _amounts(result) == {"A": 345_280, "B": 345_280, "C": 141_440}
    assert result.place_user_ids == ((1, 2), (1, 2), (3,))
    assert result.place_names == (("A", "B"), ("A", "B"), ("C",))
    assert result.total_payout_kopecks == 832_000
    assert result.remainder_kopecks == 0


def test_three_way_tie_shares_whole_podium_with_floor_remainder():
    result = calculate_payouts(
        bank_kopecks=784_000,
        scores_by_user_id={1: 2, 2: 2, 3: 2},
        names_by_user_id={1: "A", 2: "B", 3: "C"},
        prize_percents=(50, 33, 17),
    )
    assert _amounts(result) == {"A": 261_333, "B": 261_333, "C": 261_333}
    assert result.total_payout_kopecks == 783_999
    assert result.remainder_kopecks == 1


def test_n_way_tie_on_third_place_and_players_below_podium_get_zero():
    result = calculate_payouts(
        bank_kopecks=768_000,
        scores_by_user_id={1: 4, 2: 3, 3: 2, 4: 2, 5: 2, 6: 2, 7: 1},
        names_by_user_id={1: "A", 2: "B", 3: "C", 4: "D", 5: "E", 6: "F", 7: "G"},
        prize_percents=(50, 33, 17),
    )
    assert _amounts(result) == {
        "A": 384_000,
        "B": 253_440,
        "C": 32_640,
        "D": 32_640,
        "E": 32_640,
        "F": 32_640,
    }
    assert "G" not in _amounts(result)
    assert result.total_payout_kopecks <= 768_000


def test_percentages_are_not_hardcoded_and_math_is_integer_only():
    result = calculate_payouts(
        bank_kopecks=101,
        scores_by_user_id={1: 3, 2: 2, 3: 1},
        names_by_user_id={1: "A", 2: "B", 3: "C"},
        prize_percents=(60, 25, 10),
    )
    assert _amounts(result) == {"A": 60, "B": 25, "C": 10}
    assert result.remainder_kopecks == 6
    assert all(isinstance(item.amount_kopecks, int) for item in result.payouts)


def test_runtime_preserves_raw_name_snapshot_and_uses_it_for_tie_order():
    result = calculate_payouts(
        bank_kopecks=100,
        scores_by_user_id={1: 3, 2: 3},
        names_by_user_id={1: "  Z  ", 2: "A"},
        prize_percents=(50, 30, 20),
    )

    assert [item.player_name for item in result.payouts] == ["  Z  ", "A"]


class _Session:
    commits = 0
    rollbacks = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class _NoOpResults:
    async def add_many(self, **kwargs):
        return None


class _PokerData:
    async def list_for_poker_ids(self, *, poker_ids):
        return [
            SimpleNamespace(poker_id=poker_id, player_id=user_id, money_kopecks=0)
            for poker_id in poker_ids
            for user_id in range(1, 101)
        ]


def _dependencies():
    return {
        "tournament_result_repository": _NoOpResults(),
        "tournament_role_result_repository": _NoOpResults(),
        "poker_data_repository": _PokerData(),
    }


@pytest.mark.asyncio
async def test_preview_does_not_mutate_and_confirm_revalidates_and_is_idempotent():
    tournament = SimpleNamespace(
        row_id=1,
        tournament_type="regular",
        params_id=3,
        start_date=date(2025, 4, 1),
        end_date=date(2025, 8, 31),
        current_bank_kopecks=832_000,
        is_paid=False,
    )

    class Users:
        async def get_by_row_id(self, value):
            return SimpleNamespace(is_admin=True, is_approved=True)

    class Tournaments:
        calls = 0
        force_conflict = False

        async def get_by_id(self, **kwargs):
            self.calls += 1
            return tournament

        async def list_eligible_for_finalization(self, **kwargs):
            return [tournament]

        async def finalize_if_unpaid(self, **kwargs):
            if self.force_conflict:
                return False
            if tournament.is_paid:
                return False
            tournament.is_paid = True
            return True

    class Params:
        rows = {
            1: SimpleNamespace(
                row_id=1,
                tournament_type="regular",
                bet_param_id=1,
                percent_to_first=60,
                percent_to_second=25,
                percent_to_third=10,
            ),
            3: SimpleNamespace(
                row_id=3,
                tournament_type="regular",
                bet_param_id=1,
                percent_to_first=50,
                percent_to_second=33,
                percent_to_third=17,
            ),
        }

        async def get_by_id(self, *, row_id):
            return self.rows.get(row_id)

    class Bets:
        async def list_for_period(self, **kwargs):
            return [
                SimpleNamespace(row_id=1, poker_id=1, date=date(2025, 4, 1), better_id=1, better_name="A", winner_id=1, loser_id=1, score=7),
                SimpleNamespace(row_id=2, poker_id=2, date=date(2025, 4, 2), better_id=2, better_name="B", winner_id=2, loser_id=2, score=7),
                SimpleNamespace(row_id=3, poker_id=3, date=date(2025, 4, 3), better_id=3, better_name="C", winner_id=3, loser_id=3, score=6),
            ]

    session = _Session()
    tournaments = Tournaments()
    use_case = CloseBettingTournamentUseCase(
        session=session,
        user_repository=Users(),
        tournament_repository=tournaments,
        tournament_param_repository=Params(),
        bet_repository=Bets(),
        **_dependencies(),
    )
    eligible = await use_case.list_eligible(actor_user_id=1, today=date(2026, 1, 1))
    _, preview = await use_case.preview(
        actor_user_id=1, tournament_id=1, today=date(2026, 1, 1)
    )
    assert eligible == [tournament] and tournament.is_paid is False and session.commits == 0
    assert _amounts(preview) == {"A": 345_280, "B": 345_280, "C": 141_440}
    _, confirmed = await use_case.confirm(
        actor_user_id=1, tournament_id=1, today=date(2026, 1, 1)
    )
    assert _amounts(confirmed) == _amounts(preview)
    assert tournament.is_paid is True and session.commits == 1 and tournaments.calls == 2
    tournament.is_paid = False
    tournaments.force_conflict = True
    with pytest.raises(ValueError):
        await use_case.confirm(actor_user_id=1, tournament_id=1, today=date(2026, 1, 1))
    assert session.rollbacks == 1


@pytest.mark.asyncio
async def test_same_bettor_with_renamed_snapshots_is_one_canonical_participant():
    tournament = SimpleNamespace(
        row_id=1, params_id=3, start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31), current_bank_kopecks=101,
        is_paid=False,
    )

    class Users:
        async def get_by_row_id(self, value):
            return SimpleNamespace(is_admin=True, is_approved=True)

    class Tournaments:
        async def get_by_id(self, *, row_id):
            return tournament

    class Params:
        requested = []

        async def get_by_id(self, *, row_id):
            self.requested.append(row_id)
            return SimpleNamespace(
                row_id=3, bet_param_id=1,
                percent_to_first=60, percent_to_second=25, percent_to_third=10,
            )

    class Bets:
        async def list_for_period(self, **kwargs):
            return [
                SimpleNamespace(
                    row_id=1, poker_id=1, date=date(2025, 3, 1), better_id=10,
                    better_name="Old Name", winner_id=10, loser_id=10, score=2,
                ),
                SimpleNamespace(
                    row_id=2, poker_id=1, date=date(2025, 3, 1), better_id=10,
                    better_name="New Name", winner_id=10, loser_id=10, score=3,
                ),
                SimpleNamespace(
                    row_id=3, poker_id=1, date=date(2025, 3, 1), better_id=20,
                    better_name="Other", winner_id=20, loser_id=20, score=4,
                ),
            ]

    params = Params()
    use_case = CloseBettingTournamentUseCase(
        session=_Session(), user_repository=Users(), tournament_repository=Tournaments(),
        tournament_param_repository=params, bet_repository=Bets(),
        **_dependencies(),
    )

    _, result = await use_case.preview(
        actor_user_id=1, tournament_id=1, today=date(2026, 1, 1)
    )

    assert [(item.user_id, item.player_name, item.score) for item in result.payouts] == [
        (10, "New Name", 5),
        (20, "Other", 4),
    ]
    assert result.place_user_ids == ((10,), (20,), ())
    assert result.place_names == (("New Name",), ("Other",), ())
    assert params.requested == [3]


@pytest.mark.asyncio
async def test_same_name_users_remain_two_tied_payout_recipients_and_persist_snapshots():
    tournament = SimpleNamespace(
        row_id=1, params_id=3, start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31), current_bank_kopecks=832_000,
        is_paid=False,
    )

    class Users:
        async def get_by_row_id(self, value):
            return SimpleNamespace(is_admin=True, is_approved=True)

    class Tournaments:
        finalized = None

        async def get_by_id(self, *, row_id):
            return tournament

        async def finalize_if_unpaid(self, **kwargs):
            self.finalized = kwargs
            tournament.is_paid = True
            return True

    class Params:
        async def get_by_id(self, *, row_id):
            assert row_id == 3
            return SimpleNamespace(
                row_id=3, bet_param_id=1,
                percent_to_first=50, percent_to_second=33, percent_to_third=17,
            )

    class Bets:
        async def list_for_period(self, **kwargs):
            return [
                SimpleNamespace(
                    row_id=1, poker_id=1, date=date(2025, 2, 1), better_id=10,
                    better_name="Alex", winner_id=10, loser_id=10, score=7,
                ),
                SimpleNamespace(
                    row_id=2, poker_id=1, date=date(2025, 2, 1), better_id=20,
                    better_name="Alex", winner_id=20, loser_id=20, score=7,
                ),
                SimpleNamespace(
                    row_id=3, poker_id=1, date=date(2025, 2, 1), better_id=30,
                    better_name="Chris", winner_id=30, loser_id=30, score=6,
                ),
                SimpleNamespace(
                    row_id=4, poker_id=1, date=date(2025, 2, 1), better_id=40,
                    better_name="Unpaid", winner_id=40, loser_id=40, score=1,
                ),
            ]

    class Results:
        inserted = None

        async def add_many(self, **kwargs):
            self.inserted = kwargs

    class RoleResults:
        inserted = None

        async def add_many(self, **kwargs):
            self.inserted = kwargs

    tournaments = Tournaments()
    session = _Session()
    results = Results()
    role_results = RoleResults()
    use_case = CloseBettingTournamentUseCase(
        session=session, user_repository=Users(), tournament_repository=tournaments,
        tournament_param_repository=Params(), bet_repository=Bets(),
        tournament_result_repository=results,
        tournament_role_result_repository=role_results,
        poker_data_repository=_PokerData(),
    )

    _, result = await use_case.confirm(
        actor_user_id=1, tournament_id=1, today=date(2026, 1, 1)
    )

    assert [(item.user_id, item.amount_kopecks) for item in result.payouts] == [
        (10, 345_280), (20, 345_280), (30, 141_440),
    ]
    assert result.place_user_ids == ((10, 20), (10, 20), (30,))
    assert result.place_names == (("Alex", "Alex"), ("Alex", "Alex"), ("Chris",))
    assert tournaments.finalized == {
        "tournament_id": 1,
        "first_place_name": "Alex, Alex",
        "second_place_name": "Alex, Alex",
        "third_place_name": "Chris",
    }
    assert result.total_payout_kopecks == 832_000
    assert result.remainder_kopecks == 0
    assert tournament.current_bank_kopecks == 832_000
    assert session.commits == 1
    assert results.inserted == {"tournament_id": 1, "payouts": result.payouts}
    assert role_results.inserted == {"tournament_id": 1, "snapshots": result.role_scores}


@pytest.mark.asyncio
async def test_result_insert_failure_rolls_back_finalization_transaction():
    tournament = SimpleNamespace(
        row_id=1, params_id=3, start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31), current_bank_kopecks=100, is_paid=False,
    )

    class Users:
        async def get_by_row_id(self, value):
            return SimpleNamespace(is_admin=True, is_approved=True)

    class Tournaments:
        async def get_by_id(self, **kwargs):
            return tournament

        async def finalize_if_unpaid(self, **kwargs):
            tournament.is_paid = True
            return True

    class Params:
        async def get_by_id(self, **kwargs):
            return SimpleNamespace(percent_to_first=50, percent_to_second=30, percent_to_third=20)

    class Bets:
        async def list_for_period(self, **kwargs):
            return [SimpleNamespace(row_id=1, poker_id=1, date=date(2025, 1, 1), better_id=2, better_name="A", winner_id=2, loser_id=2, score=1)]

    class Results:
        async def add_many(self, **kwargs):
            raise RuntimeError("insert failed")

    session = _Session()
    use_case = CloseBettingTournamentUseCase(
        session=session, user_repository=Users(), tournament_repository=Tournaments(),
        tournament_param_repository=Params(), bet_repository=Bets(),
        tournament_result_repository=Results(),
        tournament_role_result_repository=_NoOpResults(),
        poker_data_repository=_PokerData(),
    )
    with pytest.raises(RuntimeError, match="insert failed"):
        await use_case.confirm(actor_user_id=1, tournament_id=1, today=date(2026, 1, 1))
    assert session.commits == 0
    assert session.rollbacks == 1


@pytest.mark.asyncio
async def test_non_admin_is_rejected_before_tournament_access():
    class Users:
        async def get_by_row_id(self, value):
            return SimpleNamespace(is_admin=False, is_approved=True)

    class Never:
        async def list_eligible_for_finalization(self, **kwargs):
            raise AssertionError

    use_case = CloseBettingTournamentUseCase(
        session=_Session(),
        user_repository=Users(),
        tournament_repository=Never(),
        tournament_param_repository=Never(),
        bet_repository=Never(),
        **_dependencies(),
    )
    with pytest.raises(PermissionError):
        await use_case.list_eligible(actor_user_id=1, today=date(2026, 1, 1))


@pytest.mark.asyncio
async def test_only_ended_unfinalized_tournaments_are_eligible(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'eligible.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all, tables=[BetTournament.__table__])
    async with sessions() as session:
        session.add_all([
            BetTournament(params_id=1, tournament_type="regular", start_date=date(2025, 1, 1), end_date=date(2025, 4, 30), current_bank_kopecks=1, is_paid=False),
            BetTournament(params_id=1, tournament_type="regular", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), current_bank_kopecks=1, is_paid=False),
            BetTournament(params_id=1, tournament_type="year", start_date=date(2025, 1, 1), end_date=date(2025, 12, 31), current_bank_kopecks=1, is_paid=True),
        ])
        await session.commit()
        eligible = await BetTournamentRepository(session).list_eligible_for_finalization(today=date(2026, 1, 1))
        assert [(item.tournament_type, item.is_paid) for item in eligible] == [("regular", False)]
    await engine.dispose()


async def _real_store(tmp_path, filename):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / filename}",
        connect_args={"timeout": 10},
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        admin = User(telegram_id=1001, name="Admin", is_admin=True, is_approved=True)
        bettor = User(telegram_id=1002, name="Bettor", is_approved=True)
        winner = User(telegram_id=1003, name="Winner", is_approved=True)
        loser = User(telegram_id=1004, name="Loser", is_approved=True)
        poker_params = PokerParam(
            buyin_size_chips=200, buyin_size_kopecks=20_000,
            bb_size_chips=10, max_buyins=3,
        )
        bet_params = BetParam(
            small_size_kopecks=10_000, small_score=1, small_score_combo=2,
            big_size_kopecks=20_000, big_score=2, big_score_combo=4,
        )
        session.add_all([admin, bettor, winner, loser, poker_params, bet_params])
        await session.flush()
        tournament_params = BetTournamentParam(
            tournament_type="regular", bet_param_id=bet_params.row_id,
            percent_to_first=50, percent_to_second=33, percent_to_third=17,
            duration_months=4,
        )
        poker = Poker(params_id=poker_params.row_id, date=date(2025, 1, 5))
        session.add_all([tournament_params, poker])
        await session.flush()
        tournament = BetTournament(
            params_id=tournament_params.row_id, tournament_type="regular",
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 31),
            current_bank_kopecks=10_000, is_paid=False,
        )
        session.add_all([
            tournament,
            PokerData(
                poker_id=poker.row_id, date=poker.date, player_id=winner.row_id,
                player_name=winner.name, money_kopecks=10_000,
            ),
            PokerData(
                poker_id=poker.row_id, date=poker.date, player_id=bettor.row_id,
                player_name=bettor.name, money_kopecks=-10_000,
            ),
            Bet(
                poker_id=poker.row_id, params_id=bet_params.row_id, date=poker.date,
                better_id=bettor.row_id, better_name=bettor.name,
                amount_kopecks=10_000, winner_id=winner.row_id,
                winner_name=winner.name, loser_id=bettor.row_id,
                loser_name=bettor.name, score=4, is_paid=True,
            ),
        ])
        await session.commit()
        return engine, sessions, admin.row_id, tournament.row_id


def _real_use_case(session, *, role_repository=None):
    return CloseBettingTournamentUseCase(
        session=session,
        user_repository=UserRepository(session),
        tournament_repository=BetTournamentRepository(session),
        tournament_param_repository=BetTournamentParamRepository(session),
        bet_repository=BetRepository(session),
        tournament_result_repository=BetTournamentResultRepository(session),
        tournament_role_result_repository=(
            role_repository or BetTournamentRoleResultRepository(session)
        ),
        poker_data_repository=PokerDataRepository(session),
    )


@pytest.mark.asyncio
async def test_real_sqlite_concurrent_confirmation_has_one_complete_winner(tmp_path):
    engine, sessions, admin_id, tournament_id = await _real_store(
        tmp_path, "concurrent-finalization.db"
    )

    async def confirm():
        async with sessions() as session:
            return await _real_use_case(session).confirm(
                actor_user_id=admin_id,
                tournament_id=tournament_id,
                today=date(2026, 1, 1),
            )

    outcomes = await asyncio.gather(confirm(), confirm(), return_exceptions=True)

    assert sum(not isinstance(item, Exception) for item in outcomes) == 1
    assert sum(isinstance(item, ValueError) for item in outcomes) == 1
    async with sessions() as session:
        tournament = await session.get(BetTournament, tournament_id)
        assert tournament is not None and tournament.is_paid is True
        assert await session.scalar(
            select(func.count()).select_from(BetTournamentResult)
        ) == 1
        assert await session.scalar(
            select(func.count()).select_from(BetTournamentRoleResult)
        ) == 2
    await engine.dispose()


@pytest.mark.asyncio
async def test_real_constraint_failure_rolls_back_all_finalization_writes(tmp_path):
    engine, sessions, admin_id, tournament_id = await _real_store(
        tmp_path, "rollback-finalization.db"
    )

    class InvalidRoleRepository:
        def __init__(self, session):
            self.session = session

        async def add_many(self, *, tournament_id, snapshots):
            self.session.add(BetTournamentRoleResult(
                tournament_id=tournament_id,
                bettor_user_id=snapshots[0].bettor_user_id,
                target_user_id=snapshots[0].target_user_id,
                role=snapshots[0].role,
                score_units=0,
            ))
            await self.session.flush()

    async with sessions() as session:
        with pytest.raises(Exception, match="score_units"):
            await _real_use_case(
                session, role_repository=InvalidRoleRepository(session)
            ).confirm(
                actor_user_id=admin_id,
                tournament_id=tournament_id,
                today=date(2026, 1, 1),
            )

    async with sessions() as session:
        tournament = await session.get(BetTournament, tournament_id)
        assert tournament is not None and tournament.is_paid is False
        assert await session.scalar(
            select(func.count()).select_from(BetTournamentResult)
        ) == 0
        assert await session.scalar(
            select(func.count()).select_from(BetTournamentRoleResult)
        ) == 0
        await _real_use_case(session).confirm(
            actor_user_id=admin_id,
            tournament_id=tournament_id,
            today=date(2026, 1, 1),
        )

    async with sessions() as session:
        assert await session.scalar(
            select(func.count()).select_from(BetTournamentResult)
        ) == 1
        assert await session.scalar(
            select(func.count()).select_from(BetTournamentRoleResult)
        ) == 2
    await engine.dispose()


@pytest.mark.asyncio
async def test_real_finalized_role_money_ignores_all_mutable_legacy_inputs(tmp_path):
    engine, sessions, admin_id, tournament_id = await _real_store(
        tmp_path, "immutable-role-money.db"
    )
    async with sessions() as session:
        await _real_use_case(session).confirm(
            actor_user_id=admin_id,
            tournament_id=tournament_id,
            today=date(2026, 1, 1),
        )

    async def report():
        async with sessions() as session:
            return await StatUseCases(
                bet_repository=BetRepository(session),
                poker_data_repository=PokerDataRepository(session),
                bet_tournament_repository=BetTournamentRepository(session),
                bet_tournament_param_repository=BetTournamentParamRepository(session),
                bet_tournament_result_repository=BetTournamentResultRepository(session),
                bet_tournament_role_result_repository=BetTournamentRoleResultRepository(session),
                poker_repository=PokerRepository(session),
            ).get_betting_stat(indicators=[SimpleNamespace(row_id=1, pic="❌➡️💲")])

    reports = [await report()]
    async with sessions() as session:
        bet = await session.scalar(select(Bet))
        bet.score = 400
        await session.commit()
    reports.append(await report())
    async with sessions() as session:
        bet = await session.scalar(select(Bet))
        bet.winner_id, bet.loser_id = bet.loser_id, bet.winner_id
        bet.winner_name, bet.loser_name = "Changed loser", "Changed winner"
        await session.commit()
    reports.append(await report())
    async with sessions() as session:
        bettor = await session.scalar(select(User).where(User.telegram_id == 1002))
        bettor.name = "Renamed canonical user"
        await session.commit()
    reports.append(await report())
    async with sessions() as session:
        params = await session.scalar(select(BetTournamentParam))
        params.percent_to_first = 1
        params.percent_to_second = 1
        params.percent_to_third = 1
        await session.commit()
    reports.append(await report())
    async with sessions() as session:
        tournament = await session.get(BetTournament, tournament_id)
        tournament.current_bank_kopecks = 999_999
        await session.commit()
    reports.append(await report())

    assert all("Bettor | 25.0" in value for value in reports)
    await engine.dispose()
