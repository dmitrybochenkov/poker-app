from datetime import date

from app.bot.shared.texts.inline.telegram.user import common as InlineText
from app.bot.shared.texts.texts import Text
from app.db.repositories.poll_vote_repository import PollVoteRepository
from app.services.buyins_chart import render_buyins_session_chart_png


def _month_bounds(month: date) -> tuple[date, date]:
    first = date(month.year, month.month, 1)
    if month.month == 12:
        nxt = date(month.year + 1, 1, 1)
    else:
        nxt = date(month.year, month.month + 1, 1)
    return first, (nxt.fromordinal(nxt.toordinal() - 1))

def _parse_month_key(value: str | None) -> date:
    if not value:
        today = date.today()
        return date(today.year, today.month, 1)
    year_s, mon_s = str(value).split("-")
    return date(int(year_s), int(mon_s), 1)

def _parse_iso_dates(values: list[str] | None) -> list[date]:
    if not values:
        return []
    result: list[date] = []
    for item in values:
        try:
            result.append(date.fromisoformat(str(item)))
        except Exception:
            continue
    return sorted(set(result))

def _month_name_ru_upper(month: date) -> str:
    names = [
        InlineText.MONTH_NAME_RU_UPPER_TEXT_01,
        InlineText.MONTH_NAME_RU_UPPER_TEXT_02,
        InlineText.MONTH_NAME_RU_UPPER_TEXT_03,
        InlineText.MONTH_NAME_RU_UPPER_TEXT_04,
        InlineText.MONTH_NAME_RU_UPPER_TEXT_05,
        InlineText.MONTH_NAME_RU_UPPER_TEXT_06,
        InlineText.MONTH_NAME_RU_UPPER_TEXT_07,
        InlineText.MONTH_NAME_RU_UPPER_TEXT_08,
        InlineText.MONTH_NAME_RU_UPPER_TEXT_09,
        InlineText.MONTH_NAME_RU_UPPER_TEXT_10,
        InlineText.MONTH_NAME_RU_UPPER_TEXT_11,
        InlineText.MONTH_NAME_RU_UPPER_TEXT_12,
    ]
    return names[month.month - 1]

def _poll_choose_text(month: date) -> str:
    return f'{InlineText.POLL_CHOOSE_TEXT_TEXT_01_PART_1}{_month_name_ru_upper(month)}{InlineText.POLL_CHOOSE_TEXT_TEXT_01_PART_2}'

def _poll_days_for_month(month: date) -> list[date]:
    day = date(month.year, month.month, 1)
    result: list[date] = []
    while day.month == month.month:
        if day.weekday() in {4, 5}:
            result.append(day)
        day = date.fromordinal(day.toordinal() + 1)
    return result

def _parse_custom_day_input(raw: str, *, month: date) -> date | None:
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return None
    day = int(digits)
    try:
        value = date(month.year, month.month, day)
    except Exception:
        return None
    return value

def _format_poll_summary(
    *, month: date, selected_dates: list[date], month_counts: list[tuple[date, int]]
) -> str:
    lines = [f"{Text.user.POLL_SAVED.value} ({month:%m.%Y})"]
    if selected_dates:
        lines.append(InlineText.FORMAT_POLL_SUMMARY_TEXT_01 + ", ".join(str(item.day) for item in selected_dates))
    else:
        lines.append(InlineText.FORMAT_POLL_SUMMARY_TEXT_02)
    if month_counts:
        lines.append("")
        lines.append(InlineText.FORMAT_POLL_SUMMARY_TEXT_03)
        for day, count in month_counts:
            lines.append(f"{day.day:02d}.{day.month:02d}: {count}")
    return "\n".join(lines)

def _render_poll_results_chart(
    *,
    month: date,
    month_counts: list[tuple[date, int]],
    month_votes: list[tuple[date, int]] | None = None,
    user_names: dict[int, str] | None = None,
    days: list[date] | None = None,
) -> bytes:
    day_counts = {d: int(c) for d, c in month_counts}
    days = days or _poll_days_for_month(month)
    days = [item for item in days if int(day_counts.get(item, 0)) > 0]
    weekday_short = {
        0: InlineText.RENDER_POLL_RESULTS_CHART_TEXT_01,
        1: InlineText.RENDER_POLL_RESULTS_CHART_TEXT_02,
        2: InlineText.RENDER_POLL_RESULTS_CHART_TEXT_03,
        3: InlineText.RENDER_POLL_RESULTS_CHART_TEXT_04,
        4: InlineText.RENDER_POLL_RESULTS_CHART_TEXT_05,
        5: InlineText.RENDER_POLL_RESULTS_CHART_TEXT_06,
        6: InlineText.RENDER_POLL_RESULTS_CHART_TEXT_07,
    }
    x_labels = [f"{item.strftime('%d.%m')}\n{weekday_short[item.weekday()]}" for item in days]
    if month_votes and user_names:
        day_to_index = {day: idx for idx, day in enumerate(days)}
        day_user_voted: dict[tuple[int, int], int] = {}
        for vote_day, player_row_id in month_votes:
            if vote_day in day_to_index:
                day_user_voted[(int(player_row_id), day_to_index[vote_day])] = 1
        series: dict[str, list[tuple[int, int]]] = {}
        for player_row_id, name in user_names.items():
            points = [
                (idx, day_user_voted.get((int(player_row_id), idx), 0)) for idx in range(len(days))
            ]
            if any(value for _, value in points):
                series[name] = points
        if not series:
            series = {
                InlineText.RENDER_POLL_RESULTS_CHART_TEXT_08: [(idx, int(day_counts.get(day, 0))) for idx, day in enumerate(days)]
            }
    else:
        series = {InlineText.RENDER_POLL_RESULTS_CHART_TEXT_09: [(idx, int(day_counts.get(day, 0))) for idx, day in enumerate(days)]}
    return render_buyins_session_chart_png(
        title=f'{InlineText.RENDER_POLL_RESULTS_CHART_TEXT_10_PART_1}{month.strftime('%m.%Y')}{InlineText.RENDER_POLL_RESULTS_CHART_TEXT_10_PART_2}',
        series=series,
        x_labels=x_labels,
        chart_type="barh",
    )

async def _poll_all_days_for_month(*, session, month: date) -> list[date]:
    month_start, month_end = _month_bounds(month)
    extra_dates = await PollVoteRepository(session).get_month_extra_dates(
        month_start=month_start, month_end=month_end
    )
    return sorted(set(_poll_days_for_month(month)) | set(extra_dates))
