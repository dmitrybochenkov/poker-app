import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.application.use_cases.poker.betting_tournament_periods import (
    BettingTournamentPeriod,
    betting_tournament_statistics_mode,
    list_betting_tournament_periods,
    toggle_betting_tournament_selection,
)
from app.application.use_cases.poker.stat import StatUseCases
from app.bot.shared.texts.texts import Text
from app.bot.telegram import keyboards as tg
from app.bot.telegram.handlers.user import betting_stats as tg_betting_stats
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


def test_periods_have_date_specific_identity_status_labels_and_shared_chronology():
    periods = list_betting_tournament_periods(
        [
            _tournament(1, "regular", date(2025, 1, 1), date(2025, 4, 30)),
            _tournament(2, "year", date(2025, 1, 1), date(2025, 12, 31)),
            _tournament(3, "regular", date(2026, 1, 1), date(2026, 4, 30)),
            _tournament(4, "year", date(2026, 1, 1), date(2026, 12, 31)),
            _tournament(5, "regular", date(2026, 5, 1), date(2026, 8, 31)),
        ]
    )

    assert [period.display_label(today=date(2026, 6, 1)) for period in periods] == [
        "🎄💰 Годовой 2026",
        "💰 Регулярный май – авг 2026",
        "🏁💰 Регулярный янв – апр 2026",
        "🏁🎄💰 Годовой 2025",
        "🏁💰 Регулярный янв – апр 2025",
    ]
    assert periods[1].selection_id != periods[3].selection_id
    assert BettingTournamentPeriod.from_selection_id(periods[1].selection_id) == periods[1]


def test_open_and_closed_selection_modes_are_mutually_exclusive():
    periods = list_betting_tournament_periods(
        [
            _tournament(1, "regular", date(2026, 1, 1), date(2026, 4, 30)),
            _tournament(2, "year", date(2026, 1, 1), date(2026, 12, 31)),
        ]
    )

    regular = next(period for period in periods if period.tournament_type == "regular")
    annual = next(period for period in periods if period.tournament_type == "year")
    today = date(2026, 3, 10)
    selected = toggle_betting_tournament_selection(
        periods=periods,
        selected_period_ids=set(),
        toggled_period_id=regular.selection_id,
        today=today,
    )
    assert selected == {regular.selection_id}
    selected = toggle_betting_tournament_selection(
        periods=periods,
        selected_period_ids=selected,
        toggled_period_id=annual.selection_id,
        today=today,
    )
    assert selected == {annual.selection_id}
    assert betting_tournament_statistics_mode(periods, selected, today=today) == "year"


def test_open_closed_transition_and_closed_multi_select_rules():
    periods = list_betting_tournament_periods(
        [
            _tournament(1, "regular", date(2025, 1, 1), date(2025, 4, 30)),
            _tournament(2, "year", date(2025, 1, 1), date(2025, 12, 31)),
            _tournament(3, "year", date(2026, 1, 1), date(2026, 12, 31)),
        ]
    )
    open_period, closed_annual, closed_regular = periods
    today = date(2026, 6, 1)

    selected = toggle_betting_tournament_selection(
        periods, {open_period.selection_id}, closed_annual.selection_id, today=today
    )
    assert selected == {closed_annual.selection_id}
    selected = toggle_betting_tournament_selection(
        periods, selected, closed_regular.selection_id, today=today
    )
    assert selected == {closed_annual.selection_id, closed_regular.selection_id}
    selected = toggle_betting_tournament_selection(
        periods, selected, closed_annual.selection_id, today=today
    )
    assert selected == {closed_regular.selection_id}
    assert betting_tournament_statistics_mode(periods, selected, today=today) == "all"
    selected = toggle_betting_tournament_selection(
        periods, selected, open_period.selection_id, today=today
    )
    assert selected == {open_period.selection_id}


def test_no_selection_has_no_statistics_mode():
    assert betting_tournament_statistics_mode([], set(), today=date(2026, 6, 1)) is None


