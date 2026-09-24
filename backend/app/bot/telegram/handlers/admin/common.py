import logging
from datetime import date

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from app.bot.shared.guards import is_tg_admin
from app.bot.shared.texts.texts import Text


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
