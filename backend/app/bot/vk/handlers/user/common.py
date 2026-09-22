import asyncio
import logging
import random
import re
import urllib.request
from datetime import date, timezone
from zoneinfo import ZoneInfo

from app.application.exceptions import (
    UserAlreadyRegisteredError,
    UserIdentityRequiredError,
    UserNameRequiredError,
    UserRegistrationPendingError,
)
from app.application.use_cases.poker.stat import StatUseCases
from app.application.use_cases.user.request_registration import RequestRegistrationUseCase
from app.bot.shared.chips_runtime import (
    TG_ADMIN_ROOM_STATUS_MSG_IDS,
    VK_ADMIN_ROOM_STATUS_MSG_IDS,
)
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
    poker_room_admin_status_keyboard as tg_poker_room_admin_status_keyboard,
)
from app.bot.telegram.keyboards import (
    registration_link_review_keyboard as tg_registration_link_review_keyboard,
)
from app.bot.telegram.keyboards import (
    registration_review_keyboard as tg_registration_review_keyboard,
)
from app.bot.telegram.notifications import (
    notify_admins_about_registration as notify_tg_admins_about_registration,
)
from app.bot.vk.api import (
    delete_vk_message,
    delete_vk_message_by_id,
    send_vk_message,
    send_vk_message_with_id,
)
from app.bot.vk.keyboards import (
    betting_dynamic_keyboard,
    main_dynamic_keyboard,
    main_keyboard,
    new_user_keyboard,
    poker_room_admin_status_keyboard,
    room_admin_keyboard,
    room_keyboard,
)
from app.bot.vk.keyboards import (
    registration_link_review_keyboard as vk_registration_link_review_keyboard,
)
from app.bot.vk.keyboards import (
    registration_review_keyboard as vk_registration_review_keyboard,
)
from app.bot.vk.notifications import notify_admins_about_registration
from app.bot.vk.state import (
    vk_user_contexts,
    vk_user_states,
)
from app.db.models.user import User
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.buyin_data_repository import BuyinDataRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_param_repository import PokerParamRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.poll_config_repository import PollConfigRepository
from app.db.repositories.poll_vote_repository import PollVoteRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory
from app.services.buyins_chart import render_buyins_session_chart_png

STAT_SNACKBAR = "Обновлено"
PAYMENT_OWNER_ROW_ID = 1
logger = logging.getLogger(__name__)


HANDLER_UNMATCHED = object()


def _clear_vk_bet_draft_state(user_id: int) -> None:
    vk_user_states.pop(user_id, None)
    ctx = vk_user_contexts.setdefault(user_id, {})
    for key in (
        "bet_tournament_type",
        "bet_players",
        "bet_better_name",
        "bet_amount_kopecks",
        "bet_winner_name",
        "bet_loser_name",
    ):
        ctx.pop(key, None)


def _format_payment_requisites(owner: User | None) -> str:
    if owner is None:
        return "реквизиты не указаны"
    phone = (owner.tel_number or "").strip()
    bank = (owner.bank_name or "").strip()
    if phone and bank:
        return f"{phone} ({bank})"
    if phone:
        return phone
    return "реквизиты не указаны"


def _format_unpaid_bets_lines(bets: list) -> str:
    if not bets:
        return "-"
    return "\n".join(
        f"{(bet.date.strftime('%d.%m.%Y') if bet.date else '—')} - {int(bet.amount_kopecks) // 100} ₽"
        for bet in bets
    )


def _format_rub_from_kopecks(value_kopecks: int) -> str:
    rub = int(value_kopecks) // 100
    kop = abs(int(value_kopecks) % 100)
    if kop == 0:
        return str(rub)
    return f"{rub}.{kop:02d}"


def _pick_fifo_bets_to_close(*, bets: list, paid_kopecks: int) -> list:
    selected: list = []
    running = 0
    for bet in bets:
        running += int(bet.amount_kopecks)
        selected.append(bet)
        if running == paid_kopecks:
            return selected
        if running > paid_kopecks:
            return []
    return []


