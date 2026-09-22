from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.texts.texts import Text
from app.bot.vk.api import (
    send_vk_message,
    send_vk_message_event_answer,
)
from app.bot.vk.keyboards import (
    new_user_keyboard,
    played_before_keyboard,
    registration_candidates_keyboard,
    registration_candidates_page_keyboard,
    registration_optional_details_keyboard,
    registration_platform_keyboard,
)
from app.bot.vk.state import (
    WAITING_FOR_NEW_NAME,
    WAITING_FOR_OPTIONAL_BANK,
    WAITING_FOR_OPTIONAL_DETAILS_ACTION,
    WAITING_FOR_OPTIONAL_PHONE,
    WAITING_FOR_PLAYED_BEFORE,
    vk_user_contexts,
    vk_user_states,
)
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory
from fastapi.responses import PlainTextResponse

from .common import (
    HANDLER_UNMATCHED,
    _approved_vk_keyboard,
    _delete_event_message_if_possible,
    _normalize_phone,
    _submit_registration_request,
)


async def _event_0_11(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "registration_existing":
        selected_row_id = callback_payload.get("row_id")
        if not isinstance(selected_row_id, int):
            return PlainTextResponse("ok")
        async with SessionFactory() as session:
            repository = UserRepository(session)
            selected_user = await repository.get_by_row_id(selected_row_id)
            if (
                selected_user is None
                or not selected_user.is_approved
                or selected_user.vk_id is not None
            ):
                await send_vk_message_event_answer(
                    event_id=event_id,
                    user_id=user_id,
                    peer_id=peer_id,
                    text=Text.user.REGISTRATION_CHOOSE_FROM_LIST.value,
                )
                return PlainTextResponse("ok")

        context = vk_user_contexts.setdefault(user_id, {})
        context["linked_user_row_id"] = str(selected_user.row_id)
        context["linked_user_name"] = selected_user.name
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=user_id,
            peer_id=peer_id,
            text=Text.user.REGISTRATION_PLATFORM_PROMPT.value,
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=user_id,
            message=Text.user.REGISTRATION_PLATFORM_PROMPT.value,
            keyboard=registration_platform_keyboard(),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _event_0_12(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action in {"registration_played_before_yes", "registration_played_before_no"}:
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        if action == "registration_played_before_yes":
            async with SessionFactory() as session:
                repository = UserRepository(session)
                candidates = await repository.list_approved_without_vk_id()
            vk_user_states.pop(user_id, None)
            if not candidates:
                vk_user_states[user_id] = WAITING_FOR_NEW_NAME
                await send_vk_message_event_answer(
                    event_id=event_id,
                    user_id=user_id,
                    peer_id=peer_id,
                    text=Text.user.REGISTRATION_PLAYED_BEFORE_EMPTY.value,
                )
                await send_vk_message(
                    user_id=user_id,
                    message=Text.user.REGISTRATION_PLAYED_BEFORE_EMPTY.value,
                )
                return PlainTextResponse("ok")
            await send_vk_message_event_answer(
                event_id=event_id,
                user_id=user_id,
                peer_id=peer_id,
                text=Text.user.REGISTRATION_PLAYED_BEFORE_Y.value,
            )
            await send_vk_message(
                user_id=user_id,
                message=Text.user.REGISTRATION_PLAYED_BEFORE_Y.value,
                keyboard=registration_candidates_keyboard(users=candidates),
            )
            return PlainTextResponse("ok")

        vk_user_states[user_id] = WAITING_FOR_NEW_NAME
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=user_id,
            peer_id=peer_id,
            text=Text.user.REGISTRATION_NEW_NAME_PROMPT.value,
        )
        await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_NEW_NAME_PROMPT.value)
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _event_0_13(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "registration_existing_page":
        page = callback_payload.get("page")
        if not isinstance(page, int):
            return PlainTextResponse("ok")
        async with SessionFactory() as session:
            repository = UserRepository(session)
            candidates = await repository.list_approved_without_vk_id()
        if not candidates:
            await send_vk_message_event_answer(
                event_id=event_id,
                user_id=user_id,
                peer_id=peer_id,
                text=Text.user.REGISTRATION_PLAYED_BEFORE_EMPTY.value,
            )
            await _delete_event_message_if_possible(
                peer_id=peer_id, conversation_message_id=conversation_message_id
            )
            await send_vk_message(
                user_id=user_id,
                message=Text.user.REGISTRATION_PLAYED_BEFORE_EMPTY.value,
            )
            return PlainTextResponse("ok")
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=user_id,
            peer_id=peer_id,
            text=Text.user.REGISTRATION_PLAYED_BEFORE_Y.value,
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(
            user_id=user_id,
            message=Text.user.REGISTRATION_PLAYED_BEFORE_Y.value,
            keyboard=registration_candidates_page_keyboard(users=candidates, page=page),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _event_0_14(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "registration_new_name":
        vk_user_states[user_id] = WAITING_FOR_NEW_NAME
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=user_id,
            peer_id=peer_id,
            text=Text.user.REGISTRATION_NEW_NAME_PROMPT.value,
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_NEW_NAME_PROMPT.value)
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _event_0_15(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action in {"registration_platform_tg", "registration_platform_vk"}:
        context = vk_user_contexts.get(user_id, {})
        selected_name = context.get("linked_user_name")
        selected_row_id = context.get("linked_user_row_id")
        if not selected_name or not selected_row_id:
            await send_vk_message_event_answer(
                event_id=event_id,
                user_id=user_id,
                peer_id=peer_id,
                text=Text.user.REGISTRATION_READ_ERROR.value,
            )
            return PlainTextResponse("ok")
        platform = "tg" if action.endswith("_tg") else "vk"
        async with SessionFactory() as session:
            repository = UserRepository(session)
            linked_user = await repository.get_by_row_id(int(selected_row_id))
            if linked_user is None:
                await send_vk_message_event_answer(
                    event_id=event_id,
                    user_id=user_id,
                    peer_id=peer_id,
                    text=Text.user.REGISTRATION_READ_ERROR.value,
                )
                return PlainTextResponse("ok")
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=user_id,
            peer_id=peer_id,
            text=Text.user.REGISTRATION_WAIT.value,
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await _submit_registration_request(
            user_id=user_id,
            name=selected_name,
            success_message=Text.user.REGISTRATION_WAIT.value,
            linked_to_user=linked_user,
            notification_platform=platform,
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _event_0_16(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "registration_optional_bank":
        if "registration_name" not in vk_user_contexts.get(user_id, {}):
            await send_vk_message_event_answer(
                event_id=event_id,
                user_id=user_id,
                peer_id=peer_id,
                text=Text.user.REGISTRATION_READ_ERROR.value,
            )
            return PlainTextResponse("ok")
        vk_user_states[user_id] = WAITING_FOR_OPTIONAL_BANK
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=user_id,
            peer_id=peer_id,
            text=Text.user.REGISTRATION_BANK_PROMPT.value,
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_BANK_PROMPT.value)
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _event_0_17(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "registration_optional_phone":
        if "registration_name" not in vk_user_contexts.get(user_id, {}):
            await send_vk_message_event_answer(
                event_id=event_id,
                user_id=user_id,
                peer_id=peer_id,
                text=Text.user.REGISTRATION_READ_ERROR.value,
            )
            return PlainTextResponse("ok")
        vk_user_states[user_id] = WAITING_FOR_OPTIONAL_PHONE
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=user_id,
            peer_id=peer_id,
            text=Text.user.REGISTRATION_PHONE_PROMPT.value,
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_PHONE_PROMPT.value)
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _event_0_18(
    *, user_id, peer_id, event_id, conversation_message_id, callback_payload, action
):
    if action == "registration_optional_skip":
        context = vk_user_contexts.get(user_id, {})
        registration_name = context.get("registration_name")
        if not registration_name:
            await send_vk_message_event_answer(
                event_id=event_id,
                user_id=user_id,
                peer_id=peer_id,
                text=Text.user.REGISTRATION_READ_ERROR.value,
            )
            return PlainTextResponse("ok")
        await send_vk_message_event_answer(
            event_id=event_id,
            user_id=user_id,
            peer_id=peer_id,
            text=Text.user.REGISTRATION_WAIT.value,
        )
        await _delete_event_message_if_possible(
            peer_id=peer_id, conversation_message_id=conversation_message_id
        )
        await _submit_registration_request(
            user_id=user_id,
            name=registration_name,
            success_message=Text.user.REGISTRATION_WAIT.value,
            bank_name=context.get("bank_name"),
            tel_number=context.get("tel_number"),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _text_1_35(*, user_id, text, raw_message):
    if text == Buttons.new_user.REGISTRATION.value:
        if vk_user_states.get(user_id) in {
            WAITING_FOR_PLAYED_BEFORE,
            WAITING_FOR_NEW_NAME,
            WAITING_FOR_OPTIONAL_DETAILS_ACTION,
            WAITING_FOR_OPTIONAL_BANK,
            WAITING_FOR_OPTIONAL_PHONE,
        }:
            await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_IN_PROGRESS.value)
            return PlainTextResponse("ok")
        async with SessionFactory() as session:
            repository = UserRepository(session)
            existing_user = await repository.get_by_vk_id(user_id)
        if existing_user is not None:
            vk_user_states.pop(user_id, None)
            vk_user_contexts.pop(user_id, None)
            await send_vk_message(
                user_id=user_id,
                message=Text.user.REGISTRATION_EXIST.value
                if existing_user.is_approved
                else Text.user.REGISTRATION_PENDING.value,
                keyboard=(await _approved_vk_keyboard(existing_user))
                if existing_user.is_approved
                else new_user_keyboard,
            )
            return PlainTextResponse("ok")
        vk_user_states[user_id] = WAITING_FOR_PLAYED_BEFORE
        await send_vk_message(
            user_id=user_id,
            message=Text.user.REGISTRATION_PLAYED_BEFORE_Q.value,
            keyboard=played_before_keyboard(),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _text_1_36(*, user_id, text, raw_message):
    if text == Buttons.new_user.ABOUT.value:
        async with SessionFactory() as session:
            repository = UserRepository(session)
            existing_user = await repository.get_by_vk_id(user_id)
        await send_vk_message(
            user_id=user_id,
            message=Text.user.BOT_INFO.value,
            keyboard=(await _approved_vk_keyboard(existing_user))
            if existing_user and existing_user.is_approved
            else new_user_keyboard,
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _text_1_38(*, user_id, text, raw_message):
    if vk_user_states.get(user_id) == WAITING_FOR_PLAYED_BEFORE:
        normalized_text = text.lower()
        if normalized_text == Buttons.registration_inline.YES.value.lower():
            async with SessionFactory() as session:
                repository = UserRepository(session)
                candidates = await repository.list_approved_without_vk_id()
            vk_user_states.pop(user_id, None)
            if not candidates:
                vk_user_states[user_id] = WAITING_FOR_NEW_NAME
                await send_vk_message(
                    user_id=user_id,
                    message=Text.user.REGISTRATION_PLAYED_BEFORE_EMPTY.value,
                )
                return PlainTextResponse("ok")
            await send_vk_message(
                user_id=user_id,
                message=Text.user.REGISTRATION_PLAYED_BEFORE_Y.value,
                keyboard=registration_candidates_keyboard(users=candidates),
            )
            return PlainTextResponse("ok")
        if normalized_text == Buttons.registration_inline.NO.value.lower():
            vk_user_states[user_id] = WAITING_FOR_NEW_NAME
            await send_vk_message(
                user_id=user_id, message=Text.user.REGISTRATION_NEW_NAME_PROMPT.value
            )
            return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id,
            message=Text.user.REGISTRATION_PLAYED_BEFORE_Q.value,
            keyboard=played_before_keyboard(),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _text_1_39(*, user_id, text, raw_message):
    if vk_user_states.get(user_id) == WAITING_FOR_NEW_NAME:
        name = " ".join(text.split())
        vk_user_states[user_id] = WAITING_FOR_OPTIONAL_DETAILS_ACTION
        vk_user_contexts[user_id] = {"registration_name": name, "bank_name": "", "tel_number": ""}
        await send_vk_message(
            user_id=user_id,
            message=Text.user.REGISTRATION_OPTIONAL_DETAILS_PROMPT.value,
            keyboard=registration_optional_details_keyboard(),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _text_1_40(*, user_id, text, raw_message):
    if vk_user_states.get(user_id) == WAITING_FOR_OPTIONAL_BANK:
        bank_name = " ".join(text.split()).title()
        if not bank_name:
            await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_BANK_PROMPT.value)
            return PlainTextResponse("ok")
        context = vk_user_contexts.setdefault(user_id, {})
        context["bank_name"] = bank_name
        existing_phone = context.get("tel_number")
        if existing_phone:
            registration_name = context.get("registration_name")
            if not registration_name:
                vk_user_states.pop(user_id, None)
                vk_user_contexts.pop(user_id, None)
                await send_vk_message(
                    user_id=user_id, message=Text.user.REGISTRATION_READ_ERROR.value
                )
                return PlainTextResponse("ok")
            await _submit_registration_request(
                user_id=user_id,
                name=registration_name,
                success_message=Text.user.REGISTRATION_WAIT.value,
                bank_name=bank_name,
                tel_number=existing_phone,
            )
            return PlainTextResponse("ok")
        vk_user_states[user_id] = WAITING_FOR_OPTIONAL_PHONE
        await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_PHONE_PROMPT.value)
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _text_1_41(*, user_id, text, raw_message):
    if vk_user_states.get(user_id) == WAITING_FOR_OPTIONAL_PHONE:
        normalized_phone = _normalize_phone(text)
        if normalized_phone is None:
            await send_vk_message(
                user_id=user_id, message=Text.user.REGISTRATION_PHONE_INVALID.value
            )
            return PlainTextResponse("ok")
        context = vk_user_contexts.setdefault(user_id, {})
        context["tel_number"] = normalized_phone
        existing_bank = context.get("bank_name")
        if existing_bank:
            registration_name = context.get("registration_name")
            if not registration_name:
                vk_user_states.pop(user_id, None)
                vk_user_contexts.pop(user_id, None)
                await send_vk_message(
                    user_id=user_id, message=Text.user.REGISTRATION_READ_ERROR.value
                )
                return PlainTextResponse("ok")
            await _submit_registration_request(
                user_id=user_id,
                name=registration_name,
                success_message=Text.user.REGISTRATION_WAIT.value,
                bank_name=existing_bank,
                tel_number=normalized_phone,
            )
            return PlainTextResponse("ok")
        vk_user_states[user_id] = WAITING_FOR_OPTIONAL_BANK
        await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_BANK_PROMPT.value)
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def _text_1_42(*, user_id, text, raw_message):
    if vk_user_states.get(user_id) == WAITING_FOR_OPTIONAL_DETAILS_ACTION:
        await send_vk_message(
            user_id=user_id,
            message=Text.user.REGISTRATION_OPTIONAL_DETAILS_PROMPT.value,
            keyboard=registration_optional_details_keyboard(),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED
