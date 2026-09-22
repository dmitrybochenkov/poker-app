from fastapi.responses import PlainTextResponse

from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.texts.inline.vk.user import navigation as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.vk.api import (
    send_vk_message,
)
from app.bot.vk.keyboards import (
    admin_main_keyboard,
    betting_info_keyboard,
    main_info_keyboard,
    new_user_keyboard,
    poker_info_keyboard,
    poker_keyboard,
    poll_menu_keyboard,
)
from app.bot.vk.state import (
    WAITING_FOR_BET_PAYMENT_RECEIPT,
    vk_user_states,
)
from app.db.repositories.poll_config_repository import PollConfigRepository
from app.db.session import SessionFactory

from .common import (
    HANDLER_UNMATCHED,
    _approved_vk_keyboard,
    _betting_vk_keyboard,
    _get_vk_user,
)


async def handle_navigation_access_check_text(*, user_id, text, raw_message):
    if text in {
        Buttons.main.BETTING.value,
        Buttons.main.INFO.value,
        Buttons.main.NEXT_POKER_DATE.value,
        Buttons.poll_menu.VOTE.value,
        Buttons.poll_menu.RESULTS.value,
        Buttons.poll_menu.TO_MAIN.value,
        Buttons.betting.TO_MAIN.value,
        Buttons.betting.CURRENT_TOURS.value,
        Buttons.betting_current.REG_TOURNAMENT.value,
        Buttons.betting_current.YEAR_TOURNAMENT.value,
        Buttons.betting_current.TO_MAIN.value,
        Buttons.betting.BETTING_STAT.value,
        Buttons.bettingInfo.BETTING_RULES.value,
        Buttons.bettingInfo.BETTING_ACH_INFO.value,
        Buttons.bettingInfo.BETTING_STAT_INFO.value,
        Buttons.betting.MAKE_BET.value,
        Buttons.betting.PAY_BET.value,
        Buttons.main.ROOM.value,
        Buttons.room.STATUS.value,
        Buttons.main.ADMIN.value,
        Buttons.admin_main.TO_MAIN.value,
        Buttons.main.POKER.value,
        Buttons.poker.TO_MAIN.value,
        Buttons.pokerInfo.POKER_ACH_INFO.value,
        Buttons.pokerInfo.POKER_STAT_INFO.value,
        Buttons.poker.HISTORY.value,
        Buttons.poker.POKER_STAT.value,
    }:
        user = await _get_vk_user(user_id)
        if user is None:
            await send_vk_message(
                user_id=user_id,
                message=Text.user.STATUS_NEED_REGISTRATION.value,
                keyboard=new_user_keyboard,
            )
            return PlainTextResponse("ok")
        if not user.is_approved:
            await send_vk_message(
                user_id=user_id, message=Text.user.STATUS_PENDING.value, keyboard=new_user_keyboard
            )
            return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_main_admin_text(*, user_id, text, raw_message):
    if text == Buttons.main.ADMIN.value:
        user = await _get_vk_user(user_id)
        if user is None or not user.is_approved:
            await send_vk_message(
                user_id=user_id, message=Text.user.STATUS_PENDING.value, keyboard=new_user_keyboard
            )
            return PlainTextResponse("ok")
        if not user.is_admin:
            await send_vk_message(
                user_id=user_id,
                message=Text.admin.NO_RIGHTS.value,
                keyboard=await _approved_vk_keyboard(user),
            )
            return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id, message=Text.admin.ADMIN_PANEL.value, keyboard=admin_main_keyboard
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_admin_main_to_main_text(*, user_id, text, raw_message):
    if text == Buttons.admin_main.TO_MAIN.value:
        user = await _get_vk_user(user_id)
        if user is None:
            await send_vk_message(
                user_id=user_id,
                message=Text.user.STATUS_NEED_REGISTRATION.value,
                keyboard=new_user_keyboard,
            )
            return PlainTextResponse("ok")
        if not user.is_approved:
            await send_vk_message(
                user_id=user_id, message=Text.user.STATUS_PENDING.value, keyboard=new_user_keyboard
            )
            return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id,
            message=Text.user.MAIN_MENU.value,
            keyboard=await _approved_vk_keyboard(user),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_main_betting_text(*, user_id, text, raw_message):
    if text == Buttons.main.BETTING.value:
        if vk_user_states.get(user_id) == WAITING_FOR_BET_PAYMENT_RECEIPT:
            vk_user_states.pop(user_id, None)
        await send_vk_message(
            user_id=user_id,
            message=Text.user.BETTING_MENU.value,
            keyboard=await _betting_vk_keyboard(),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_main_info_text(*, user_id, text, raw_message):
    if text == Buttons.main.INFO.value:
        await send_vk_message(
            user_id=user_id, message=InlineText.TEXT_1_05_TEXT_01, keyboard=main_info_keyboard
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_main_next_poker_date_text(*, user_id, text, raw_message):
    if text == Buttons.main.NEXT_POKER_DATE.value:
        user = await _get_vk_user(user_id)
        if user is None:
            await send_vk_message(
                user_id=user_id,
                message=Text.user.STATUS_NEED_REGISTRATION.value,
                keyboard=new_user_keyboard,
            )
            return PlainTextResponse("ok")
        if not user.is_approved:
            await send_vk_message(
                user_id=user_id, message=Text.user.STATUS_PENDING.value, keyboard=new_user_keyboard
            )
            return PlainTextResponse("ok")
        async with SessionFactory() as session:
            month = await PollConfigRepository(session).get_active_month()
        if month is None:
            await send_vk_message(
                user_id=user_id,
                message=Text.user.POLL_NOT_ACTIVE.value,
                keyboard=await _approved_vk_keyboard(user),
            )
            return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id, message=InlineText.TEXT_1_06_TEXT_01, keyboard=poll_menu_keyboard
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_main_poker_text(*, user_id, text, raw_message):
    if text == Buttons.main.POKER.value:
        await send_vk_message(
            user_id=user_id, message=Text.user.POKER_MENU.value, keyboard=poker_keyboard
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_betting_to_main_text(*, user_id, text, raw_message):
    if text == Buttons.betting.TO_MAIN.value:
        if vk_user_states.get(user_id) == WAITING_FOR_BET_PAYMENT_RECEIPT:
            vk_user_states.pop(user_id, None)
            await send_vk_message(user_id=user_id, message=Text.user.BETTING_PAY_CANCELED.value)
        user = await _get_vk_user(user_id)
        if user is None:
            await send_vk_message(
                user_id=user_id,
                message=Text.user.STATUS_NEED_REGISTRATION.value,
                keyboard=new_user_keyboard,
            )
            return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id,
            message=Text.user.MAIN_MENU.value,
            keyboard=await _approved_vk_keyboard(user),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_poker_to_main_text(*, user_id, text, raw_message):
    if text == Buttons.poker.TO_MAIN.value:
        user = await _get_vk_user(user_id)
        if user is None:
            await send_vk_message(
                user_id=user_id,
                message=Text.user.STATUS_NEED_REGISTRATION.value,
                keyboard=new_user_keyboard,
            )
            return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id,
            message=Text.user.MAIN_MENU.value,
            keyboard=await _approved_vk_keyboard(user),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_room_to_main_text(*, user_id, text, raw_message):
    if text == Buttons.room.TO_MAIN.value:
        user = await _get_vk_user(user_id)
        if user is None:
            await send_vk_message(
                user_id=user_id,
                message=Text.user.STATUS_NEED_REGISTRATION.value,
                keyboard=new_user_keyboard,
            )
            return PlainTextResponse("ok")
        if not user.is_approved:
            await send_vk_message(
                user_id=user_id, message=Text.user.STATUS_PENDING.value, keyboard=new_user_keyboard
            )
            return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id,
            message=Text.user.MAIN_MENU.value,
            keyboard=await _approved_vk_keyboard(user),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_poll_menu_to_main_text(*, user_id, text, raw_message):
    if text == Buttons.poll_menu.TO_MAIN.value:
        user = await _get_vk_user(user_id)
        if user is None:
            await send_vk_message(
                user_id=user_id,
                message=Text.user.STATUS_NEED_REGISTRATION.value,
                keyboard=new_user_keyboard,
            )
            return PlainTextResponse("ok")
        if not user.is_approved:
            await send_vk_message(
                user_id=user_id, message=Text.user.STATUS_PENDING.value, keyboard=new_user_keyboard
            )
            return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id,
            message=Text.user.MAIN_MENU.value,
            keyboard=await _approved_vk_keyboard(user),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_poker_info_text(*, user_id, text, raw_message):
    if text in {Buttons.main_info.POKER_INFO.value, InlineText.TEXT_1_12_TEXT_01}:
        await send_vk_message(
            user_id=user_id, message=Text.user.POKER_INFO.value, keyboard=poker_info_keyboard
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_betting_info_text(*, user_id, text, raw_message):
    if text in {Buttons.main_info.BETTING_INFO.value, InlineText.TEXT_1_13_TEXT_01}:
        await send_vk_message(
            user_id=user_id, message=Text.user.BETTING_MENU.value, keyboard=betting_info_keyboard
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_main_info_to_main_text(*, user_id, text, raw_message):
    if text == Buttons.main_info.TO_MAIN.value:
        user = await _get_vk_user(user_id)
        if user is None:
            await send_vk_message(
                user_id=user_id,
                message=Text.user.STATUS_NEED_REGISTRATION.value,
                keyboard=new_user_keyboard,
            )
            return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id,
            message=Text.user.MAIN_MENU.value,
            keyboard=await _approved_vk_keyboard(user),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED
