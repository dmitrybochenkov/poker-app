from app.application.exceptions import (
    UserNotFoundError,
)
from app.application.use_cases.user.make_admin import MakeAdminUseCase
from app.bot.shared.guards import is_vk_admin
from app.bot.shared.texts.texts import Text
from app.bot.vk.api import (
    send_vk_message,
    send_vk_message_event_answer,
)
from app.bot.vk.keyboards import (
    link_candidates_keyboard,
    link_candidates_page_keyboard,
)
from app.bot.vk.state import (
    WAITING_FOR_ADMIN_CORRECTED_NAME,
    vk_user_contexts,
    vk_user_states,
)
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory
from fastapi.responses import PlainTextResponse

from .common import (
    HANDLER_UNMATCHED,
    _clear_event_inline_keyboard_if_possible,
    _process_vk_approve,
    _process_vk_correct,
    _process_vk_link,
    _process_vk_reject,
)


async def _event_0_00(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "approve":
        row_id = callback_payload.get("row_id")
        if not isinstance(row_id, int):
            return PlainTextResponse("ok")
        result_text = await _process_vk_approve(admin_user_id=admin_user_id, row_id=row_id)
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=admin_user_id,
            peer_id=peer_id,
            text=Text.admin.APPROVE_ACTION.value
            if result_text.startswith(Text.admin.APPROVE_ACTION.value)
            else result_text,
        )
        await _clear_event_inline_keyboard_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(user_id=admin_user_id, message=result_text)
        return None
    return HANDLER_UNMATCHED


async def _event_0_01(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "reject":
        row_id = callback_payload.get("row_id")
        if not isinstance(row_id, int):
            return PlainTextResponse("ok")
        result_text = await _process_vk_reject(admin_user_id=admin_user_id, row_id=row_id)
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=admin_user_id,
            peer_id=peer_id,
            text=Text.admin.REJECT_ACTION.value
            if result_text.startswith(Text.admin.REJECT_ACTION.value)
            else result_text,
        )
        await _clear_event_inline_keyboard_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(user_id=admin_user_id, message=result_text)
        return None
    return HANDLER_UNMATCHED


async def _event_0_03(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "correct":
        row_id = callback_payload.get("row_id")
        if not isinstance(row_id, int):
            return PlainTextResponse("ok")
        vk_user_states[admin_user_id] = WAITING_FOR_ADMIN_CORRECTED_NAME
        vk_user_contexts[admin_user_id] = {"pending_row_id": str(row_id)}
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=admin_user_id,
            peer_id=peer_id,
            text=Text.admin.CORRECT_FLOW_STARTED.value,
        )
        await _clear_event_inline_keyboard_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(user_id=admin_user_id, message=Text.admin.CORRECT_PROMPT.value)
        return None
    return HANDLER_UNMATCHED


async def _event_0_04(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "link":
        row_id = callback_payload.get("row_id")
        if not isinstance(row_id, int):
            return PlainTextResponse("ok")
        async with SessionFactory() as session:
            repository = UserRepository(session)
            approved_users = await repository.list_approved()
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=admin_user_id,
            peer_id=peer_id,
            text=Text.admin.LINK_ACTION.value,
        )
        await _clear_event_inline_keyboard_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=admin_user_id,
            message=Text.admin.LINK_PROMPT.value,
            keyboard=link_candidates_keyboard(pending_row_id=row_id, users=approved_users),
        )
        return None
    return HANDLER_UNMATCHED


async def _event_0_05(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "link_to":
        pending_row_id = callback_payload.get("pending_row_id")
        existing_row_id = callback_payload.get("existing_row_id")
        if not isinstance(pending_row_id, int) or not isinstance(existing_row_id, int):
            return PlainTextResponse("ok")
        result_text = await _process_vk_link(
            admin_user_id=admin_user_id,
            pending_row_id=pending_row_id,
            existing_row_id=existing_row_id,
        )
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=admin_user_id,
            peer_id=peer_id,
            text=Text.admin.LINK_SUCCESS.value
            if result_text.startswith(Text.admin.LINK_SUCCESS.value)
            else result_text,
        )
        await _clear_event_inline_keyboard_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(user_id=admin_user_id, message=result_text)
        return None
    return HANDLER_UNMATCHED


async def _event_0_06(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "link_page":
        pending_row_id = callback_payload.get("pending_row_id")
        page = callback_payload.get("page")
        if not isinstance(pending_row_id, int) or not isinstance(page, int):
            return PlainTextResponse("ok")
        async with SessionFactory() as session:
            repository = UserRepository(session)
            approved_users = await repository.list_approved()
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=admin_user_id,
            peer_id=peer_id,
            text=Text.admin.LINK_ACTION.value,
        )
        await _clear_event_inline_keyboard_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=admin_user_id,
            message=Text.admin.LINK_PROMPT.value,
            keyboard=link_candidates_page_keyboard(
                pending_row_id=pending_row_id,
                users=approved_users,
                page=page,
            ),
        )
        return None
    return HANDLER_UNMATCHED


async def _event_0_07(
    *,
    admin_user_id,
    peer_id,
    event_id,
    conversation_message_id,
    callback_payload,
    action,
    handle_admin_text_commands,
):
    if action == "make_admin_select":
        row_id = callback_payload.get("row_id")
        if not isinstance(row_id, int):
            return PlainTextResponse("ok")
        async with SessionFactory() as session:
            repository = UserRepository(session)
            if not await is_vk_admin(session=session, vk_id=admin_user_id):
                result_text = Text.admin.NO_RIGHTS.value
            else:
                use_case = MakeAdminUseCase(repository)
                try:
                    user = await use_case.execute(row_id=row_id)
                    result_text = f"{Text.admin.MAKE_ADMIN_SUCCESS.value}\n\nИмя: {user.name}"
                except UserNotFoundError:
                    result_text = Text.admin.USER_NOT_FOUND.value
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
    return HANDLER_UNMATCHED


async def _text_1_00(*, user_id, text):
    if vk_user_states.get(user_id) == WAITING_FOR_ADMIN_CORRECTED_NAME:
        pending_row_id = vk_user_contexts.get(user_id, {}).get("pending_row_id")
        corrected_name = " ".join(text.split())
        if pending_row_id is None:
            vk_user_states.pop(user_id, None)
            vk_user_contexts.pop(user_id, None)
            await send_vk_message(user_id=user_id, message=Text.admin.REQUEST_NOT_FOUND.value)
            return PlainTextResponse("ok")
        result_text = await _process_vk_correct(
            admin_user_id=user_id,
            row_id=int(pending_row_id),
            corrected_name=corrected_name,
        )
        vk_user_states.pop(user_id, None)
        vk_user_contexts.pop(user_id, None)
        await send_vk_message(user_id=user_id, message=result_text)
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _text_1_04(*, user_id, text):
    if text.lower().startswith("approve "):
        parts = text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            await send_vk_message(user_id=user_id, message=Text.admin.APPROVE_COMMAND_USAGE.value)
            return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id,
            message=await _process_vk_approve(admin_user_id=user_id, row_id=int(parts[1])),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _text_1_05(*, user_id, text):
    if text.lower().startswith("correct "):
        parts = text.split(maxsplit=2)
        if len(parts) != 3 or not parts[1].isdigit() or not parts[2].strip():
            await send_vk_message(user_id=user_id, message=Text.admin.CORRECT_COMMAND_USAGE.value)
            return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id,
            message=await _process_vk_correct(
                admin_user_id=user_id,
                row_id=int(parts[1]),
                corrected_name=" ".join(parts[2].split()),
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _text_1_06(*, user_id, text):
    if text.lower().startswith("reject "):
        parts = text.split()
        if len(parts) != 2 or not parts[1].isdigit():
            await send_vk_message(user_id=user_id, message=Text.admin.REJECT_COMMAND_USAGE.value)
            return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id,
            message=await _process_vk_reject(admin_user_id=user_id, row_id=int(parts[1])),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _text_1_07(*, user_id, text):
    if text.lower().startswith("link "):
        parts = text.split()
        if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
            await send_vk_message(user_id=user_id, message=Text.admin.LINK_COMMAND_USAGE.value)
            return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id,
            message=await _process_vk_link(
                admin_user_id=user_id,
                pending_row_id=int(parts[1]),
                existing_row_id=int(parts[2]),
            ),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED
