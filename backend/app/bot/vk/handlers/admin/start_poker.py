from fastapi.responses import PlainTextResponse

from app.application.use_cases.poker.start_poker import (
    PokerAlreadyStartedError,
    PokerParamsNotFoundError,
    StartPokerNotAuthorizedError,
    StartPokerUseCase,
)
from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.guards import is_vk_admin
from app.bot.shared.texts.inline.vk.admin import poker as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.vk.api import send_vk_message, send_vk_message_event_answer
from app.bot.vk.keyboards import poker_params_keyboard
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory
from app.services.start_poker_flow import execute_start_poker

from .common import HANDLER_UNMATCHED, _clear_event_inline_keyboard_if_possible


async def handle_poker_start_param_event(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action != "poker_start_param":
        return HANDLER_UNMATCHED

    params_id = callback_payload.get("params_id")
    if not isinstance(params_id, int):
        return PlainTextResponse("ok")

    async with SessionFactory() as session:
        actor = await UserRepository(session).get_by_vk_id(admin_user_id)

    if actor is None:
        result_text = Text.admin.NO_RIGHTS.value
    else:
        try:
            await execute_start_poker(actor_user_id=int(actor.row_id), params_id=params_id)
            result_text = Text.admin.POKER_START_SUCCESS.value
        except (PokerAlreadyStartedError, PokerParamsNotFoundError):
            result_text = Text.admin.POKER_STARTED.value
        except StartPokerNotAuthorizedError:
            result_text = Text.admin.NO_RIGHTS.value

    await send_vk_message_event_answer(
        event_id=event_id,
        user_id=admin_user_id,
        peer_id=peer_id,
        text=result_text,
    )
    await _clear_event_inline_keyboard_if_possible(
        peer_id=peer_id, conversation_message_id=conversation_message_id
    )
    await send_vk_message(user_id=admin_user_id, message=result_text)
    return None


async def handle_admin_main_start_poker_text(*, user_id, text):
    if text != Buttons.admin_main.START_POKER.value:
        return HANDLER_UNMATCHED

    async with SessionFactory() as session:
        if not await is_vk_admin(session=session, vk_id=user_id):
            await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
            return PlainTextResponse("ok")
        can_start, params = await StartPokerUseCase(session).get_start_data()
        if not can_start:
            await send_vk_message(user_id=user_id, message=Text.admin.POKER_STARTED.value)
            return PlainTextResponse("ok")
        if not params:
            await send_vk_message(user_id=user_id, message=Text.admin.POKER_PARAMS_EMPTY.value)
            return PlainTextResponse("ok")

    await send_vk_message(
        user_id=user_id,
        message="\n\n".join(
            [
                Text.admin.POKER_PARAMS_CHOOSE.value,
                *[
                    (
                        f"{InlineText.TEXT_1_09_TEXT_01_PART_1}{p.row_id}"
                        f"{InlineText.TEXT_1_09_TEXT_01_PART_2}{p.buyin_size_chips}"
                        f"{InlineText.TEXT_1_09_TEXT_01_PART_3}"
                        f"{int(p.buyin_size_kopecks) // 100}"
                        f"{InlineText.TEXT_1_09_TEXT_01_PART_4}{p.bb_size_chips}"
                        f"{InlineText.TEXT_1_09_TEXT_01_PART_5}{p.max_buyins}"
                        f"{InlineText.TEXT_1_09_TEXT_01_PART_6}{p.big_buyin}"
                        f"{InlineText.TEXT_1_09_TEXT_01_PART_7}{p.super_buyin}"
                    )
                    for p in params
                ],
            ]
        ),
        keyboard=poker_params_keyboard(params=params),
    )
    return PlainTextResponse("ok")
