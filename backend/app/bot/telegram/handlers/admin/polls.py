import logging
from datetime import date

from aiogram.types import CallbackQuery, Message

from app.bot.shared.texts.inline.telegram.admin import polls as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
    main_dynamic_keyboard as tg_main_dynamic_keyboard,
)
from app.bot.telegram.keyboards import (
    poll_admin_choose_keyboard,
    poll_admin_other_keyboard,
)
from app.bot.vk.api import send_vk_message
from app.bot.vk.keyboards import main_dynamic_keyboard as vk_main_dynamic_keyboard
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.poll_config_repository import PollConfigRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory

from .common import (
    _clear_inline_keyboard,
    _ensure_tg_admin_callback,
    _ensure_tg_admin_message,
    _parse_month_key,
    _safe_callback_edit_reply_markup,
    _shift_month,
)

logger = logging.getLogger(__name__)


async def create_poll_menu(message: Message) -> None:
    if message.from_user is None:
        await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
        return
    async with SessionFactory() as session:
        if not await _ensure_tg_admin_message(
            session=session, user_id=message.from_user.id, message=message
        ):
            return
    current_month = date.today().replace(day=1)
    next_month = _shift_month(current_month, 1)
    await message.answer(
        InlineText.CREATE_POLL_MENU_TEXT_01,
        reply_markup=poll_admin_choose_keyboard(current_month=current_month, next_month=next_month),
    )


async def create_poll_choose_other(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
        return
    async with SessionFactory() as session:
        if not await _ensure_tg_admin_callback(
            session=session, user_id=callback.from_user.id, callback=callback
        ):
            return
    current = date.today().replace(day=1)
    months = [current, _shift_month(current, 1), _shift_month(current, 2)]
    if callback.message is not None:
        await _safe_callback_edit_reply_markup(
            callback, reply_markup=poll_admin_other_keyboard(months=months)
        )
    await callback.answer()


async def create_poll_cancel(callback: CallbackQuery) -> None:
    if callback.message is not None:
        try:
            await callback.message.delete()
        except Exception:
            await _clear_inline_keyboard(callback)
            await callback.message.answer(InlineText.CREATE_POLL_CANCEL_TEXT_01)
            await callback.answer(InlineText.CREATE_POLL_CANCEL_TEXT_02)
            return
        await callback.message.answer(InlineText.CREATE_POLL_CANCEL_TEXT_03)
    await callback.answer(InlineText.CREATE_POLL_CANCEL_TEXT_04)


async def create_poll_set_month(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
        return
    async with SessionFactory() as session:
        if not await _ensure_tg_admin_callback(
            session=session, user_id=callback.from_user.id, callback=callback
        ):
            return
        month = _parse_month_key(str(callback.data).split(":", 1)[1])
        await PollConfigRepository(session).set_active_month(month=month)
        approved_users = await UserRepository(session).list_approved()
        has_active_poker = await PokerRepository(session).get_started() is not None
        await session.commit()
    notify_text = InlineText.CREATE_POLL_SET_MONTH_TEXT_01
    from app.bot.telegram.runtime import telegram_bot

    if telegram_bot is not None:
        for user in approved_users:
            if user.telegram_id is not None:
                try:
                    await telegram_bot.send_message(
                        chat_id=int(user.telegram_id),
                        text=notify_text,
                        reply_markup=tg_main_dynamic_keyboard(
                            is_admin=bool(user.is_admin),
                            has_active_poker=has_active_poker,
                            has_active_poll=True,
                        ),
                    )
                except Exception:
                    logger.exception(
                        "Poll invitation delivery failed: platform=tg recipient_id=%s",
                        user.telegram_id,
                    )
    for user in approved_users:
        if user.vk_id is not None:
            try:
                await send_vk_message(
                    user_id=int(user.vk_id),
                    message=notify_text,
                    keyboard=vk_main_dynamic_keyboard(
                        is_admin=bool(user.is_admin),
                        has_active_poker=has_active_poker,
                        has_active_poll=True,
                    ),
                )
            except Exception:
                logger.exception(
                    "Poll invitation delivery failed: platform=vk recipient_id=%s",
                    user.vk_id,
                )
    if callback.message is not None:
        try:
            await callback.message.delete()
        except Exception:
            await _clear_inline_keyboard(callback)
    if callback.message is not None:
        await callback.message.answer(f'{InlineText.CREATE_POLL_SET_MONTH_TEXT_02_PART_1}{month:%m.%Y}{InlineText.CREATE_POLL_SET_MONTH_TEXT_02_PART_2}')
    await callback.answer(InlineText.CREATE_POLL_SET_MONTH_TEXT_03)
