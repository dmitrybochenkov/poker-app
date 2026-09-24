import logging
import random
import re
from datetime import date, timezone
from zoneinfo import ZoneInfo

from app.application.exceptions import (
    UserAlreadyRegisteredError,
    UserIdentityRequiredError,
    UserNameRequiredError,
    UserRegistrationPendingError,
)
from app.application.use_cases.user.request_registration import RequestRegistrationUseCase
from app.bot.shared.chips_runtime import (
    TG_ADMIN_ROOM_STATUS_MSG_IDS,
    VK_ADMIN_ROOM_STATUS_MSG_IDS,
)
from app.bot.shared.texts.inline.vk.user import common as InlineText
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
from .poll_helpers import (
    _shift_month as _shift_month,
)
from .receipts_helpers import (
    _download_vk_receipt_bytes as _download_vk_receipt_bytes,
)
from .receipts_helpers import (
    _extract_vk_attachment_url as _extract_vk_attachment_url,
)
from .receipts_helpers import (
    _extract_vk_external_file_id as _extract_vk_external_file_id,
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

STAT_SNACKBAR = InlineText.MODULE_TEXT_01
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






def _format_rub_from_kopecks(value_kopecks: int) -> str:
    rub = int(value_kopecks) // 100
    kop = abs(int(value_kopecks) % 100)
    if kop == 0:
        return str(rub)
    return f"{rub}.{kop:02d}"






































def _strip_html_tags(text: str) -> str:
    return text.replace("<b>", "").replace("</b>", "")


def _normalize_vk_button_text(text: str) -> str:
    normalized = " ".join((text or "").replace(InlineText._NORMALIZE_VK_BUTTON_TEXT_MARKER_02, "").split()).strip().lower()
    normalized = re.sub(InlineText.NORMALIZE_VK_BUTTON_TEXT_TEXT_01, "", normalized, flags=re.IGNORECASE)
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
    winner = [InlineText._CHIPS_REACTION_MARKER_03, InlineText._CHIPS_REACTION_MARKER_04, InlineText._CHIPS_REACTION_MARKER_05, InlineText._CHIPS_REACTION_MARKER_06, InlineText._CHIPS_REACTION_MARKER_07, InlineText._CHIPS_REACTION_MARKER_08, InlineText._CHIPS_REACTION_MARKER_09]
    loser = [InlineText._CHIPS_REACTION_MARKER_10, InlineText._CHIPS_REACTION_MARKER_11, InlineText._CHIPS_REACTION_MARKER_12, InlineText._CHIPS_REACTION_MARKER_13, InlineText._CHIPS_REACTION_MARKER_14, InlineText._CHIPS_REACTION_MARKER_15, InlineText._CHIPS_REACTION_MARKER_16]
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
        return InlineText.REACTION_MARKER_17 if int(money_kopecks) >= 0 else InlineText._CHIPS_REACTION_MARKER_14

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
                f'{p.player_name}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_08_PART_1}{int(p.chips)}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_08_PART_4}{_format_rub_from_kopecks(int(money_kopecks))}{InlineText._BUILD_CHIPS_STATUS_TEXT_MARKER_19_PART_6}{reaction(int(money_kopecks))}'
            )
    return "\n".join(lines)


def _build_user_chips_text(
    *, chips: int | None, money_kopecks: int | None, reaction: str | None
) -> str:
    chips_text = str(chips) if chips is not None else InlineText.BUILD_USER_CHIPS_TEXT_TEXT_01
    if money_kopecks is None or reaction is None:
        result_text = InlineText.BUILD_USER_CHIPS_TEXT_TEXT_02
    else:
        result_text = f'{_format_rub_from_kopecks(int(money_kopecks))}{InlineText._BUILD_CHIPS_STATUS_TEXT_MARKER_19_PART_6}{reaction}'
    return (
        f'{InlineText.BUILD_USER_CHIPS_TEXT_TEXT_03_PART_1}{chips_text}{InlineText.BUILD_USER_CHIPS_TEXT_TEXT_03_PART_2}{result_text}'
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
        lines.append(f'{loser['name']}{InlineText.BUILD_POKER_HISTORY_REPORT_TEXT_08_PART_4}{winner['name']}{InlineText.FORMAT_ACHIEVEMENT_INFO_REPORT_TEXT_02_PART_2}{_format_rub_from_kopecks(transfer)}{InlineText._FORMAT_UNPAID_BETS_LINES_MARKER_01_PART_4}')
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
    winner_line = ", ".join(f'{InlineText._BUILD_POKER_HISTORY_REPORT_MARKER_22_PART_1}{name}' for name in winners) if winners else InlineText._BUILD_POKER_HISTORY_REPORT_MARKER_23
    loser_line = ", ".join(f'{InlineText._BUILD_POKER_HISTORY_REPORT_MARKER_24_PART_1}{name}' for name in losers) if losers else InlineText._BUILD_POKER_HISTORY_REPORT_MARKER_25
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
            size_mark = InlineText._BUILD_POKER_HISTORY_REPORT_MARKER_26 if int(bet.amount_kopecks or 0) >= 40000 else InlineText._BUILD_POKER_HISTORY_REPORT_MARKER_27
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
                marks.append(InlineText.PLAYER_MARKS_MARKER_28)
            elif player_name in losers_by_date.get(d, set()):
                marks.append(InlineText.PLAYER_MARKS_MARKER_29)
            else:
                marks.append(InlineText.PLAYER_MARKS_MARKER_30)
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
