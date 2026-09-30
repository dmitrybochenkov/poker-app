from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.use_cases.poker.close_betting_tournament import (
    CloseBettingTournamentUseCase,
    calculate_payouts,
)
from app.db.base import Base
from app.db.models.bet_tournament import BetTournament
from app.db.repositories.bet_tournament_repository import BetTournamentRepository


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


class _Session:
    commits = 0
    rollbacks = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


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
                SimpleNamespace(row_id=1, date=date(2025, 4, 1), better_id=1, better_name="A", score=7),
                SimpleNamespace(row_id=2, date=date(2025, 4, 2), better_id=2, better_name="B", score=7),
                SimpleNamespace(row_id=3, date=date(2025, 4, 3), better_id=3, better_name="C", score=6),
            ]

    session = _Session()
    tournaments = Tournaments()
    use_case = CloseBettingTournamentUseCase(
        session=session,
        user_repository=Users(),
        tournament_repository=tournaments,
        tournament_param_repository=Params(),
        bet_repository=Bets(),
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
                    row_id=1, date=date(2025, 3, 1), better_id=10,
                    better_name="Old Name", score=2,
                ),
                SimpleNamespace(
                    row_id=2, date=date(2025, 3, 1), better_id=10,
                    better_name="New Name", score=3,
                ),
                SimpleNamespace(
                    row_id=3, date=date(2025, 3, 1), better_id=20,
                    better_name="Other", score=4,
                ),
            ]

    params = Params()
    use_case = CloseBettingTournamentUseCase(
        session=_Session(), user_repository=Users(), tournament_repository=Tournaments(),
        tournament_param_repository=params, bet_repository=Bets(),
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
                    row_id=1, date=date(2025, 2, 1), better_id=10,
                    better_name="Alex", score=7,
                ),
                SimpleNamespace(
                    row_id=2, date=date(2025, 2, 1), better_id=20,
                    better_name="Alex", score=7,
                ),
                SimpleNamespace(
                    row_id=3, date=date(2025, 2, 1), better_id=30,
                    better_name="Chris", score=6,
                ),
                SimpleNamespace(
                    row_id=4, date=date(2025, 2, 1), better_id=40,
                    better_name="Unpaid", score=1,
                ),
            ]

    tournaments = Tournaments()
    session = _Session()
    use_case = CloseBettingTournamentUseCase(
        session=session, user_repository=Users(), tournament_repository=tournaments,
        tournament_param_repository=Params(), bet_repository=Bets(),
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