def _extract_vk_attachment_url(raw_message: dict | None) -> str | None:
    attachments = (raw_message or {}).get("attachments") or []
    for item in attachments:
        item_type = str(item.get("type") or "")
        if item_type == "photo":
            photo = item.get("photo") or {}
            sizes = photo.get("sizes") or []
            if sizes:
                best = max(sizes, key=lambda s: int(s.get("width", 0)) * int(s.get("height", 0)))
                url = best.get("url")
                if isinstance(url, str) and url:
                    return url
        if item_type == "doc":
            doc = item.get("doc") or {}
            url = doc.get("url")
            if isinstance(url, str) and url:
                return url
    return None


def _extract_vk_external_file_id(raw_message: dict | None) -> str | None:
    attachments = (raw_message or {}).get("attachments") or []
    for item in attachments:
        item_type = str(item.get("type") or "")
        if item_type == "photo":
            photo = item.get("photo") or {}
            owner_id = photo.get("owner_id")
            photo_id = photo.get("id")
            if owner_id is not None and photo_id is not None:
                return f"photo:{owner_id}_{photo_id}"
        if item_type == "doc":
            doc = item.get("doc") or {}
            owner_id = doc.get("owner_id")
            doc_id = doc.get("id")
            if owner_id is not None and doc_id is not None:
                return f"doc:{owner_id}_{doc_id}"
    return None


async def _download_vk_receipt_bytes(raw_message: dict | None) -> bytes | None:
    url = _extract_vk_attachment_url(raw_message)
    if not url:
        return None

    def _read() -> bytes | None:
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                return response.read()
        except Exception:
            return None

    return await asyncio.to_thread(_read)


def _month_bounds(month: date) -> tuple[date, date]:
    first = date(month.year, month.month, 1)
    if month.month == 12:
        nxt = date(month.year + 1, 1, 1)
    else:
        nxt = date(month.year, month.month + 1, 1)
    return first, (nxt.fromordinal(nxt.toordinal() - 1))


def _shift_month(month: date, delta: int) -> date:
    total = month.year * 12 + (month.month - 1) + delta
    year = total // 12
    mon = total % 12 + 1
    return date(year, mon, 1)


def _parse_month_key(value: str | None) -> date:
    if not value:
        today = date.today()
        return date(today.year, today.month, 1)
    year_s, mon_s = str(value).split("-")
    return date(int(year_s), int(mon_s), 1)


def _parse_iso_dates(values: str | None) -> list[date]:
    if not values:
        return []
    result: list[date] = []
    for item in str(values).split("|"):
        if not item:
            continue
        try:
            result.append(date.fromisoformat(item))
        except Exception:
            continue
    return sorted(set(result))


def _month_name_ru_upper(month: date) -> str:
    names = [
        "ЯНВАРЬ",
        "ФЕВРАЛЬ",
        "МАРТ",
        "АПРЕЛЬ",
        "МАЙ",
        "ИЮНЬ",
        "ИЮЛЬ",
        "АВГУСТ",
        "СЕНТЯБРЬ",
        "ОКТЯБРЬ",
        "НОЯБРЬ",
        "ДЕКАБРЬ",
    ]
    return names[month.month - 1]


def _poll_choose_text(month: date) -> str:
    return f"Выбери даты на {_month_name_ru_upper(month)} и нажми '🚀 Готово'."


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
        lines.append("Твои даты: " + ", ".join(str(item.day) for item in selected_dates))
    else:
        lines.append("Твои даты: не выбраны")
    if month_counts:
        lines.append("")
        lines.append("Общий итог:")
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
        0: "пн",
        1: "вт",
        2: "ср",
        3: "чт",
        4: "пт",
        5: "сб",
        6: "вс",
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
                "Голоса": [(idx, int(day_counts.get(day, 0))) for idx, day in enumerate(days)]
            }
    else:
        series = {"Голоса": [(idx, int(day_counts.get(day, 0))) for idx, day in enumerate(days)]}
    return render_buyins_session_chart_png(
        title=f"Голоса за даты покера ({month.strftime('%m.%Y')})",
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


def _filter_betting_indicators_by_mode(*, indicators, mode: str):
    if mode == "all":
        return [item for item in indicators if item.for_current_tournaments in {"yes", "no"}]
    return [item for item in indicators if item.for_current_tournaments in {"yes", "only"}]


def _default_betting_indicator(*, indicators, mode: str):
    preferred = "Денег выиграно" if mode == "all" else "Баллы"
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
        lines.append(f"Период: {period}.")
    pics = [
        str(getattr(item, "pic", "")).strip()
        for item in indicators
        if str(getattr(item, "pic", "")).strip()
    ]
    if pics:
        lines.append(f"Показатели: {', '.join(pics)}.")
    return "\n".join(lines)


def _strip_html_tags(text: str) -> str:
    return text.replace("<b>", "").replace("</b>", "")


def _normalize_vk_button_text(text: str) -> str:
    normalized = " ".join((text or "").replace("\ufe0f", "").split()).strip().lower()
    normalized = re.sub(r"^[^\w\dа-яё]+", "", normalized, flags=re.IGNORECASE)
    return normalized


def _vk_button_matches(text: str, button_text: str) -> bool:
    return _normalize_vk_button_text(text) == _normalize_vk_button_text(button_text)


def _money_kopecks_from_chips(
    *, chips: int, buyins: int, buyin_size_chips: int, buyin_size_kopecks: int
) -> int:
    if buyin_size_chips <= 0:
        return 0
    return ((int(chips) - int(buyins) * int(buyin_size_chips)) * int(buyin_size_kopecks)) // int(
        buyin_size_chips
    )


def _format_rub_from_kopecks(value_kopecks: int) -> str:
    rub = int(value_kopecks) // 100
    kop = abs(int(value_kopecks) % 100)
    if kop == 0:
        return str(rub)
    return f"{rub}.{kop:02d}"


def _chips_reaction(money_kopecks: int) -> str:
    winner = ["🍾", "👍", "🔥", "🏆", "👏", "🤩", "🎉"]
    loser = ["👎", "🥴", "😢", "💩", "🤮", "😭", "🤷‍♀"]
    return random.choice(winner if int(money_kopecks) >= 0 else loser)


def _build_chips_status_text(*, players: list, chips_in_game: int, chips_entered: int) -> str:
    def money_from_chips(
        chips: int, buyins: int, buyin_size_chips: int, buyin_size_kopecks: int
    ) -> int:
        if buyin_size_chips <= 0:
            return 0
        return (
            (int(chips) - int(buyins) * int(buyin_size_chips)) * int(buyin_size_kopecks)
        ) // int(buyin_size_chips)

    def reaction(money_kopecks: int) -> str:
        return "😎" if int(money_kopecks) >= 0 else "🤮"

    buyin_size_chips = 200
    buyin_size_kopecks = 20000
    if players:
        sample = players[0]
        buyin_size_chips = int(getattr(sample, "_buyin_size_chips", buyin_size_chips))
        buyin_size_kopecks = int(getattr(sample, "_buyin_size_kopecks", buyin_size_kopecks))

    remainder = int(chips_in_game) - int(chips_entered)
    lines = [
        "🎰 Ввод фишек.",
        "",
        f"Закуплено: {chips_in_game}. Введено: {chips_entered}. Остаток: {remainder}",
        "",
    ]
    for p in players:
        if p.chips is None:
            lines.append(f"{p.player_name}: еще не ввел фишки")
        else:
            money_kopecks = money_from_chips(
                chips=int(p.chips),
                buyins=int(p.buyins),
                buyin_size_chips=buyin_size_chips,
                buyin_size_kopecks=buyin_size_kopecks,
            )
            lines.append(
                f"{p.player_name}: {int(p.chips)} → {_format_rub_from_kopecks(int(money_kopecks))} ₽ {reaction(int(money_kopecks))}"
            )
    return "\n".join(lines)


def _build_user_chips_text(
    *, chips: int | None, money_kopecks: int | None, reaction: str | None
) -> str:
    chips_text = str(chips) if chips is not None else "ты еще не ввел фишки"
    if money_kopecks is None or reaction is None:
        result_text = "ты еще не ввел фишки"
    else:
        result_text = f"{_format_rub_from_kopecks(int(money_kopecks))} ₽ {reaction}"
    return (
        "Покер завершен. Посчитай свои фишки и отправь число мне.\n"
        f"Введено: {chips_text}\n"
        f"Итог: {result_text}"
    )


def _split_names(value: str | None) -> set[str]:
    if not value:
        return set()
    return {item.strip() for item in str(value).split(",") if item.strip()}


def _calculate_transfers_history(money_rows: list[dict[str, int | str]]) -> list[str]:
    rows = [{"name": str(item["name"]), "money": int(item["money"])} for item in money_rows]
    lines: list[str] = []
    while True:
        loser = min(rows, key=lambda x: int(x["money"]))
        winner = max(rows, key=lambda x: int(x["money"]))
        if int(loser["money"]) == 0 and int(winner["money"]) == 0:
            break
        transfer = min(-int(loser["money"]), int(winner["money"]))
        if transfer <= 0:
            break
        loser["money"] = int(loser["money"]) + transfer
        winner["money"] = int(winner["money"]) - transfer
        lines.append(f"{loser['name']} → {winner['name']} {_format_rub_from_kopecks(transfer)} ₽")
    return lines


async def _build_poker_history_report(*, session, target_date: date) -> str:
    poker_rows = await PokerRepository(session).list_all()
    poker = next(
        (item for item in poker_rows if item.date == target_date and not bool(item.is_going)), None
    )
    if poker is None:
        return "Игра не найдена."
    params = await PokerParamRepository(session).get_by_row_id(row_id=int(poker.params_id))
    buyin_size_chips = int(params.buyin_size_chips) if params is not None else 200
    buyin_size_kopecks = int(params.buyin_size_kopecks) if params is not None else 20000
    players = await PokerDataRepository(session).list_players(date=target_date)
    if not players:
        return "Нет данных по игре."

    player_rows: list[dict[str, int | str]] = []
    money_rows: list[dict[str, int | str]] = []
    for player in players:
        chips = int(player.chips or 0)
        money_kopecks = int(
            player.money_kopecks
            or _money_kopecks_from_chips(
                chips=chips,
                buyins=int(player.buyins),
                buyin_size_chips=buyin_size_chips,
                buyin_size_kopecks=buyin_size_kopecks,
            )
        )
        money_rows.append({"name": player.player_name, "money": money_kopecks})
        player_rows.append(
            {
                "name": player.player_name,
                "buyins": int(player.buyins),
                "chips": chips,
                "money": money_kopecks,
            }
        )

    player_rows.sort(key=lambda item: int(item["money"]), reverse=True)
    player_lines = [
        (
            f"{str(item['name'])}: {int(item['buyins'])} закупов, {int(item['chips'])} фишек, "
            f"{_format_rub_from_kopecks(int(item['money']))} рублей"
        )
        for item in player_rows
    ]
    poker_money_by_name = {str(item["name"]): int(item["money"]) for item in player_rows}

    winners = [name.strip() for name in str(poker.winners or "").split(",") if name.strip()]
    losers = [name.strip() for name in str(poker.loosers or "").split(",") if name.strip()]
    winner_line = ", ".join(f"💍 {name}" for name in winners) if winners else "💍 -"
    loser_line = ", ".join(f"❌ {name}" for name in losers) if losers else "❌ -"
    transfer_lines = _calculate_transfers_history(money_rows)
    bets = await BetRepository(session).list_for_poker(date=target_date)

    lines = [
        target_date.strftime("%d.%m.%Y"),
        "♣️ Покер",
        *player_lines,
        "",
        winner_line,
        loser_line,
        "",
        "💲 Переводы:",
    ]
    lines.extend(transfer_lines if transfer_lines else ["Переводы не требуются"])
    if bets:
        lines.extend(["", "🍀 Ставки"])
        for bet in sorted(
            bets,
            key=lambda item: (
                -int(item.score or 0),
                -int(poker_money_by_name.get(str(item.better_name), 0)),
                int(item.row_id),
            ),
        ):
            size_mark = "🐔" if int(bet.amount_kopecks or 0) >= 40000 else "🐤"
            score_value = int(bet.score or 0)
            score_text = f"+{score_value}" if score_value > 0 else str(score_value)
            winner_name = str(bet.winner_name or "-")
            loser_name = str(bet.loser_name or "-")
            lines.append(
                f"{bet.better_name}: {size_mark}, W: {winner_name}, L: {loser_name} → {score_text} баллов"
            )
    return "\n".join(lines)


