from datetime import date
from types import SimpleNamespace

import pytest

from app.application.use_cases.poker.stat import StatUseCases


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    async def list_all(self):
        return list(self.rows)


class _Achievements:
    def __init__(self, rows):
        self.rows = rows

    async def list_by_type(self, *, achievement_type):
        assert achievement_type == "poker"
        return list(self.rows)


def _row(*, row_id, poker_id, day, player_id, name, money, buyins=1):
    return SimpleNamespace(
        row_id=row_id,
        poker_id=poker_id,
        date=day,
        player_id=player_id,
        player_name=name,
        money_kopecks=money,
        buyins=buyins,
    )


def _indicator(row_id, pic):
    return SimpleNamespace(row_id=row_id, pic=pic)


def _data_lines(report):
    return [
        [cell.strip() for cell in line.split("|")]
        for line in report.splitlines()[2:]
    ]


@pytest.mark.asyncio
async def test_unique_name_statistics_retain_existing_numeric_results():
    rows = [
        _row(row_id=1, poker_id=1, day=date(2026, 1, 1), player_id=10, name="Alice", money=10_000, buyins=1),
        _row(row_id=2, poker_id=1, day=date(2026, 1, 1), player_id=20, name="Bob", money=-10_000, buyins=2),
        _row(row_id=3, poker_id=2, day=date(2026, 1, 2), player_id=10, name="Alice", money=-5_000, buyins=2),
        _row(row_id=4, poker_id=2, day=date(2026, 1, 2), player_id=20, name="Bob", money=5_000, buyins=1),
    ]
    indicators = [
        _indicator(1, "🎲"),
        _indicator(2, "💍"),
        _indicator(3, "❌"),
        _indicator(4, "💲"),
    ]

    report = await StatUseCases(
        bet_repository=_Rows([]),
        poker_data_repository=_Rows(rows),
    ).get_poker_stat(indicators=indicators, sort_pic="🎲")

    assert sorted(_data_lines(report)) == [
        ["Alice", "2", "1", "1", "50"],
        ["Bob", "2", "1", "1", "-50"],
    ]


@pytest.mark.asyncio
async def test_poker_statistics_use_player_ids_across_renames_duplicate_names_and_ties():
    original_names = [
        "Old Name", "Alex", "Third", "New Name", "Alex", "Third",
        "New Name", "Alex", "Third", "New Name", "Alex", "Third",
    ]
    rows = [
        _row(row_id=1, poker_id=1, day=date(2026, 1, 1), player_id=1, name="Old Name", money=10_000),
        _row(row_id=2, poker_id=1, day=date(2026, 1, 1), player_id=2, name="Alex", money=-10_000),
        _row(row_id=3, poker_id=1, day=date(2026, 1, 1), player_id=3, name="Third", money=0),
        _row(row_id=4, poker_id=2, day=date(2026, 1, 2), player_id=1, name="New Name", money=10_000),
        _row(row_id=5, poker_id=2, day=date(2026, 1, 2), player_id=2, name="Alex", money=-10_000),
        _row(row_id=6, poker_id=2, day=date(2026, 1, 2), player_id=3, name="Third", money=0),
        _row(row_id=7, poker_id=3, day=date(2026, 1, 3), player_id=1, name="New Name", money=5_000),
        _row(row_id=8, poker_id=3, day=date(2026, 1, 3), player_id=2, name="Alex", money=5_000),
        _row(row_id=9, poker_id=3, day=date(2026, 1, 3), player_id=3, name="Third", money=-10_000),
        _row(row_id=10, poker_id=4, day=date(2026, 1, 4), player_id=1, name="New Name", money=-5_000),
        _row(row_id=11, poker_id=4, day=date(2026, 1, 4), player_id=2, name="Alex", money=-5_000),
        _row(row_id=12, poker_id=4, day=date(2026, 1, 4), player_id=3, name="Third", money=10_000),
    ]
    indicators = [
        _indicator(1, "🎲"),
        _indicator(2, "💍"),
        _indicator(3, "❌"),
        _indicator(4, "💲"),
        _indicator(5, "🛡️💍"),
    ]
    achievement = SimpleNamespace(
        stat_id=5,
        pic="💪",
        description="two consecutive wins",
        sort="none",
    )

    report = await StatUseCases(
        bet_repository=_Rows([]),
        poker_data_repository=_Rows(rows),
        achievement_repository=_Achievements([achievement]),
    ).get_poker_stat(indicators=indicators, sort_pic="💲")

    data = _data_lines(report)
    assert data == [
        ["New Name", "4", "3", "1", "200", "2", "💪"],
        ["Third", "4", "1", "1", "0", "0", ""],
        ["Alex", "4", "1", "3", "-200", "0", ""],
    ]
    assert [row.player_name for row in rows] == original_names
    assert all(isinstance(row.money_kopecks, int) for row in rows)


@pytest.mark.asyncio
async def test_duplicate_display_names_remain_two_canonical_stat_rows():
    rows = [
        _row(row_id=1, poker_id=1, day=date(2026, 2, 1), player_id=11, name="Alex", money=20_000),
        _row(row_id=2, poker_id=1, day=date(2026, 2, 1), player_id=22, name="Alex", money=-20_000),
        _row(row_id=3, poker_id=2, day=date(2026, 2, 2), player_id=11, name="Alex", money=10_000),
        _row(row_id=4, poker_id=2, day=date(2026, 2, 2), player_id=22, name="Alex", money=-10_000),
    ]

    report = await StatUseCases(
        bet_repository=_Rows([]),
        poker_data_repository=_Rows(rows),
    ).get_poker_stat(
        indicators=[_indicator(1, "🎲"), _indicator(2, "💍"), _indicator(3, "❌"), _indicator(4, "💲")],
        sort_pic="💲",
    )

    assert _data_lines(report) == [
        ["Alex", "2", "2", "0", "300"],
        ["Alex", "2", "0", "2", "-300"],
    ]


@pytest.mark.asyncio
async def test_poker_stat_year_filter_and_display_snapshot_are_deterministic():
    rows = [
        _row(row_id=1, poker_id=1, day=date(2025, 12, 31), player_id=1, name="Old", money=50_000),
        _row(row_id=2, poker_id=2, day=date(2026, 1, 1), player_id=1, name="Middle", money=10_000),
        _row(row_id=3, poker_id=3, day=date(2026, 2, 1), player_id=1, name="Current Snapshot", money=20_000),
    ]

    report = await StatUseCases(
        bet_repository=_Rows([]),
        poker_data_repository=_Rows(rows),
    ).get_poker_stat(
        indicators=[_indicator(1, "🎲"), _indicator(2, "💲")],
        year=2026,
        sort_pic="💲",
    )

    assert _data_lines(report) == [["Current Snapshot", "2", "300"]]
