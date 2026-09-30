from datetime import date
from types import SimpleNamespace

import pytest

from app.bot.telegram.handlers.user import betting_stats as tg_betting_stats
from app.bot.telegram.handlers.user import navigation as tg_navigation
from app.bot.telegram.handlers.user import poker_stats as tg_poker_stats
from app.bot.vk.handlers.user import betting_stats as vk_betting_stats
from app.bot.vk.handlers.user import information as vk_information
from app.bot.vk.handlers.user import poker_stats as vk_poker_stats


def _indicator():
    return SimpleNamespace(pic="🏆", description="Wins", description_full="Full")


def test_statistics_caption_format_is_stable_across_platforms():
    expected = "Report\nПериод: 2024, 2025.\nПоказатели: 🏆."

    assert (
        tg_betting_stats._format_stat_caption(
            report_type="Report",
            indicators=[_indicator()],
            years=[2025, 2024],
            include_period=True,
        )
        == expected
    )
    assert (
        vk_betting_stats._format_stat_caption(
            report_type="Report",
            indicators=[_indicator()],
            years=[2025, 2024],
            include_period=True,
        )
        == expected
    )


def test_statistics_information_format_remains_platform_specific():
    assert tg_navigation._format_stat_info_report([_indicator()]) == "🏆 <b>Wins</b>\nFull"
    assert vk_information._format_stat_info_report([_indicator()]) == "🏆 Wins\nFull"


@pytest.mark.asyncio
@pytest.mark.parametrize("consumer", [tg_poker_stats, vk_poker_stats])
async def test_poker_history_report_format_is_stable(monkeypatch, consumer):
    target_date = date(2026, 1, 2)

    class PokerRepository:
        def __init__(self, session):
            pass

        async def list_all(self):
            return [
                SimpleNamespace(
                    date=target_date,
                    is_going=False,
                    params_id=1,
                    winners="Winner",
                    loosers="Loser",
                )
            ]

    class PokerParamRepository:
        def __init__(self, session):
            pass

        async def get_by_row_id(self, *, row_id):
            return SimpleNamespace(buyin_size_chips=200, buyin_size_kopecks=20_000)

    class PokerDataRepository:
        def __init__(self, session):
            pass

        async def list_players_for_date(self, *, date):
            return [
                SimpleNamespace(
                    player_name="Winner", chips=300, money_kopecks=10_000, buyins=1
                ),
                SimpleNamespace(
                    player_name="Loser", chips=100, money_kopecks=-10_000, buyins=1
                ),
            ]

    class BetRepository:
        def __init__(self, session):
            pass

        async def list_for_date(self, *, date):
            return []

    report_builder = consumer._build_poker_history_report
    for name, replacement in {
        "PokerRepository": PokerRepository,
        "PokerParamRepository": PokerParamRepository,
        "PokerDataRepository": PokerDataRepository,
        "BetRepository": BetRepository,
    }.items():
        monkeypatch.setitem(report_builder.__globals__, name, replacement)

    report = await report_builder(session=object(), target_date=target_date)

    assert report == (
        "02.01.2026\n"
        "♣️ Покер\n"
        "Winner: 1 закупов, 300 фишек, 100 рублей\n"
        "Loser: 1 закупов, 100 фишек, -100 рублей\n\n"
        "💍 Winner\n"
        "❌ Loser\n\n"
        "💲 Переводы:\n"
        "Loser → Winner 100 ₽"
    )
