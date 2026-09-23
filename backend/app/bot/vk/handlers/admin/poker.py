from fastapi.responses import PlainTextResponse

from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.guards import is_vk_admin
from app.bot.shared.texts.inline.vk.admin import poker as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.vk.api import (
    send_vk_message,
    send_vk_message_event_answer,
)
from app.bot.vk.keyboards import (
    admin_room_correct_keyboard,
    admin_room_keyboard,
    room_admin_keyboard,
)
from app.db.session import SessionFactory

from .common import (
    HANDLER_UNMATCHED,
    _clear_event_inline_keyboard_if_possible,
)


async def handle_poker_start_betting_inline_event(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "poker_start_betting_inline":
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=admin_user_id,
            peer_id=peer_id,
            text=InlineText.EVENT_0_29_TEXT_01,
        )
        await _clear_event_inline_keyboard_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        return await handle_admin_text_commands(
            user_id=admin_user_id, text=Buttons.admin_room.START_BETTING.value
        )
    return HANDLER_UNMATCHED


async def handle_admin_room_correct_poker_text(*, user_id, text):
    if text == Buttons.admin_room.CORRECT_POKER.value:
        async with SessionFactory() as session:
            if not await is_vk_admin(session=session, vk_id=user_id):
                await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
                return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id, message=InlineText.TEXT_1_14_TEXT_01, keyboard=admin_room_correct_keyboard
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_admin_room_correct_to_admin_room_text(*, user_id, text):
    if text == Buttons.admin_room_correct.TO_ADMIN_ROOM.value:
        async with SessionFactory() as session:
            if not await is_vk_admin(session=session, vk_id=user_id):
                await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
                return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id, message=Text.admin.ADMIN_PANEL.value, keyboard=admin_room_keyboard
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_admin_room_to_room_text(*, user_id, text):
    if text == Buttons.admin_room.TO_ROOM.value:
        async with SessionFactory() as session:
            if not await is_vk_admin(session=session, vk_id=user_id):
                await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
                return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id,
            message=InlineText.TEXT_1_21_TEXT_01,
            keyboard=room_admin_keyboard,
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED
