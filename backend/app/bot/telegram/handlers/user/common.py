import logging
import random
from datetime import date, timezone
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from app.application.exceptions import (
    UserAlreadyRegisteredError,
    UserIdentityRequiredError,
    UserNameRequiredError,
    UserRegistrationPendingError,
)
from app.application.use_cases.poker.stat import StatUseCases
from app.application.use_cases.user.request_registration import RequestRegistrationUseCase
from app.bot.shared.chips_runtime import (
    TG_ADMIN_CHIPS_STATUS_MSG_IDS,
    TG_ADMIN_ROOM_STATUS_MSG_IDS,
    TG_USER_CHIPS_RESULT_MSG_IDS,
    VK_ADMIN_ROOM_STATUS_MSG_IDS,
)
from app.bot.shared.texts.inline.telegram.user import common as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
    betting_dynamic_keyboard,
    betting_stat_indicators_keyboard,
    main_dynamic_keyboard,
    main_keyboard,
    new_user_keyboard,
    poker_calc_keyboard,
    poker_room_admin_status_keyboard,
    registration_link_review_keyboard,
    registration_review_keyboard,
    room_admin_keyboard,
    room_keyboard,
    stat_year_keyboard,
)
from app.bot.telegram.notifications import notify_admins_about_registration
from app.bot.telegram.states import RegistrationState
from app.bot.vk.api import delete_vk_message_by_id, send_vk_message, send_vk_message_with_id
from app.bot.vk.keyboards import (
    poker_room_admin_status_keyboard as vk_poker_room_admin_status_keyboard,
)
from app.bot.vk.keyboards import (
    registration_link_review_keyboard as vk_registration_link_review_keyboard,
)
from app.bot.vk.keyboards import (
    registration_review_keyboard as vk_registration_review_keyboard,
)
from app.bot.vk.notifications import (
    notify_admins_about_registration as notify_vk_admins_about_registration,
)
from app.db.models.user import User
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.buyin_data_repository import BuyinDataRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_param_repository import PokerParamRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.poll_config_repository import PollConfigRepository
from app.db.repositories.stat_indicator_repository import StatIndicatorRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory
from app.services.buyins_chart import render_buyins_session_chart_png

from .poll_helpers import (
    _format_poll_summary as _format_poll_summary,
)
from .poll_helpers import (
    _month_bounds as _month_bounds,
)
from .poll_helpers import (
    _month_name_ru_upper as _month_name_ru_upper,
)
from .poll_helpers import (
    _parse_custom_day_input as _parse_custom_day_input,
)
from .poll_helpers import (
    _parse_iso_dates as _parse_iso_dates,
)
from .poll_helpers import (
    _parse_month_key as _parse_month_key,
)
from .poll_helpers import (
    _poll_all_days_for_month as _poll_all_days_for_month,
)
from .poll_helpers import (
    _poll_choose_text as _poll_choose_text,
)
from .poll_helpers import (
    _poll_days_for_month as _poll_days_for_month,
)
from .poll_helpers import (
    _render_poll_results_chart as _render_poll_results_chart,
)
from .receipts_helpers import (
    _download_telegram_receipt_bytes as _download_telegram_receipt_bytes,
)
from .receipts_helpers import (
    _format_payment_requisites as _format_payment_requisites,
)
from .receipts_helpers import (
    _format_unpaid_bets_lines as _format_unpaid_bets_lines,
)
from .receipts_helpers import (
    _pick_fifo_bets_to_close as _pick_fifo_bets_to_close,
)
from .receipts_helpers import (
    _telegram_external_file_id as _telegram_external_file_id,
)

router = Router()
logger = logging.getLogger(__name__)
PAYMENT_OWNER_ROW_ID = 1


def _money_kopecks_from_chips(
    *, chips: int, buyins: int, buyin_size_chips: int, buyin_size_kopecks: int
) -> int:
    if buyin_size_chips <= 0:
        return 0
    return ((int(chips) - int(buyins) * int(buyin_size_chips)) * int(buyin_size_kopecks)) // int(
        buyin_size_chips
    )


def _chips_reaction(money_kopecks: int) -> str:
    winner = [InlineText._CHIPS_REACTION_MARKER_01, InlineText._CHIPS_REACTION_MARKER_02, InlineText._CHIPS_REACTION_MARKER_03, InlineText._CHIPS_REACTION_MARKER_04, InlineText._CHIPS_REACTION_MARKER_05, InlineText._CHIPS_REACTION_MARKER_06, InlineText._CHIPS_REACTION_MARKER_07]
    loser = [InlineText._CHIPS_REACTION_MARKER_08, InlineText._CHIPS_REACTION_MARKER_09, InlineText._CHIPS_REACTION_MARKER_10, InlineText._CHIPS_REACTION_MARKER_11, InlineText._CHIPS_REACTION_MARKER_12, InlineText._CHIPS_REACTION_MARKER_13, InlineText._CHIPS_REACTION_MARKER_14]
    return random.choice(winner if int(money_kopecks) >= 0 else loser)


