import logging
import random
from datetime import date, timezone
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from app.bot.shared.chips_runtime import (
    TG_ADMIN_CHIPS_STATUS_MSG_IDS,
    TG_ADMIN_ROOM_STATUS_MSG_IDS,
    TG_USER_CHIPS_RESULT_MSG_IDS,
    VK_ADMIN_ROOM_STATUS_MSG_IDS,
)
from app.bot.shared.guards import is_tg_admin
from app.bot.shared.texts.inline.telegram.admin import common as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
    betting_keyboard,
    main_admin_entry_keyboard,
    main_keyboard,
    poker_calc_keyboard,
    poker_room_admin_status_keyboard,
)
from app.bot.telegram.keyboards import (
    main_dynamic_keyboard as tg_main_dynamic_keyboard,
)
from app.bot.vk.api import (
    delete_vk_message_by_id,
    pin_vk_message_by_id,
    send_vk_message,
    send_vk_message_with_id,
    unpin_vk_message,
)
from app.bot.vk.keyboards import betting_keyboard as vk_betting_keyboard
from app.bot.vk.keyboards import main_dynamic_keyboard as vk_main_dynamic_keyboard
from app.bot.vk.keyboards import main_keyboard as vk_main_keyboard
from app.bot.vk.keyboards import (
    poker_room_admin_status_keyboard as vk_poker_room_admin_status_keyboard,
)
from app.db.repositories.buyin_data_repository import BuyinDataRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory
from app.services.buyins_chart import render_buyins_session_chart_png

router = Router()
TG_BUYIN_NOTIFY_CASHIER_ONLY: set[tuple[int, int]] = set()
TG_MANUAL_RECEIPT_SELECTIONS: dict[tuple[int, int], set[int]] = {}
logger = logging.getLogger(__name__)


async def _safe_callback_edit_reply_markup(
    callback: CallbackQuery,
    reply_markup: InlineKeyboardMarkup | None,
) -> None:
    if callback.message is None:
        return
    try:
        await callback.message.edit_reply_markup(reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


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


async def _start_betting_flow(*, admin_tg_id: int) -> str:
    async with SessionFactory() as session:
        user_repository = UserRepository(session)
        poker_repository = PokerRepository(session)
        active = await poker_repository.get_started()
        if active is None:
            return Text.admin.POKER_ACTIVE_NOT_FOUND.value
        poker, _ = active
        if poker.is_ready_for_chips_entering:
            return Text.user.FINISH_CHIPS_NOT_READY.value
        if poker.is_bettable:
            return Text.admin.BETTING_ALREADY_OPEN.value
        await poker_repository.start_betting(poker)
        tg_user_ids = await user_repository.list_approved_tg_ids()
        vk_user_ids = await user_repository.list_approved_vk_ids()

    from app.bot.telegram.runtime import telegram_bot

    if telegram_bot is not None:
        for chat_id, message_id in list(TG_ADMIN_ROOM_STATUS_MSG_IDS.items()):
            try:
                await telegram_bot.unpin_chat_message(
                    chat_id=int(chat_id), message_id=int(message_id)
                )
            except Exception:
                pass
            try:
                await telegram_bot.delete_message(chat_id=int(chat_id), message_id=int(message_id))
            except Exception:
                pass
    for peer_id, message_id in list(VK_ADMIN_ROOM_STATUS_MSG_IDS.items()):
        try:
            await unpin_vk_message(peer_id=int(peer_id))
        except Exception:
            pass
        try:
            await delete_vk_message_by_id(peer_id=int(peer_id), message_id=int(message_id))
        except Exception:
            pass
    TG_ADMIN_ROOM_STATUS_MSG_IDS.clear()
    VK_ADMIN_ROOM_STATUS_MSG_IDS.clear()
    if telegram_bot is not None:
        for user_id in tg_user_ids:
            try:
                await telegram_bot.send_message(
                    chat_id=user_id,
                    text=Text.user.START_BETTING.value,
                    reply_markup=betting_keyboard,
                )
            except Exception:
                logger.exception("Failed to announce betting start to Telegram user %s", user_id)
    for user_id in vk_user_ids:
        try:
            await send_vk_message(
                user_id=user_id,
                message=Text.user.START_BETTING.value,
                keyboard=vk_betting_keyboard,
            )
        except Exception:
            logger.exception("Failed to announce betting start to VK user %s", user_id)
    return Text.admin.BETTING_START_SUCCESS.value


async def _refresh_admin_room_status(*, session) -> None:
    from app.bot.telegram.runtime import telegram_bot

    user_repository = UserRepository(session)
    poker_repository = PokerRepository(session)
    poker_data_repository = PokerDataRepository(session)
    active = await poker_repository.get_started()
    if active is None:
        return
    poker, _ = active
    players = await poker_data_repository.list_players(date=poker.date)
    can_start_betting = bool(
        poker.cashier_id is not None
        and not bool(poker.is_bettable)
        and not bool(poker.is_ready_for_chips_entering)
    )
    if poker.cashier_id is None:
        status_text = (
            InlineText.REFRESH_ADMIN_ROOM_STATUS_TEXT_01
        )
    else:
        status_text = (
            InlineText.REFRESH_ADMIN_ROOM_STATUS_TEXT_02
        )
    player_row_ids = {int(p.player_id) for p in players}
    admins = [
        u
        for u in await user_repository.list_approved()
        if u.is_admin and int(u.row_id) in player_row_ids
    ]
    tg_admins = [int(u.telegram_id) for u in admins if u.telegram_id is not None]
    vk_admins = [int(u.vk_id) for u in admins if u.vk_id is not None]
    if telegram_bot is not None:
        for admin_id in tg_admins:
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
                    players=[] if poker.cashier_id is not None else players,
                    can_start_betting=can_start_betting,
                ),
            )
            try:
                await telegram_bot.pin_chat_message(
                    chat_id=int(admin_id),
                    message_id=int(sent.message_id),
                    disable_notification=True,
                )
            except Exception:
                pass
            TG_ADMIN_ROOM_STATUS_MSG_IDS[int(admin_id)] = int(sent.message_id)
    for admin_id in vk_admins:
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
                players=[] if poker.cashier_id is not None else players,
                can_start_betting=can_start_betting,
            ),
        )
        if sent_mid is not None:
            try:
                await pin_vk_message_by_id(peer_id=int(admin_id), message_id=int(sent_mid))
            except Exception:
                pass
            VK_ADMIN_ROOM_STATUS_MSG_IDS[int(admin_id)] = int(sent_mid)


