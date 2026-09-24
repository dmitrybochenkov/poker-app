import logging
from datetime import date

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from app.bot.shared.chips_runtime import (
    TG_ADMIN_ROOM_STATUS_MSG_IDS,
    VK_ADMIN_ROOM_STATUS_MSG_IDS,
)
from app.bot.shared.guards import is_tg_admin
from app.bot.shared.texts.inline.telegram.admin import common as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
    main_admin_entry_keyboard,
    main_keyboard,
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
)
from app.bot.vk.keyboards import main_dynamic_keyboard as vk_main_dynamic_keyboard
from app.bot.vk.keyboards import main_keyboard as vk_main_keyboard
from app.bot.vk.keyboards import (
    poker_room_admin_status_keyboard as vk_poker_room_admin_status_keyboard,
)
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory

from .poker_helpers import _build_user_chips_text

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
                    reply_markup=tg_main_dynamic_keyboard(
                        is_admin=False,
                        has_active_poker=False,
                        has_active_poll=False,
                    ),
                )
            elif user.notification_platform == "vk" and user.vk_id is not None:
                await send_vk_message(
                    user_id=user.vk_id,
                    message=text,
                    keyboard=vk_main_dynamic_keyboard(
                        is_admin=False,
                        has_active_poker=False,
                        has_active_poll=False,
                    ),
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