def _format_rub_from_kopecks(value_kopecks: int) -> str:
    rub = int(value_kopecks) // 100
    kop = abs(int(value_kopecks) % 100)
    if kop == 0:
        return str(rub)
    return f"{rub}.{kop:02d}"












def _format_waiting_players(players: list) -> str:
    waiting = [p.player_name for p in players if p.chips is None]
    if not waiting:
        return Text.admin.POKER_CHIPS_ALL_ENTERED.value
    return Text.admin.POKER_CHIPS_WAITING.value.format(
        players="\n".join(f"- {name}" for name in waiting)
    )


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
        return InlineText.REACTION_MARKER_16 if int(money_kopecks) >= 0 else InlineText._CHIPS_REACTION_MARKER_12

    buyin_size_chips = 200
    buyin_size_kopecks = 20000
    if players:
        sample = players[0]
        buyin_size_chips = int(getattr(sample, "_buyin_size_chips", buyin_size_chips))
        buyin_size_kopecks = int(getattr(sample, "_buyin_size_kopecks", buyin_size_kopecks))

    remainder = int(chips_in_game) - int(chips_entered)
    lines = [
        InlineText.BUILD_CHIPS_STATUS_TEXT_TEXT_01,
        "",
        f'{InlineText.BUILD_CHIPS_STATUS_TEXT_TEXT_02_PART_1}{chips_in_game}{InlineText.BUILD_CHIPS_STATUS_TEXT_TEXT_02_PART_2}{chips_entered}{InlineText.BUILD_CHIPS_STATUS_TEXT_TEXT_02_PART_3}{remainder}',
        "",
    ]
    for p in players:
        if p.chips is None:
            lines.append(f'{p.player_name}{InlineText.BUILD_CHIPS_STATUS_TEXT_TEXT_03_PART_1}')
        else:
            money_kopecks = money_from_chips(
                chips=int(p.chips),
                buyins=int(p.buyins),
                buyin_size_chips=buyin_size_chips,
                buyin_size_kopecks=buyin_size_kopecks,
            )
            lines.append(
                f'{p.player_name}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_08_PART_1}{int(p.chips)}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_08_PART_4}{_format_rub_from_kopecks(int(money_kopecks))}{InlineText._BUILD_CHIPS_STATUS_TEXT_MARKER_18_PART_6}{reaction(int(money_kopecks))}'
            )
    return "\n".join(lines)


async def _upsert_tg_user_chips_result(*, chat_id: int, text: str) -> None:
    from app.bot.telegram.runtime import telegram_bot

    if telegram_bot is None:
        return
    prev_msg_id = TG_USER_CHIPS_RESULT_MSG_IDS.get(int(chat_id))
    if prev_msg_id is not None:
        try:
            await telegram_bot.delete_message(chat_id=chat_id, message_id=prev_msg_id)
        except Exception:
            pass
    sent = await telegram_bot.send_message(chat_id=chat_id, text=text)
    TG_USER_CHIPS_RESULT_MSG_IDS[int(chat_id)] = int(sent.message_id)


def _build_user_chips_text(
    *, chips: int | None, money_kopecks: int | None, reaction: str | None
) -> str:
    chips_text = str(chips) if chips is not None else InlineText.BUILD_USER_CHIPS_TEXT_TEXT_01
    if money_kopecks is None or reaction is None:
        result_text = InlineText.BUILD_USER_CHIPS_TEXT_TEXT_02
    else:
        result_text = f'{_format_rub_from_kopecks(int(money_kopecks))}{InlineText._BUILD_CHIPS_STATUS_TEXT_MARKER_18_PART_6}{reaction}'
    return (
        f'{InlineText.BUILD_USER_CHIPS_TEXT_TEXT_03_PART_1}{chips_text}{InlineText.BUILD_USER_CHIPS_TEXT_TEXT_03_PART_2}{result_text}'
    )