def test_tg_vk_tournament_filter_keyboards_are_equivalent_and_page_at_five():
    periods = [
        BettingTournamentPeriod(
            tournament_type="regular",
            start_date=date(2026, month, 1),
            end_date=date(2026, month, 28),
        )
        for month in range(6, 0, -1)
    ]
    selected = {periods[1].selection_id, periods[5].selection_id}
    today = date(2026, 7, 1)

    tg_rows = _tg_rows(
        tg.betting_tournament_periods_keyboard(
            periods=periods, selected_period_ids=selected, page=0, today=today
        )
    )
    vk_rows = _vk_rows(
        vk.betting_tournament_periods_keyboard(
            periods=periods, selected_period_ids=selected, page=0, today=today
        )
    )

    assert len(tg_rows[:5]) == 5
    assert len(vk_rows[:5]) == 5
    assert [row[0][0] for row in tg_rows[:5]] == [row[0][0] for row in vk_rows[:5]]
    assert tg_rows[0][0][1].startswith("betstattour_toggle:")
    assert vk_rows[0][0][1]["action"] == "betstattour_toggle"
    assert tg_rows[-2][0][1] == "betstattour_page:1"
    assert vk_rows[-2][0][1] == {"action": "betstattour_page", "page": 1}

    tg_second_page = _tg_rows(
        tg.betting_tournament_periods_keyboard(
            periods=periods, selected_period_ids=selected, page=1, today=today
        )
    )
    vk_second_page = _vk_rows(
        vk.betting_tournament_periods_keyboard(
            periods=periods, selected_period_ids=selected, page=1, today=today
        )
    )
    assert tg_second_page[0][0][0].startswith("✅ ")
    assert vk_second_page[0][0][0].startswith("✅ ")
    assert tg_rows[-1][0][1] == "betstattour_back"
    assert vk_rows[-1][0][1] == {"action": "betstattour_back"}


def test_betting_statistics_instruction_mentions_tournaments_not_years():
    assert (
        Text.user.STAT_CHOOSE_BETTING_TOURNAMENT.value
        == "Выбери один открытый или любое количество закрытых турниров и нажми «Готово»."
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


class _SessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, traceback):
        return False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tournament", "today", "expected_mode", "indicator_scope"),
    [
        (
            _tournament(1, "year", date(2026, 1, 1), date(2026, 12, 31)),
            date(2026, 6, 1),
            "year",
            "only",
        ),
        (
            _tournament(2, "regular", date(2025, 1, 1), date(2025, 4, 30)),
            date(2026, 6, 1),
            "all",
            "no",
        ),
    ],
)
async def test_telegram_done_uses_open_or_historical_indicator_mode(
    monkeypatch, tournament, today, expected_mode, indicator_scope
):
    period = list_betting_tournament_periods([tournament])[0]
    indicator = SimpleNamespace(
        row_id=1,
        for_current_tournaments=indicator_scope,
        pic="💯",
        description="Баллы",
    )
    state = SimpleNamespace(
        get_data=AsyncMock(return_value={"betstat_period_ids": [period.selection_id]}),
        update_data=AsyncMock(),
    )
    message = SimpleNamespace(edit_text=AsyncMock())
    callback = SimpleNamespace(message=message, answer=AsyncMock())
    monkeypatch.setattr(tg_betting_stats, "SessionFactory", _SessionContext)
    monkeypatch.setattr(
        tg_betting_stats,
        "BetTournamentRepository",
        lambda session: SimpleNamespace(list_active=AsyncMock(return_value=[tournament])),
    )
    monkeypatch.setattr(
        tg_betting_stats,
        "StatIndicatorRepository",
        lambda session: SimpleNamespace(list_by_type=AsyncMock(return_value=[indicator])),
    )
    monkeypatch.setattr(
        tg_betting_stats,
        "_ensure_approved_telegram_callback_user",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        tg_betting_stats,
        "betting_tournament_statistics_mode",
        lambda periods, selected: expected_mode,
    )

    await tg_betting_stats.betting_tournament_done(callback, state)

    state.update_data.assert_awaited_with(
        betstat_mode=expected_mode, betstat_selected_ids=[]
    )
    message.edit_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_telegram_done_without_selection_stays_on_selector(monkeypatch):
    state = SimpleNamespace(
        get_data=AsyncMock(return_value={"betstat_period_ids": []}),
        update_data=AsyncMock(),
    )
    message = SimpleNamespace(edit_text=AsyncMock())
    callback = SimpleNamespace(message=message, answer=AsyncMock())
    monkeypatch.setattr(tg_betting_stats, "SessionFactory", _SessionContext)
    monkeypatch.setattr(
        tg_betting_stats,
        "BetTournamentRepository",
        lambda session: SimpleNamespace(list_active=AsyncMock(return_value=[])),
    )
    monkeypatch.setattr(
        tg_betting_stats,
        "_ensure_approved_telegram_callback_user",
        AsyncMock(return_value=True),
    )

    await tg_betting_stats.betting_tournament_done(callback, state)

    message.edit_text.assert_not_awaited()
    callback.answer.assert_awaited_once_with(
        Text.user.BETTING_TOURNAMENT_NOT_SELECTED.value, show_alert=True
    )