def _shift_month(value: date, delta: int) -> date:
    total = value.year * 12 + (value.month - 1) + delta
    year = total // 12
    month = total % 12 + 1
    return date(year, month, 1)


def _parse_month_key(value: str) -> date:
    year_s, month_s = value.split("-")
    return date(int(year_s), int(month_s), 1)


async def _clear_inline_keyboard(callback: CallbackQuery) -> None:
    if callback.message is None:
        return
    try:
        await _safe_callback_edit_reply_markup(callback, reply_markup=None)
    except Exception:
        return


def _format_rub_from_kopecks(value_kopecks: int) -> str:
    rub = int(value_kopecks) // 100
    kop = int(value_kopecks) % 100
    if kop == 0:
        return str(rub)
    return f"{rub}.{kop:02d}"


def _get_reaction(mode: str) -> str:
    winner = [InlineText._GET_REACTION_MARKER_01, InlineText._GET_REACTION_MARKER_02, InlineText._GET_REACTION_MARKER_03, InlineText._GET_REACTION_MARKER_04, InlineText._GET_REACTION_MARKER_05, InlineText._GET_REACTION_MARKER_06, InlineText._GET_REACTION_MARKER_07]
    loser = [InlineText._GET_REACTION_MARKER_08, InlineText._GET_REACTION_MARKER_09, InlineText._GET_REACTION_MARKER_10, InlineText._GET_REACTION_MARKER_11, InlineText._GET_REACTION_MARKER_12, InlineText._GET_REACTION_MARKER_13, InlineText._GET_REACTION_MARKER_14]
    return random.choice(winner if mode == "winner" else loser)


