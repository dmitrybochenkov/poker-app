from datetime import date
from types import SimpleNamespace

import pytest

from app.application.use_cases.poker.stat import StatUseCases


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    async def list_all(self):
        return self.rows

    async def list_active(self):
        return self.rows


def _tournament(*, bank_kopecks, params_id, first, second, third):
    return SimpleNamespace(
        row_id=1,
        tournament_type="regular",
        params_id=params_id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 4, 30),
        current_bank_kopecks=bank_kopecks,
        first_place_name=first,
        second_place_name=second,
        third_place_name=third,
        is_paid=True,
    )


def _params(*, row_id, bet_param_id, percents):
    return SimpleNamespace(
        row_id=row_id,
        tournament_type="regular",
        bet_param_id=bet_param_id,
        percent_to_first=percents[0],
        percent_to_second=percents[1],
        percent_to_third=percents[2],
    )


def _bet(name, score):
    player_id = ord(name) - ord("A") + 1
    return SimpleNamespace(
        row_id=player_id,
        date=date(2026, 3, 1),
        better_name=name,
        better_id=player_id,
        score=score,
        is_paid=True,
        amount_kopecks=10_000,
    )


def _result(*, tournament_id, user_id, position, payout, name, score):
    return SimpleNamespace(
        tournament_id=tournament_id, user_id=user_id, position=position,
        payout_kopecks=payout, name_snapshot=name, score=score,
    )


@pytest.mark.asyncio
async def test_historical_prizes_use_tournament_params_and_authoritative_tie_math():
    tournament = _tournament(
        bank_kopecks=832_000,
        params_id=3,
        first="A, B",
        second="A, B",
        third="C",
    )
    use_case = StatUseCases(
        bet_repository=_Rows([_bet("A", 7), _bet("B", 7), _bet("C", 6)]),
        bet_tournament_repository=_Rows([tournament]),
        bet_tournament_param_repository=_Rows(
            [
                _params(row_id=1, bet_param_id=1, percents=(60, 25, 10)),
                _params(row_id=3, bet_param_id=1, percents=(50, 33, 17)),
            ]
        ),
    )

    report = await use_case.get_betting_stat(
        indicators=[
            SimpleNamespace(row_id=1, pic="💯"),
            SimpleNamespace(row_id=2, pic="+💲"),
        ]
    )

    assert [line.split() for line in report.splitlines()[2:]] == [
        ["A", "|", "7", "|", "3452.8"],
        ["B", "|", "7", "|", "3452.8"],
        ["C", "|", "6", "|", "1414.4"],
    ]


@pytest.mark.asyncio
async def test_historical_three_way_tie_preserves_kopeck_floor_remainder():
    tournament = _tournament(
        bank_kopecks=784_000,
        params_id=3,
        first="A, B, C",
        second="A, B, C",
        third="A, B, C",
    )
    use_case = StatUseCases(
        bet_repository=_Rows([_bet("A", 2), _bet("B", 2), _bet("C", 2)]),
        bet_tournament_repository=_Rows([tournament]),
        bet_tournament_param_repository=_Rows(
            [
                _params(row_id=1, bet_param_id=1, percents=(60, 25, 10)),
                _params(row_id=3, bet_param_id=1, percents=(50, 33, 17)),
            ]
        ),
    )

    report = await use_case.get_betting_stat(
        indicators=[SimpleNamespace(row_id=1, pic="+💲")]
    )

    assert "A | 2613.33" in report
    assert "B | 2613.33" in report
    assert "C | 2613.33" in report
    assert "2613.34" not in report


def test_open_projection_uses_integer_kopeck_floor_and_associated_params():
    tournament = _tournament(
        bank_kopecks=101,
        params_id=3,
        first="",
        second="",
        third="",
    )
    use_case = StatUseCases(bet_repository=_Rows([]), bet_tournament_param_repository=_Rows([]))
    use_case._tournament_percents_cache = {
        1: (50, 30, 20),
        3: (60, 25, 10),
    }

    assert use_case._format_current_tournament_money_block(tournament=tournament) == (
        "💰: 1.01 ₽\n"
        "🥇: 0.60 ₽\n"
        "🥈: 0.25 ₽\n"
        "🥉: 0.10 ₽"
    )


@pytest.mark.asyncio
async def test_finalized_prizes_and_titles_use_immutable_canonical_results():
    tournament = _tournament(
        bank_kopecks=999_999, params_id=3,
        first="Wrong Legacy Name", second="", third="",
    )
    tournament.row_id = 41
    bets = [
        SimpleNamespace(
            row_id=1, date=date(2026, 3, 1), better_name="Current Changed Name",
            better_id=10, score=-999, is_paid=True, amount_kopecks=10_000,
            poker_id=1, winner_id=20, loser_id=30,
        )
    ]
    results = [
        _result(tournament_id=41, user_id=10, position=1, payout=123_456, name="Historical", score=7)
    ]
    use_case = StatUseCases(
        bet_repository=_Rows(bets),
        bet_tournament_repository=_Rows([tournament]),
        bet_tournament_param_repository=_Rows([
            _params(row_id=3, bet_param_id=1, percents=(1, 1, 1)),
        ]),
        bet_tournament_result_repository=_Rows(results),
    )
    report = await use_case.get_betting_stat(
        indicators=[SimpleNamespace(row_id=1, pic="+💲"), SimpleNamespace(row_id=2, pic="🏆")]
    )
    assert "Current Changed Name | 1234.56 | 1" in report
    assert "9999.99" not in report