async def _build_poker_history_buyins_chart(*, session, target_date: date) -> bytes | None:
    buyin_events = await BuyinDataRepository(session).list_for_date(poker_date=target_date)
    if not buyin_events:
        return None

    cumulative: dict[str, int] = {}
    points: dict[str, list[tuple[int, int]]] = {}
    x_labels: list[str] = []
    msk_tz = ZoneInfo("Europe/Moscow")

    for idx, event in enumerate(buyin_events):
        if event.created_at is not None:
            event_dt = event.created_at
            if event_dt.tzinfo is None:
                event_dt = event_dt.replace(tzinfo=timezone.utc)
            label = event_dt.astimezone(msk_tz).strftime("%H:%M")
        else:
            label = str(idx + 1)
        x_labels.append(label)
        for name in list(points.keys()):
            points[name].append((idx, cumulative.get(name, 0)))
        name = str(event.player_name)
        cumulative[name] = cumulative.get(name, 0) + int(event.buyins_count or 0)
        if name not in points:
            points[name] = [(prev_idx, 0) for prev_idx in range(idx)]
            points[name].append((idx, cumulative[name]))
        else:
            points[name][-1] = (idx, cumulative[name])

    points = {name: vals for name, vals in points.items() if vals}
    if not points:
        return None

    return render_buyins_session_chart_png(
        title=f"Закупы за игру {target_date.strftime('%d.%m.%Y')}",
        series=points,
        x_labels=x_labels,
        legend_value_mode="max",
    )


async def _build_bet_last_five_hints(
    *, session, players: list[str]
) -> tuple[dict[str, str], str, str]:
    poker_rows = await PokerRepository(session).list_all()
    poker_rows = [
        p
        for p in poker_rows
        if p.date is not None
        and not bool(p.is_going)
        and bool(str(p.winners or "").strip())
        and bool(str(p.loosers or "").strip())
    ]
    poker_rows.sort(key=lambda p: p.date)
    winners_by_date = {p.date: _split_names(p.winners) for p in poker_rows}
    losers_by_date = {p.date: _split_names(p.loosers) for p in poker_rows}
    completed_dates = {p.date for p in poker_rows}
    poker_data_rows = await PokerDataRepository(session).list_all()
    player_game_dates: dict[str, list] = {}
    for row in poker_data_rows:
        if row.date in completed_dates:
            player_game_dates.setdefault(row.player_name, []).append(row.date)
    for name, dates in list(player_game_dates.items()):
        player_game_dates[name] = sorted(set(dates))

    def player_marks(player_name: str) -> str:
        player_dates = player_game_dates.get(player_name, [])[-5:]
        marks: list[str] = []
        for d in player_dates:
            if player_name in winners_by_date.get(d, set()):
                marks.append(" 🟢")
            elif player_name in losers_by_date.get(d, set()):
                marks.append(" 🔴")
            else:
                marks.append(" ⚪")
        return "".join(marks)

    marks_map = {name: player_marks(name) for name in players}
    last_five_games = poker_rows[-5:]
    winners_text = "\n".join(str(p.winners or "-") for p in last_five_games)
    losers_text = "\n".join(str(p.loosers or "-") for p in last_five_games)
    return marks_map, winners_text, losers_text


async def _notify_admins_about_room_join(
    *,
    session,
    joined_user: User,
    platform_label: str,
) -> None:
    from app.bot.telegram.runtime import telegram_bot

    repository = UserRepository(session)
    poker_repository = PokerRepository(session)
    poker_data_repository = PokerDataRepository(session)
    active = await poker_repository.get_started()
    players = (
        await poker_data_repository.list_players(date=active[0].date) if active is not None else []
    )
    player_row_ids = {int(p.player_id) for p in players}
    admins = [
        u
        for u in await repository.list_approved()
        if u.is_admin and int(u.row_id) in player_row_ids
    ]
    admin_tg_ids = [int(u.telegram_id) for u in admins if u.telegram_id is not None]
    admin_vk_ids = [int(u.vk_id) for u in admins if u.vk_id is not None]
    can_start_betting = bool(
        active is not None
        and active[0].cashier_id is not None
        and not bool(active[0].is_bettable)
        and not bool(active[0].is_ready_for_chips_entering)
    )
    if active is None or active[0].cashier_id is None:
        status_text = (
            "🎲 Ниже список игроков в руме.\n"
            "❌ Лишних можно удалить.\n"
            "❗ После входа большинства игроков выбери кассира."
        )
    else:
        status_text = (
            "🍀 Когда все игроки будут в руме - запусти ставки.\n"
            "❗ Ставки можно делать только на активных игроков."
        )
    for admin_id in admin_tg_ids:
        if joined_user.telegram_id is not None and int(admin_id) == int(joined_user.telegram_id):
            continue
        if telegram_bot is not None:
            prev_mid = TG_ADMIN_ROOM_STATUS_MSG_IDS.get(int(admin_id))
            if prev_mid is not None:
                try:
                    await telegram_bot.delete_message(
                        chat_id=int(admin_id), message_id=int(prev_mid)
                    )
                except Exception:
                    pass
            sent = await telegram_bot.send_message(
                chat_id=int(admin_id),
                text=status_text,
                reply_markup=tg_poker_room_admin_status_keyboard(
                    players=[]
                    if (active is not None and active[0].cashier_id is not None)
                    else players,
                    can_start_betting=can_start_betting,
                ),
            )
            TG_ADMIN_ROOM_STATUS_MSG_IDS[int(admin_id)] = int(sent.message_id)

    for admin_id in admin_vk_ids:
        if joined_user.vk_id is not None and int(admin_id) == int(joined_user.vk_id):
            continue
        prev_mid = VK_ADMIN_ROOM_STATUS_MSG_IDS.get(int(admin_id))
        if prev_mid is not None:
            try:
                await delete_vk_message_by_id(peer_id=int(admin_id), message_id=int(prev_mid))
            except Exception:
                pass
        sent_mid = await send_vk_message_with_id(
            user_id=int(admin_id),
            message=status_text,
            keyboard=poker_room_admin_status_keyboard(
                players=[]
                if (active is not None and active[0].cashier_id is not None)
                else players,
                can_start_betting=can_start_betting,
            ),
        )
        if sent_mid is not None:
            VK_ADMIN_ROOM_STATUS_MSG_IDS[int(admin_id)] = int(sent_mid)


async def _get_vk_user(user_id: int) -> User | None:
    async with SessionFactory() as session:
        repository = UserRepository(session)
        return await repository.get_by_vk_id(user_id)


async def _is_vk_user_approved(user_id: int) -> bool:
    user = await _get_vk_user(user_id)
    return bool(user and user.is_approved)


async def _approved_vk_keyboard(user: User) -> str:
    async with SessionFactory() as session:
        active = await PokerRepository(session).get_started()
        poll_month = await PollConfigRepository(session).get_active_month()
    return main_dynamic_keyboard(
        is_admin=bool(user.is_admin),
        has_active_poker=active is not None,
        has_active_poll=poll_month is not None,
    )


async def _betting_vk_keyboard() -> str:
    return betting_dynamic_keyboard(include_make_bet=True)