async def _notify_admins_about_chips_entry(
    *, session, player, chips: int, money_kopecks: int
) -> None:
    from app.bot.telegram.runtime import telegram_bot

    user_repository = UserRepository(session)
    poker_repository = PokerRepository(session)
    players = await PokerDataRepository(session).list_players(date=player.date)
    player_row_ids = {int(p.player_id) for p in players}
    admins = [
        u
        for u in await user_repository.list_approved()
        if u.is_admin and int(u.row_id) in player_row_ids
    ]
    chips_entered = sum(int(p.chips or 0) for p in players)
    chips_in_game = 0
    ready = await poker_repository.get_latest_ready_for_chips_with_params()
    if ready is not None:
        poker, params = ready
        if poker.date == player.date:
            chips_in_game = sum(int(p.buyins) * int(params.buyin_size_chips) for p in players)
            for p in players:
                setattr(p, "_buyin_size_chips", int(params.buyin_size_chips))
                setattr(p, "_buyin_size_kopecks", int(params.buyin_size_kopecks))
    full_text = _build_chips_status_text(
        players=players, chips_in_game=chips_in_game, chips_entered=chips_entered
    )
    for admin in admins:
        if (
            admin.notification_platform == "tg"
            and admin.telegram_id is not None
            and telegram_bot is not None
        ):
            prev_msg_id = TG_ADMIN_CHIPS_STATUS_MSG_IDS.get(int(admin.telegram_id))
            if prev_msg_id is not None:
                try:
                    await telegram_bot.delete_message(
                        chat_id=admin.telegram_id, message_id=prev_msg_id
                    )
                except Exception:
                    pass
            sent = await telegram_bot.send_message(
                chat_id=admin.telegram_id,
                text=full_text,
                reply_markup=poker_calc_keyboard(),
            )
            TG_ADMIN_CHIPS_STATUS_MSG_IDS[int(admin.telegram_id)] = int(sent.message_id)
        elif admin.notification_platform == "vk" and admin.vk_id is not None:
            await send_vk_message(user_id=admin.vk_id, message=full_text)






















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
            InlineText.NOTIFY_ADMINS_ABOUT_ROOM_JOIN_TEXT_01
        )
    else:
        status_text = (
            InlineText.NOTIFY_ADMINS_ABOUT_ROOM_JOIN_TEXT_02
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
                reply_markup=poker_room_admin_status_keyboard(
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
            keyboard=vk_poker_room_admin_status_keyboard(
                players=[]
                if (active is not None and active[0].cashier_id is not None)
                else players,
                can_start_betting=can_start_betting,
            ),
        )
        if sent_mid is not None:
            VK_ADMIN_ROOM_STATUS_MSG_IDS[int(admin_id)] = int(sent_mid)


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
        lines.append(f'{loser['name']}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_08_PART_4}{winner['name']}{InlineText.FORMAT_ACHIEVEMENT_INFO_REPORT_TEXT_02_PART_2}{_format_rub_from_kopecks(transfer)}{InlineText._FORMAT_UNPAID_BETS_LINES_MARKER_15_PART_4}')
    return lines


async def _build_poker_history_report(*, session, target_date: date) -> str:
    poker_rows = await PokerRepository(session).list_all()
    poker = next(
        (item for item in poker_rows if item.date == target_date and not bool(item.is_going)), None
    )
    if poker is None:
        return InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_01
    params = await PokerParamRepository(session).get_by_row_id(row_id=int(poker.params_id))
    buyin_size_chips = int(params.buyin_size_chips) if params is not None else 200
    buyin_size_kopecks = int(params.buyin_size_kopecks) if params is not None else 20000
    players = await PokerDataRepository(session).list_players(date=target_date)
    if not players:
        return InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_02

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
            f'{str(item['name'])}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_03_PART_1}{int(item['buyins'])}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_03_PART_2}{int(item['chips'])}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_03_PART_3}{_format_rub_from_kopecks(int(item['money']))}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_03_PART_4}'
        )
        for item in player_rows
    ]
    poker_money_by_name = {str(item["name"]): int(item["money"]) for item in player_rows}

    winners = [name.strip() for name in str(poker.winners or "").split(",") if name.strip()]
    losers = [name.strip() for name in str(poker.loosers or "").split(",") if name.strip()]
    winner_line = ", ".join(f'{InlineText._BUILD_POKER_HISTORY_REPORT_MARKER_21_PART_1}{name}' for name in winners) if winners else InlineText._BUILD_POKER_HISTORY_REPORT_MARKER_22
    loser_line = ", ".join(f'{InlineText._BUILD_POKER_HISTORY_REPORT_MARKER_23_PART_1}{name}' for name in losers) if losers else InlineText._BUILD_POKER_HISTORY_REPORT_MARKER_24
    transfer_lines = _calculate_transfers_history(money_rows)
    bets = await BetRepository(session).list_for_poker(date=target_date)

    lines = [
        target_date.strftime("%d.%m.%Y"),
        InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_04,
        *player_lines,
        "",
        winner_line,
        loser_line,
        "",
        InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_05,
    ]
    lines.extend(transfer_lines if transfer_lines else [InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_06])
    if bets:
        lines.extend(["", InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_07])
        for bet in sorted(
            bets,
            key=lambda item: (
                -int(item.score or 0),
                -int(poker_money_by_name.get(str(item.better_name), 0)),
                int(item.row_id),
            ),
        ):
            size_mark = InlineText._BUILD_POKER_HISTORY_REPORT_MARKER_25 if int(bet.amount_kopecks or 0) >= 40000 else InlineText._BUILD_POKER_HISTORY_REPORT_MARKER_26
            score_value = int(bet.score or 0)
            score_text = f"+{score_value}" if score_value > 0 else str(score_value)
            winner_name = str(bet.winner_name or "-")
            loser_name = str(bet.loser_name or "-")
            lines.append(
                f'{bet.better_name}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_08_PART_1}{size_mark}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_08_PART_2}{winner_name}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_08_PART_3}{loser_name}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_08_PART_4}{score_text}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_08_PART_5}'
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
        title=f'{InlineText.BUILD_POKER_HISTORY_BUYINS_CHART_TEXT_01_PART_1}{target_date.strftime('%d.%m.%Y')}',
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
                marks.append(InlineText.PLAYER_MARKS_MARKER_27)
            elif player_name in losers_by_date.get(d, set()):
                marks.append(InlineText.PLAYER_MARKS_MARKER_28)
            else:
                marks.append(InlineText.PLAYER_MARKS_MARKER_29)
        return "".join(marks)

    marks_map = {name: player_marks(name) for name in players}
    last_five_games = poker_rows[-5:]
    winners_text = "\n".join(str(p.winners or "-") for p in last_five_games)
    losers_text = "\n".join(str(p.loosers or "-") for p in last_five_games)
    return marks_map, winners_text, losers_text


async def _get_telegram_user(telegram_id: int) -> User | None:
    async with SessionFactory() as session:
        repository = UserRepository(session)
        return await repository.get_by_telegram_id(telegram_id)


async def _ensure_approved_telegram_user(message: Message) -> bool:
    if message.from_user is None:
        await message.answer(
            Text.user.REGISTRATION_READ_ERROR.value, reply_markup=new_user_keyboard
        )
        return False
    user = await _get_telegram_user(message.from_user.id)
    if user is None:
        await message.answer(
            Text.user.STATUS_NEED_REGISTRATION.value, reply_markup=new_user_keyboard
        )
        return False
    if not user.is_approved:
        await message.answer(Text.user.STATUS_PENDING.value, reply_markup=new_user_keyboard)
        return False
    return True


async def _approved_tg_keyboard(user: User):
    async with SessionFactory() as session:
        active = await PokerRepository(session).get_started()
        poll_month = await PollConfigRepository(session).get_active_month()
    return main_dynamic_keyboard(
        is_admin=bool(user.is_admin),
        has_active_poker=active is not None,
        has_active_poll=poll_month is not None,
    )


async def _betting_tg_keyboard():
    return betting_dynamic_keyboard(include_make_bet=True)


async def _post_bet_tg_keyboard_for_user(*, telegram_id: int):
    async with SessionFactory() as session:
        user = await UserRepository(session).get_by_telegram_id(telegram_id)
        if user is None:
            return main_keyboard
        active = await PokerRepository(session).get_started()
        if active is None:
            return await _approved_tg_keyboard(user)
        poker, _ = active
        player = await PokerDataRepository(session).get_player(
            date=poker.date, player_id=int(user.row_id)
        )
        if player is not None:
            return room_admin_keyboard if user.is_admin else room_keyboard
        return await _approved_tg_keyboard(user)


async def _ensure_approved_telegram_callback_user(callback: CallbackQuery) -> bool:
    if callback.from_user is None:
        await callback.answer(Text.user.REGISTRATION_READ_ERROR.value, show_alert=True)
        return False
    user = await _get_telegram_user(callback.from_user.id)
    if user is None:
        await callback.answer(Text.user.STATUS_NEED_REGISTRATION.value, show_alert=True)
        return False
    if not user.is_approved:
        await callback.answer(Text.user.STATUS_PENDING.value, show_alert=True)
        return False
    return True


async def _clear_inline_keyboard(callback: CallbackQuery) -> None:
    if callback.message is None:
        return
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        return


async def _delete_message_if_possible(callback: CallbackQuery) -> None:
    if callback.message is None:
        return
    try:
        await callback.message.delete()
    except Exception:
        return


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


async def _safe_edit_reply_markup(
    message: Message | None, reply_markup: InlineKeyboardMarkup | None
) -> None:
    if message is None:
        return
    try:
        await message.edit_reply_markup(reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


async def _safe_callback_edit_reply_markup(
    callback: CallbackQuery,
    reply_markup: InlineKeyboardMarkup | None,
) -> None:
    await _safe_edit_reply_markup(callback.message, reply_markup)


async def _safe_callback_edit_text(
    callback: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    if callback.message is None:
        return
    try:
        await callback.message.edit_text(text=text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


async def _start_betting_stat_flow(*, message: Message, state: FSMContext, mode: str) -> None:
    await state.update_data(
        betstat_years=[],
        betstat_selected_ids=[],
        betstat_mode=mode,
        betstat_sort_id=None,
    )
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
        bets = await BetRepository(session).list_all()
    years = sorted({int(item.date.year) for item in bets if item.date is not None}, reverse=True)
    if not years:
        await message.answer(InlineText.START_BETTING_STAT_FLOW_TEXT_01)
        return
    await message.answer(
        Text.user.STAT_CHOOSE_YEAR.value,
        reply_markup=stat_year_keyboard(
            prefix="betstatyear", years=years, selected_years=[], page=0
        ),
    )


async def _submit_registration_request(
    *,
    message: Message,
    state: FSMContext,
    name: str,
    success_text: str,
    linked_to_user: User | None = None,
    requester_telegram_id: int | None = None,
    bank_name: str | None = None,
    tel_number: str | None = None,
    notification_platform: str | None = None,
) -> None:
    telegram_id = (
        requester_telegram_id
        if requester_telegram_id is not None
        else (message.from_user.id if message.from_user is not None else None)
    )
    if telegram_id is None:
        await message.answer(Text.user.REGISTRATION_READ_ERROR.value)
        return

    async with SessionFactory() as session:
        repository = UserRepository(session)
        use_case = RequestRegistrationUseCase(repository)

        try:
            user = await use_case.execute(
                name=name,
                telegram_id=telegram_id,
                bank_name=bank_name,
                tel_number=tel_number,
                notification_platform=notification_platform,
            )
        except UserIdentityRequiredError:
            await message.answer(Text.user.REGISTRATION_ID_ERROR.value)
            return
        except UserNameRequiredError:
            await message.answer(Text.user.REGISTRATION_EMPTY_NAME.value)
            return
        except UserAlreadyRegisteredError:
            existing_user = await repository.get_by_telegram_id(telegram_id)
            reply_markup = (
                (await _approved_tg_keyboard(existing_user))
                if existing_user and existing_user.is_approved
                else new_user_keyboard
            )
            await message.answer(Text.user.REGISTRATION_EXIST.value, reply_markup=reply_markup)
            await state.clear()
            return
        except UserRegistrationPendingError:
            await message.answer(
                Text.user.REGISTRATION_PENDING.value,
                reply_markup=new_user_keyboard,
            )
            await state.clear()
            return

        tg_admin_chat_ids = await repository.list_admin_tg_ids()
        vk_admin_ids = await repository.list_admin_vk_ids()

    await notify_admins_about_registration(
        name=name,
        telegram_id=telegram_id,
        vk_id=None,
        requester_platform="tg",
        admin_chat_ids=tg_admin_chat_ids,
        linked_to_user=linked_to_user,
        reply_markup=(
            registration_link_review_keyboard(row_id=user.row_id)
            if linked_to_user is not None
            else registration_review_keyboard(row_id=user.row_id)
        ),
    )
    await notify_vk_admins_about_registration(
        name=name,
        vk_id=None,
        telegram_id=telegram_id,
        requester_platform="tg",
        admin_ids=vk_admin_ids,
        linked_to_user=linked_to_user,
        keyboard=(
            vk_registration_link_review_keyboard(row_id=user.row_id)
            if linked_to_user is not None
            else vk_registration_review_keyboard(row_id=user.row_id)
        ),
    )
    await state.clear()
    await message.answer(
        success_text,
        reply_markup=new_user_keyboard,
    )


def _normalize_phone(value: str) -> str | None:
    digits = "".join(ch for ch in value if ch.isdigit())
    if digits.startswith("7") and len(digits) == 11:
        return f"+{digits}"
    return None


REGISTRATION_USER_STATES = {
    RegistrationState.waiting_for_played_before_answer.state,
    RegistrationState.waiting_for_new_name.state,
    RegistrationState.waiting_for_registration_platform_choice.state,
    RegistrationState.waiting_for_optional_details_action.state,
    RegistrationState.waiting_for_bank_name.state,
    RegistrationState.waiting_for_phone.state,
}
