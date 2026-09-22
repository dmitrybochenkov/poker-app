from datetime import date

from fastapi.responses import PlainTextResponse

from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.guards import is_vk_admin
from app.bot.shared.texts.inline.vk.admin import polls as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import main_dynamic_keyboard as tg_main_dynamic_keyboard
from app.bot.vk.api import (
    send_vk_message,
    send_vk_message_event_answer,
)
from app.bot.vk.keyboards import (
    main_dynamic_keyboard as vk_main_dynamic_keyboard,
)
from app.bot.vk.keyboards import (
    poll_admin_choose_keyboard,
    poll_admin_other_keyboard,
)
from app.db.repositories.poll_config_repository import PollConfigRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory

from .common import (
    HANDLER_UNMATCHED,
    _clear_event_inline_keyboard_if_possible,
    _parse_month_key,
    _shift_month,
)


async def _event_0_25(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "polladmin_other":
        async with SessionFactory() as session:
            if not await is_vk_admin(session=session, vk_id=admin_user_id):
                await send_vk_message_event_answer(
                    event_id=event_id,
                    user_id=admin_user_id,
                    peer_id=peer_id,
                    text=Text.admin.NO_RIGHTS.value,
                )
                return PlainTextResponse("ok")
        current = date.today().replace(day=1)
        months = [current, _shift_month(current, 1), _shift_month(current, 2)]
        await _clear_event_inline_keyboard_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=admin_user_id,
            message=InlineText.EVENT_0_25_TEXT_01,
            keyboard=poll_admin_other_keyboard(months=months),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _event_0_26(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "polladmin_month":
        month_key = callback_payload.get("month")
        if not isinstance(month_key, str):
            return PlainTextResponse("ok")
        async with SessionFactory() as session:
            if not await is_vk_admin(session=session, vk_id=admin_user_id):
                await send_vk_message_event_answer(
                    event_id=event_id,
                    user_id=admin_user_id,
                    peer_id=peer_id,
                    text=Text.admin.NO_RIGHTS.value,
                )
                return PlainTextResponse("ok")
            month = _parse_month_key(month_key)
            await PollConfigRepository(session).set_active_month(month=month)
            approved_users = await UserRepository(session).list_approved()
            await session.commit()
        notify_text = InlineText.EVENT_0_26_TEXT_01
        from app.bot.telegram.runtime import telegram_bot

        if telegram_bot is not None:
            for user in approved_users:
                if user.telegram_id is not None:
                    try:
                        await telegram_bot.send_message(
                            chat_id=int(user.telegram_id),
                            text=notify_text,
                            reply_markup=await tg_main_dynamic_keyboard(user),
                        )
                    except Exception:
                        pass
        for user in approved_users:
            if user.vk_id is not None:
                try:
                    await send_vk_message(
                        user_id=int(user.vk_id),
                        message=notify_text,
                        keyboard=await vk_main_dynamic_keyboard(user),
                    )
                except Exception:
                    pass
        await _clear_event_inline_keyboard_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(user_id=admin_user_id, message=f'{InlineText.EVENT_0_26_TEXT_02_PART_1}{month:%m.%Y}{InlineText.EVENT_0_26_TEXT_02_PART_2}')
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _event_0_27(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "polladmin_cancel":
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=admin_user_id,
            peer_id=peer_id,
            text=InlineText.EVENT_0_27_TEXT_01,
        )
        await _clear_event_inline_keyboard_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(user_id=admin_user_id, message=InlineText.EVENT_0_27_TEXT_02)
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _text_1_13(*, user_id, text):
    if text == Buttons.admin_main.CREATE_POLL.value:
        async with SessionFactory() as session:
            if not await is_vk_admin(session=session, vk_id=user_id):
                await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
                return PlainTextResponse("ok")
        current_month = date.today().replace(day=1)
        next_month = _shift_month(current_month, 1)
        await send_vk_message(
            user_id=user_id,
            message=InlineText.TEXT_1_13_TEXT_01,
            keyboard=poll_admin_choose_keyboard(current_month=current_month, next_month=next_month),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED
