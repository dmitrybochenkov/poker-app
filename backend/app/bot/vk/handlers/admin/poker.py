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
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.poker_room_denied_repository import PokerRoomDeniedRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory

from .common import (
    HANDLER_UNMATCHED,
    _clear_event_inline_keyboard_if_possible,
    _notify_players_about_finish,
    _upsert_vk_admin_chips_status,
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


async def handle_admin_room_finish_poker_text(*, user_id, text):
    if text == Buttons.admin_room.FINISH_POKER.value:
        async with SessionFactory() as session:
            user_repository = UserRepository(session)
            if not await is_vk_admin(session=session, vk_id=user_id):
                await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
                return PlainTextResponse("ok")
            poker_repository = PokerRepository(session)
            active = await poker_repository.get_started()
            if active is None:
                await send_vk_message(
                    user_id=user_id, message=Text.admin.POKER_ACTIVE_NOT_FOUND.value
                )
                return PlainTextResponse("ok")
            poker, params = active
            poker_data_repository = PokerDataRepository(session)
            players = await poker_data_repository.list_players(date=poker.date)
            await poker_repository.finish(poker)
            await PokerRoomDeniedRepository(session).clear_all()
        await _notify_players_about_finish(players=players)
        await send_vk_message(user_id=user_id, message=Text.admin.POKER_FINISH_SUCCESS.value)
        if players:
            async with SessionFactory() as session:
                await _upsert_vk_admin_chips_status(session=session, poker_date=players[0].date)
        return PlainTextResponse("ok")
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
            user_repository = UserRepository(session)
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
