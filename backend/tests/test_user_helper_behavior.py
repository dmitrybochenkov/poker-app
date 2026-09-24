from types import SimpleNamespace

from app.bot.telegram.handlers.user import betting_stats as tg_betting_stats
from app.bot.telegram.handlers.user import navigation as tg_navigation
from app.bot.vk.handlers.user import betting_stats as vk_betting_stats
from app.bot.vk.handlers.user import information as vk_information


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
