from datetime import date

from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.application.use_cases.poker.betting_tournament_periods import (
    list_betting_tournament_periods,
)
from app.application.use_cases.poker.stat import StatUseCases
from app.bot.shared.texts.inline.telegram.user import common as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
    betting_stat_indicators_keyboard,
    betting_tournament_periods_keyboard,
)
from app.db.repositories.bet_tournament_repository import BetTournamentRepository
from app.db.repositories.stat_indicator_repository import StatIndicatorRepository
from app.db.session import SessionFactory


def _filter_betting_indicators_by_mode(*, indicators, mode: str):
    if mode == "all":
        return [item for item in indicators if item.for_current_tournaments in {"yes", "no"}]
    return [item for item in indicators if item.for_current_tournaments in {"yes", "only"}]

def _default_betting_indicator(*, indicators, mode: str):
    preferred = InlineText.DEFAULT_BETTING_INDICATOR_TEXT_01 if mode == "all" else InlineText.DEFAULT_BETTING_INDICATOR_TEXT_02
    item = next((ind for ind in indicators if str(ind.description).strip() == preferred), None)
    if item is None and indicators:
        item = indicators[0]
    return item

def _format_stat_caption(
    *,
    report_type: str,
    indicators: list,
    years: list[int] | None = None,
    period_labels: list[str] | None = None,
    include_period: bool = False,
) -> str:
    lines = [report_type]
    if include_period:
        if period_labels is not None:
            period = ", ".join(period_labels)
        else:
            year_values = sorted({int(y) for y in (years or [])})
            period = ", ".join(str(y) for y in year_values) if year_values else str(date.today().year)
        lines.append(f'{InlineText.FORMAT_STAT_CAPTION_TEXT_01_PART_1}{period}{InlineText.FORMAT_STAT_CAPTION_TEXT_01_PART_2}')
    pics = [
        str(getattr(item, "pic", "")).strip()
        for item in indicators
        if str(getattr(item, "pic", "")).strip()
    ]
    if pics:
        lines.append(f'{InlineText.FORMAT_STAT_CAPTION_TEXT_02_PART_1}{', '.join(pics)}{InlineText.FORMAT_STAT_CAPTION_TEXT_02_PART_2}')
    return "\n".join(lines)

def _format_tournament_name(tournament_type: str) -> str:
    return InlineText.FORMAT_TOURNAMENT_NAME_TEXT_01

def _format_stat_info_report(indicators) -> str:
    if not indicators:
        return InlineText.FORMAT_STAT_INFO_REPORT_TEXT_01
    lines: list[str] = []
    for item in indicators:
        pic = StatUseCases._prettify_header(str(item.pic or ""))
        lines.append(f"{pic} <b>{item.description}</b>")
        lines.append(f"{item.description_full}")
        lines.append("")
    return "\n".join(lines).strip()

def _format_achievement_description(raw: str) -> tuple[str, str | None]:
    if "_" not in raw:
        return raw, None
    title, detail = raw.split("_", 1)
    return title.strip(), detail.strip() if detail else None

def _format_achievement_info_report(
    achievements, indicators_by_id: dict[int, tuple[str, str]]
) -> str:
    if not achievements:
        return InlineText.FORMAT_ACHIEVEMENT_INFO_REPORT_TEXT_01
    lines: list[str] = []
    for item in achievements:
        title, detail = _format_achievement_description(item.description)
        ach_pic = StatUseCases._prettify_header(str(item.pic or ""))
        lines.append(f"{ach_pic} <b>{title}</b>")
        if detail:
            lines.append(detail)
        indicator_info = indicators_by_id.get(int(item.stat_id))
        if indicator_info:
            indicator_pic, indicator_name = indicator_info
            indicator_pic = StatUseCases._prettify_header(str(indicator_pic or ""))
            lines.append(f'{InlineText.FORMAT_ACHIEVEMENT_INFO_REPORT_TEXT_02_PART_1}{indicator_pic}{InlineText.FORMAT_ACHIEVEMENT_INFO_REPORT_TEXT_02_PART_2}{indicator_name}'.strip())
        lines.append("")
    return "\n".join(lines).strip()

async def _start_betting_stat_flow(
    *, message: Message, state: FSMContext, mode: str, preserve_period_selection: bool = False
) -> None:
    state_update = {
        "betstat_selected_ids": [],
        "betstat_mode": mode,
        "betstat_sort_id": None,
        "betstat_page": 0,
    }
    if not preserve_period_selection:
        state_update["betstat_period_ids"] = []
    await state.update_data(**state_update)
    if mode in {"regular", "year"}:
        async with SessionFactory() as session:
            indicators = await StatIndicatorRepository(session).list_by_type(
                indicator_type="betting"
            )
        indicators = _filter_betting_indicators_by_mode(indicators=indicators, mode=mode)
        if not indicators:
            await message.answer(Text.user.BETTING_CURRENT_EMPTY.value)
            return
        await message.answer(
            Text.user.STAT_CHOOSE_PARAMS.value,
            reply_markup=betting_stat_indicators_keyboard(
                indicators=indicators, page=0, selected_ids=[]
            ),
        )
        return
    async with SessionFactory() as session:
        tournaments = await BetTournamentRepository(session).list_active()
    periods = list_betting_tournament_periods(tournaments)
    if not periods:
        await message.answer(InlineText.START_BETTING_STAT_FLOW_TEXT_01)
        return
    await message.answer(
        Text.user.STAT_CHOOSE_BETTING_TOURNAMENT.value,
        reply_markup=betting_tournament_periods_keyboard(
            periods=periods, selected_period_ids=set(), page=0
        ),
    )
