from datetime import date

from app.application.use_cases.poker.stat import StatUseCases
from app.bot.shared.texts.inline.vk.user import common as InlineText

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
    include_period: bool = False,
) -> str:
    lines = [report_type]
    if include_period:
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
        lines.append(f"{pic} {item.description}")
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
        lines.append(f"{ach_pic} {title}")
        if detail:
            lines.append(detail)
        indicator_info = indicators_by_id.get(int(item.stat_id))
        if indicator_info:
            indicator_pic, indicator_name = indicator_info
            indicator_pic = StatUseCases._prettify_header(str(indicator_pic or ""))
            lines.append(f'{InlineText.FORMAT_ACHIEVEMENT_INFO_REPORT_TEXT_02_PART_1}{indicator_pic}{InlineText.FORMAT_ACHIEVEMENT_INFO_REPORT_TEXT_02_PART_2}{indicator_name}'.strip())
        lines.append("")
    return "\n".join(lines).strip()