async def _post_bet_vk_keyboard_for_user(*, vk_id: int) -> str:
    async with SessionFactory() as session:
        user = await UserRepository(session).get_by_vk_id(vk_id)
        if user is None:
            return main_keyboard
        active = await PokerRepository(session).get_started()
        if active is None:
            return await _approved_vk_keyboard(user)
        poker, _ = active
        player = await PokerDataRepository(session).get_player(
            date=poker.date, player_id=int(user.row_id)
        )
        if player is not None:
            return room_admin_keyboard if user.is_admin else room_keyboard
        return await _approved_vk_keyboard(user)


async def _delete_event_message_if_possible(
    *, peer_id: int | None, conversation_message_id: int | None
) -> None:
    if peer_id is None or conversation_message_id is None:
        return
    try:
        await delete_vk_message(
            peer_id=peer_id,
            conversation_message_id=conversation_message_id,
        )
    except Exception:
        return


def _format_tournament_name(tournament_type: str) -> str:
    return "Турнир"


def _format_stat_info_report(indicators) -> str:
    if not indicators:
        return "Справка пока пустая."
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
        return "Справка пока пустая."
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
            lines.append(f"Показатель: {indicator_pic} {indicator_name}".strip())
        lines.append("")
    return "\n".join(lines).strip()


async def _submit_registration_request(
    *,
    user_id: int,
    name: str,
    success_message: str,
    linked_to_user: User | None = None,
    bank_name: str | None = None,
    tel_number: str | None = None,
    notification_platform: str | None = None,
) -> None:
    async with SessionFactory() as session:
        repository = UserRepository(session)
        use_case = RequestRegistrationUseCase(repository)
        try:
            user = await use_case.execute(
                name=name,
                vk_id=user_id,
                bank_name=bank_name,
                tel_number=tel_number,
                notification_platform=notification_platform,
            )
        except UserIdentityRequiredError:
            await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_ID_ERROR.value)
            return
        except UserNameRequiredError:
            await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_EMPTY_NAME.value)
            return
        except UserAlreadyRegisteredError:
            vk_user_states.pop(user_id, None)
            vk_user_contexts.pop(user_id, None)
            existing_user = await repository.get_by_vk_id(user_id)
            keyboard = (
                (await _approved_vk_keyboard(existing_user))
                if existing_user and existing_user.is_approved
                else new_user_keyboard
            )
            await send_vk_message(
                user_id=user_id, message=Text.user.REGISTRATION_EXIST.value, keyboard=keyboard
            )
            return
        except UserRegistrationPendingError:
            vk_user_states.pop(user_id, None)
            vk_user_contexts.pop(user_id, None)
            await send_vk_message(
                user_id=user_id,
                message=Text.user.REGISTRATION_PENDING.value,
                keyboard=new_user_keyboard,
            )
            return

        admin_ids = await repository.list_admin_vk_ids()
        tg_admin_chat_ids = await repository.list_admin_tg_ids()

    vk_user_states.pop(user_id, None)
    vk_user_contexts.pop(user_id, None)
    await notify_tg_admins_about_registration(
        name=name,
        telegram_id=None,
        vk_id=user_id,
        requester_platform="vk",
        admin_chat_ids=tg_admin_chat_ids,
        linked_to_user=linked_to_user,
        reply_markup=(
            tg_registration_link_review_keyboard(row_id=user.row_id)
            if linked_to_user is not None
            else tg_registration_review_keyboard(row_id=user.row_id)
        ),
    )
    await notify_admins_about_registration(
        name=name,
        vk_id=user_id,
        requester_platform="vk",
        admin_ids=admin_ids,
        linked_to_user=linked_to_user,
        keyboard=(
            vk_registration_link_review_keyboard(row_id=user.row_id)
            if linked_to_user is not None
            else vk_registration_review_keyboard(row_id=user.row_id)
        ),
    )
    await send_vk_message(user_id=user_id, message=success_message, keyboard=new_user_keyboard)


def _normalize_phone(value: str) -> str | None:
    digits = "".join(ch for ch in value if ch.isdigit())
    if digits.startswith("7") and len(digits) == 11:
        return f"+{digits}"
    return None