def _calculate_transfers(money_rows: list[dict[str, int | str]]) -> list[str]:
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
        lines.append(f'{loser['name']}{InlineText._CALCULATE_TRANSFERS_MARKER_15_PART_2}{winner['name']}{InlineText._CALCULATE_TRANSFERS_MARKER_15_PART_4}{_format_rub_from_kopecks(transfer)}{InlineText._CALCULATE_TRANSFERS_MARKER_15_PART_6}')
    return lines


def _split_names_csv(value: str | None) -> set[str]:
    if not value:
        return set()
    return {item.strip() for item in str(value).split(",") if item.strip()}


def _winner_mark(*, is_streak: bool) -> str:
    return InlineText._WINNER_MARK_MARKER_16 if is_streak else InlineText._WINNER_MARK_MARKER_17


def _bet_mark(*, amount_kopecks: int, guessed_winner: bool, guessed_loser: bool) -> str:
    size_mark = InlineText._BET_MARK_MARKER_18 if int(amount_kopecks) >= 40000 else InlineText._BET_MARK_MARKER_19
    if guessed_winner and guessed_loser:
        return f'{size_mark}{InlineText._BET_MARK_MARKER_20_PART_2}'
    if guessed_winner or guessed_loser:
        return f'{size_mark}{InlineText._BET_MARK_MARKER_21_PART_2}'
    return size_mark


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
        return InlineText.REACTION_MARKER_22 if int(money_kopecks) >= 0 else InlineText._GET_REACTION_MARKER_12

    # Fallback values are replaced by real params in _upsert_tg_admin_chips_status.
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
                f'{p.player_name}{InlineText.NOTIFY_ADMINS_ABOUT_REMOVED_PLAYER_TEXT_01_PART_2}{int(p.chips)}{InlineText._BUILD_CHIPS_STATUS_TEXT_MARKER_24_PART_4}{_format_rub_from_kopecks(int(money_kopecks))}{InlineText._BUILD_CHIPS_STATUS_TEXT_MARKER_24_PART_6}{reaction(int(money_kopecks))}'
            )
    return "\n".join(lines)


async def _build_poker_buyins_session_chart(*, session, poker_date: date) -> bytes | None:
    events = await BuyinDataRepository(session).list_for_date(poker_date=poker_date)
    if not events:
        return None

    cumulative: dict[str, int] = {}
    points: dict[str, list[tuple[int, int]]] = {}
    x_labels: list[str] = []
    msk_tz = ZoneInfo("Europe/Moscow")

    for idx, event in enumerate(events):
        if event.created_at is not None:
            event_dt = event.created_at
            if event_dt.tzinfo is None:
                event_dt = event_dt.replace(tzinfo=timezone.utc)
            event_dt_msk = event_dt.astimezone(msk_tz)
            x_labels.append(event_dt_msk.strftime("%H:%M"))
        else:
            x_labels.append(str(idx + 1))
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
        title=f'{InlineText.BUILD_POKER_BUYINS_SESSION_CHART_TEXT_01_PART_1}{poker_date.strftime('%d.%m.%Y')}',
        series=points,
        x_labels=x_labels,
        legend_value_mode="max",
    )


async def _upsert_tg_admin_chips_status(*, session, poker_date) -> None:
    from app.bot.telegram.runtime import telegram_bot

    if telegram_bot is None:
        return
    user_repository = UserRepository(session)
    poker_repository = PokerRepository(session)
    poker_data_repository = PokerDataRepository(session)
    players = await poker_data_repository.list_players(date=poker_date)
    chips_entered = sum(int(p.chips or 0) for p in players)
    chips_in_game = 0
    ready = await poker_repository.get_latest_ready_for_chips_with_params()
    if ready is not None:
        poker, params = ready
        if poker.date == poker_date:
            chips_in_game = sum(int(p.buyins) * int(params.buyin_size_chips) for p in players)
            for p in players:
                setattr(p, "_buyin_size_chips", int(params.buyin_size_chips))
                setattr(p, "_buyin_size_kopecks", int(params.buyin_size_kopecks))
    text = _build_chips_status_text(
        players=players, chips_in_game=chips_in_game, chips_entered=chips_entered
    )
    player_row_ids = {int(p.player_id) for p in players}
    admins = [
        u
        for u in await user_repository.list_approved()
        if u.is_admin and int(u.row_id) in player_row_ids
    ]
    for admin in admins:
        if admin.notification_platform != "tg" or admin.telegram_id is None:
            continue
        prev_msg_id = TG_ADMIN_CHIPS_STATUS_MSG_IDS.get(int(admin.telegram_id))
        if prev_msg_id is not None:
            try:
                await telegram_bot.delete_message(chat_id=admin.telegram_id, message_id=prev_msg_id)
            except Exception:
                pass
        sent = await telegram_bot.send_message(
            chat_id=admin.telegram_id,
            text=text,
            reply_markup=poker_calc_keyboard(),
        )
        TG_ADMIN_CHIPS_STATUS_MSG_IDS[int(admin.telegram_id)] = int(sent.message_id)


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
        result_text = f'{_format_rub_from_kopecks(int(money_kopecks))}{InlineText._BUILD_CHIPS_STATUS_TEXT_MARKER_24_PART_6}{reaction}'
    return (
        f'{InlineText.BUILD_USER_CHIPS_TEXT_TEXT_03_PART_1}{chips_text}{InlineText.BUILD_USER_CHIPS_TEXT_TEXT_03_PART_2}{result_text}'
    )


