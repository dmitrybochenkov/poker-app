import json
from datetime import date
from types import SimpleNamespace

import pytest

from app.application.use_cases.poker.betting_tournament_periods import (
    BettingTournamentPeriod,
    default_betting_tournament_period_ids,
    list_betting_tournament_periods,
)
from app.application.use_cases.poker.stat import StatUseCases
from app.bot.shared.texts.texts import Text
from app.bot.telegram import keyboards as tg
from app.bot.vk import keyboards as vk


def _tournament(row_id, tournament_type, start_date, end_date):
    return SimpleNamespace(
        row_id=row_id,
        tournament_type=tournament_type,
        start_date=start_date,
        end_date=end_date,
    )


def _tg_rows(markup):
    return [
        [(button.text, button.callback_data) for button in row]
        for row in markup.inline_keyboard
    ]


def _vk_rows(keyboard):
    return [
        [
            (button["action"]["label"], button["action"].get("payload"))
            for button in row
        ]
        for row in json.loads(keyboard)["buttons"]
    ]


def test_periods_have_date_specific_identity_labels_and_shared_chronology():
    periods = list_betting_tournament_periods(
        [
            _tournament(1, "regular", date(2025, 1, 1), date(2025, 4, 30)),
            _tournament(2, "year", date(2025, 1, 1), date(2025, 12, 31)),
            _tournament(3, "regular", date(2026, 1, 1), date(2026, 4, 30)),
            _tournament(4, "year", date(2026, 1, 1), date(2026, 12, 31)),
            _tournament(5, "regular", date(2026, 5, 1), date(2026, 8, 31)),
        ]
    )

    assert [period.label for period in periods] == [
        "Регулярный май – авг",
        "Регулярный янв – апр",
        "Годовой 2026",
        "Регулярный янв – апр",
        "Годовой 2025",
    ]
    assert periods[1].selection_id != periods[3].selection_id
    assert BettingTournamentPeriod.from_selection_id(periods[1].selection_id) == periods[1]


def test_default_selects_all_periods_active_on_current_date_then_latest_fallback():
    periods = list_betting_tournament_periods(
        [
            _tournament(1, "regular", date(2026, 1, 1), date(2026, 4, 30)),
            _tournament(2, "year", date(2026, 1, 1), date(2026, 12, 31)),
        ]
    )

    assert default_betting_tournament_period_ids(
        periods, today=date(2026, 3, 10)
    ) == {period.selection_id for period in periods}
    assert default_betting_tournament_period_ids(
        periods, today=date(2027, 1, 1)
    ) == {periods[0].selection_id}


def test_tg_vk_tournament_filter_keyboards_are_equivalent_and_page_at_five():
    periods = [
        BettingTournamentPeriod(
            tournament_type="regular",
            start_date=date(2026, month, 1),
            end_date=date(2026, month, 28),
        )
        for month in range(6, 0, -1)
    ]
    selected = {periods[0].selection_id, periods[5].selection_id}

    tg_rows = _tg_rows(
        tg.betting_tournament_periods_keyboard(
            periods=periods, selected_period_ids=selected, page=0
        )
    )
    vk_rows = _vk_rows(
        vk.betting_tournament_periods_keyboard(
            periods=periods, selected_period_ids=selected, page=0
        )
    )

    assert [row[0][0] for row in tg_rows[:2]] == [
        "💰 Открытый регулярный турнир",
        "🎄💰 Открытый годовой турнир",
    ]
    assert [row[0][0] for row in vk_rows[:2]] == [
        "💰 Открытый регулярный турнир",
        "🎄💰 Открытый годовой турнир",
    ]
    assert len(tg_rows[2:7]) == 5
    assert len(vk_rows[2:7]) == 5
    assert [row[0][0] for row in tg_rows[2:7]] == [row[0][0] for row in vk_rows[2:7]]
    assert tg_rows[0][0][1] == "betstatopen:regular"
    assert vk_rows[0][0][1] == {"action": "betstat_open", "mode": "regular"}
    assert tg_rows[-2][0][1] == "betstattour_page:1"
    assert vk_rows[-2][0][1] == {"action": "betstattour_page", "page": 1}

    tg_second_page = _tg_rows(
        tg.betting_tournament_periods_keyboard(
            periods=periods, selected_period_ids=selected, page=1
        )
    )
    vk_second_page = _vk_rows(
        vk.betting_tournament_periods_keyboard(
            periods=periods, selected_period_ids=selected, page=1
        )
    )
    assert tg_second_page[2][0][0].startswith("✔ ")
    assert vk_second_page[2][0][0].startswith("✔ ")


def test_betting_statistics_instruction_mentions_tournaments_not_years():
    assert (
        Text.user.STAT_CHOOSE_BETTING_TOURNAMENT.value
        == "Выбери турнир(ы) для статистики и нажми 'Готово'."
    )


def test_betting_reply_menu_drops_current_tournaments_on_both_platforms():
    tg_labels = [button.text for row in tg.betting_keyboard.keyboard for button in row]
    vk_labels = [
        button["action"]["label"]
        for row in json.loads(vk.betting_keyboard)["buttons"]
        for button in row
    ]

    assert "🎰 Текущие турниры" not in tg_labels
    assert "🎰 Текущие турниры" not in vk_labels
    assert "🍀 Статистика ставок" in tg_labels
    assert "🍀 Статистика ставок" in vk_labels


class _ListRepository:
    def __init__(self, rows):
        self.rows = rows

    async def list_all(self):
        return self.rows

    async def list_active(self):
        return self.rows


@pytest.mark.asyncio
async def test_overlapping_selected_periods_do_not_count_the_same_bet_twice():
    bet = SimpleNamespace(
        date=date(2026, 3, 10),
        better_name="Alice",
        better_id=7,
        score=11,
        is_paid=True,
    )
    tournaments = [
        _tournament(1, "regular", date(2026, 1, 1), date(2026, 4, 30)),
        _tournament(2, "year", date(2026, 1, 1), date(2026, 12, 31)),
    ]
    use_case = StatUseCases(
        bet_repository=_ListRepository([bet]),
        bet_tournament_repository=_ListRepository(tournaments),
    )
    periods = list_betting_tournament_periods(tournaments)

    report = await use_case.get_betting_stat(
        indicators=[SimpleNamespace(row_id=1, pic="💯")],
        mode="all",
        tournament_periods=periods,
    )

    assert "11" in report
    assert "22" not in report