async def _clear_tg_admin_chips_calc_buttons() -> None:
    from app.bot.telegram.runtime import telegram_bot

    if telegram_bot is None:
        TG_ADMIN_CHIPS_STATUS_MSG_IDS.clear()
        return
    for chat_id, message_id in list(TG_ADMIN_CHIPS_STATUS_MSG_IDS.items()):
        try:
            await telegram_bot.edit_message_reply_markup(
                chat_id=int(chat_id),
                message_id=int(message_id),
                reply_markup=None,
            )
        except Exception:
            pass
    TG_ADMIN_CHIPS_STATUS_MSG_IDS.clear()


async def _notify_players_about_finish(*, players: list) -> None:
    from app.bot.telegram.runtime import telegram_bot

    async with SessionFactory() as session:
        user_repository = UserRepository(session)
        for player in players:
            user = await user_repository.get_by_row_id(int(player.player_id))
            if user is None or user.notification_platform is None or bool(user.is_admin):
                continue

            text = _build_user_chips_text(chips=None, money_kopecks=None, reaction=None)
            if (
                user.notification_platform == "tg"
                and user.telegram_id is not None
                and telegram_bot is not None
            ):
                await telegram_bot.send_message(
                    chat_id=user.telegram_id,
                    text=text,
                    reply_markup=await tg_main_dynamic_keyboard(user),
                )
            elif user.notification_platform == "vk" and user.vk_id is not None:
                await send_vk_message(
                    user_id=user.vk_id,
                    message=text,
                    keyboard=await vk_main_dynamic_keyboard(user),
                )


async def _notify_about_buyin(
    *,
    session,
    poker,
    updated_player,
    buyins_count: int,
    notify_admins: bool = True,
) -> None:
    from app.bot.telegram.runtime import telegram_bot

    user_repository = UserRepository(session)
    cashier = None
    if poker.cashier_id is not None:
        cashier = await user_repository.get_by_row_id(int(poker.cashier_id))

    text = (
        f'{InlineText.NOTIFY_ABOUT_BUYIN_TEXT_01_PART_1}{updated_player.player_name}{InlineText.NOTIFY_ABOUT_BUYIN_TEXT_01_PART_2}{buyins_count}{InlineText.NOTIFY_ABOUT_BUYIN_TEXT_01_PART_3}{updated_player.buyins}{InlineText.NOTIFY_ABOUT_BUYIN_TEXT_01_PART_4}'
    )
    if cashier is not None:
        if (
            cashier.notification_platform == "tg"
            and cashier.telegram_id is not None
            and telegram_bot is not None
        ):
            await telegram_bot.send_message(chat_id=cashier.telegram_id, text=text)
        elif cashier.notification_platform == "vk" and cashier.vk_id is not None:
            await send_vk_message(user_id=cashier.vk_id, message=text)

    if notify_admins:
        recipients: dict[int, object] = {}
        players = await PokerDataRepository(session).list_players(date=poker.date)
        player_row_ids = {int(p.player_id) for p in players}
        admins = await user_repository.list_approved()
        for user in admins:
            if user.is_admin and int(user.row_id) in player_row_ids:
                recipients[int(user.row_id)] = user
        if cashier is not None:
            recipients.pop(int(cashier.row_id), None)
        for user in recipients.values():
            if (
                user.notification_platform == "tg"
                and user.telegram_id is not None
                and telegram_bot is not None
            ):
                await telegram_bot.send_message(chat_id=user.telegram_id, text=text)
            elif user.notification_platform == "vk" and user.vk_id is not None:
                await send_vk_message(user_id=user.vk_id, message=text)

    player_user = await user_repository.get_by_row_id(int(updated_player.player_id))
    if player_user is not None and player_user.notification_platform is not None:
        player_text = f'{InlineText.NOTIFY_ABOUT_BUYIN_TEXT_02_PART_1}{buyins_count}{InlineText.NOTIFY_ABOUT_BUYIN_TEXT_02_PART_2}{updated_player.buyins}{InlineText.NOTIFY_ABOUT_BUYIN_TEXT_02_PART_3}'
        if (
            player_user.notification_platform == "tg"
            and player_user.telegram_id is not None
            and telegram_bot is not None
        ):
            await telegram_bot.send_message(chat_id=player_user.telegram_id, text=player_text)
        elif player_user.notification_platform == "vk" and player_user.vk_id is not None:
            await send_vk_message(user_id=player_user.vk_id, message=player_text)


async def _notify_admins_about_removed_player(
    *, session, poker_date, player_name: str, buyins: int
) -> None:
    from app.bot.telegram.runtime import telegram_bot

    user_repository = UserRepository(session)
    players = await PokerDataRepository(session).list_players(date=poker_date)
    player_row_ids = {int(p.player_id) for p in players}
    admins = [
        u
        for u in await user_repository.list_approved()
        if u.is_admin and int(u.row_id) in player_row_ids
    ]
    text = f'{InlineText.NOTIFY_ADMINS_ABOUT_REMOVED_PLAYER_TEXT_01_PART_1}{player_name}{InlineText.NOTIFY_ADMINS_ABOUT_REMOVED_PLAYER_TEXT_01_PART_2}{int(buyins)}'
    for user in admins:
        if (
            user.notification_platform == "tg"
            and user.telegram_id is not None
            and telegram_bot is not None
        ):
            await telegram_bot.send_message(chat_id=user.telegram_id, text=text)
        elif user.notification_platform == "vk" and user.vk_id is not None:
            await send_vk_message(user_id=user.vk_id, message=text)


async def _notify_user_removed_from_room(*, user) -> None:
    from app.bot.telegram.runtime import telegram_bot

    if user.telegram_id is not None and telegram_bot is not None:
        await telegram_bot.send_message(
            chat_id=user.telegram_id,
            text=Text.user.ROOM_REMOVED_BY_ADMIN.value,
            reply_markup=main_admin_entry_keyboard if user.is_admin else main_keyboard,
        )
    if user.vk_id is not None:
        await send_vk_message(
            user_id=user.vk_id,
            message=Text.user.ROOM_REMOVED_BY_ADMIN.value,
            keyboard=vk_main_keyboard if not user.is_admin else vk_main_keyboard,
        )


async def _notify_user_unbanned_for_room(*, user) -> None:
    from app.bot.telegram.runtime import telegram_bot

    if (
        user.notification_platform == "tg"
        and user.telegram_id is not None
        and telegram_bot is not None
    ):
        await telegram_bot.send_message(
            chat_id=user.telegram_id, text=Text.user.ROOM_UNBANNED_BY_ADMIN.value
        )
    elif user.notification_platform == "vk" and user.vk_id is not None:
        await send_vk_message(user_id=user.vk_id, message=Text.user.ROOM_UNBANNED_BY_ADMIN.value)


async def _ensure_tg_admin_message(*, session, user_id: int, message: Message) -> bool:
    if not await is_tg_admin(session=session, telegram_id=user_id):
        await message.answer(Text.admin.NO_RIGHTS.value)
        return False
    return True


async def _ensure_tg_admin_callback(*, session, user_id: int, callback: CallbackQuery) -> bool:
    if not await is_tg_admin(session=session, telegram_id=user_id):
        await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
        return False
    return True
