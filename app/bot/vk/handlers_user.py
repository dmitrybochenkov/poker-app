from fastapi.responses import PlainTextResponse

from app.application.exceptions import (
  UserAlreadyRegisteredError,
  UserIdentityRequiredError,
  UserNameRequiredError,
  UserRegistrationPendingError,
)
from app.application.use_cases.request_registration import RequestRegistrationUseCase
from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
  registration_link_review_keyboard as tg_registration_link_review_keyboard,
  registration_review_keyboard as tg_registration_review_keyboard,
)
from app.bot.telegram.notifications import notify_admins_about_registration as notify_tg_admins_about_registration
from app.bot.vk.api import send_vk_message, send_vk_message_event_answer
from app.bot.vk.keyboards import (
  main_keyboard,
  played_before_keyboard,
  registration_candidates_keyboard,
  registration_link_review_keyboard as vk_registration_link_review_keyboard,
  registration_optional_details_keyboard,
  registration_platform_keyboard,
  registration_review_keyboard as vk_registration_review_keyboard,
)
from app.bot.vk.notifications import notify_admins_about_registration
from app.bot.vk.state import (
  WAITING_FOR_NEW_NAME,
  WAITING_FOR_OPTIONAL_BANK,
  WAITING_FOR_OPTIONAL_DETAILS_ACTION,
  WAITING_FOR_OPTIONAL_PHONE,
  WAITING_FOR_PLAYED_BEFORE,
  vk_user_contexts,
  vk_user_states,
)
from app.db.models.user import User
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory


async def _submit_registration_request(
  *,
  user_id: int,
  name: str,
  success_message: str,
  linked_to_user: User | None = None,
  bank_name: str | None = None,
  tel_number: str | None = None,
  notification_platform: str | None = None,
) -> None:
  async with SessionFactory() as session:
    repository = UserRepository(session)
    use_case = RequestRegistrationUseCase(repository)
    try:
      user = await use_case.execute(
        name=name,
        vk_id=user_id,
        bank_name=bank_name,
        tel_number=tel_number,
        notification_platform=notification_platform,
      )
    except UserIdentityRequiredError:
      await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_ID_ERROR.value)
      return
    except UserNameRequiredError:
      await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_EMPTY_NAME.value)
      return
    except UserAlreadyRegisteredError:
      vk_user_states.pop(user_id, None)
      vk_user_contexts.pop(user_id, None)
      await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_EXIST.value, keyboard=main_keyboard)
      return
    except UserRegistrationPendingError:
      vk_user_states.pop(user_id, None)
      vk_user_contexts.pop(user_id, None)
      await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_PENDING.value, keyboard=main_keyboard)
      return

    admin_ids = await repository.list_admin_vk_ids()
    tg_admin_chat_ids = await repository.list_admin_tg_ids()

  vk_user_states.pop(user_id, None)
  vk_user_contexts.pop(user_id, None)
  await notify_tg_admins_about_registration(
    name=name,
    telegram_id=None,
    vk_id=user_id,
    requester_platform="vk",
    admin_chat_ids=tg_admin_chat_ids,
    linked_to_user=linked_to_user,
    reply_markup=(
      tg_registration_link_review_keyboard(row_id=user.row_id)
      if linked_to_user is not None
      else tg_registration_review_keyboard(row_id=user.row_id)
    ),
  )
  await notify_admins_about_registration(
    name=name,
    vk_id=user_id,
    requester_platform="vk",
    admin_ids=admin_ids,
    linked_to_user=linked_to_user,
    keyboard=(
      vk_registration_link_review_keyboard(row_id=user.row_id)
      if linked_to_user is not None
      else vk_registration_review_keyboard(row_id=user.row_id)
    ),
  )
  await send_vk_message(user_id=user_id, message=success_message, keyboard=main_keyboard)


def _normalize_phone(value: str) -> str | None:
  digits = "".join(ch for ch in value if ch.isdigit())
  if digits.startswith("7") and len(digits) == 11:
    return f"+{digits}"
  return None


async def handle_user_message_event(event_object: dict) -> PlainTextResponse | None:
  user_id = event_object.get("user_id")
  peer_id = event_object.get("peer_id")
  event_id = event_object.get("event_id")
  callback_payload = event_object.get("payload") or {}
  action = callback_payload.get("action")
  if not user_id or not peer_id or not event_id:
    return PlainTextResponse("ok")

  if action == "registration_existing":
    selected_row_id = callback_payload.get("row_id")
    if not isinstance(selected_row_id, int):
      return PlainTextResponse("ok")
    async with SessionFactory() as session:
      repository = UserRepository(session)
      selected_user = await repository.get_by_row_id(selected_row_id)
      if selected_user is None or not selected_user.is_approved or selected_user.vk_id is not None:
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
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.REGISTRATION_PLATFORM_PROMPT.value)
    await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_PLATFORM_PROMPT.value, keyboard=registration_platform_keyboard())
    return PlainTextResponse("ok")

  if action == "registration_new_name":
    vk_user_states[user_id] = WAITING_FOR_NEW_NAME
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.REGISTRATION_NEW_NAME_PROMPT.value)
    await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_NEW_NAME_PROMPT.value)
    return PlainTextResponse("ok")

  if action in {"registration_platform_tg", "registration_platform_vk"}:
    context = vk_user_contexts.get(user_id, {})
    selected_name = context.get("linked_user_name")
    selected_row_id = context.get("linked_user_row_id")
    if not selected_name or not selected_row_id:
      await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.REGISTRATION_READ_ERROR.value)
      return PlainTextResponse("ok")
    platform = "tg" if action.endswith("_tg") else "vk"
    async with SessionFactory() as session:
      repository = UserRepository(session)
      linked_user = await repository.get_by_row_id(int(selected_row_id))
      if linked_user is None:
        await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.REGISTRATION_READ_ERROR.value)
        return PlainTextResponse("ok")
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.REGISTRATION_LINK_WAIT.value)
    await _submit_registration_request(
      user_id=user_id,
      name=selected_name,
      success_message=Text.user.REGISTRATION_LINK_WAIT.value,
      linked_to_user=linked_user,
      notification_platform=platform,
    )
    return PlainTextResponse("ok")

  if action == "registration_optional_bank":
    if "registration_name" not in vk_user_contexts.get(user_id, {}):
      await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.REGISTRATION_READ_ERROR.value)
      return PlainTextResponse("ok")
    vk_user_states[user_id] = WAITING_FOR_OPTIONAL_BANK
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.REGISTRATION_BANK_PROMPT.value)
    await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_BANK_PROMPT.value)
    return PlainTextResponse("ok")

  if action == "registration_optional_phone":
    if "registration_name" not in vk_user_contexts.get(user_id, {}):
      await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.REGISTRATION_READ_ERROR.value)
      return PlainTextResponse("ok")
    vk_user_states[user_id] = WAITING_FOR_OPTIONAL_PHONE
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.REGISTRATION_PHONE_PROMPT.value)
    await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_PHONE_PROMPT.value)
    return PlainTextResponse("ok")

  if action == "registration_optional_skip":
    context = vk_user_contexts.get(user_id, {})
    registration_name = context.get("registration_name")
    if not registration_name:
      await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.REGISTRATION_READ_ERROR.value)
      return PlainTextResponse("ok")
    await send_vk_message_event_answer(event_id=event_id, user_id=user_id, peer_id=peer_id, text=Text.user.REGISTRATION_WAIT.value)
    await _submit_registration_request(
      user_id=user_id,
      name=registration_name,
      success_message=Text.user.REGISTRATION_WAIT.value,
      bank_name=context.get("bank_name"),
      tel_number=context.get("tel_number"),
    )
    return PlainTextResponse("ok")

  return None


async def handle_user_message_new(*, user_id: int, text: str) -> PlainTextResponse | None:
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
        message=Text.user.REGISTRATION_EXIST.value if existing_user.is_approved else Text.user.REGISTRATION_PENDING.value,
        keyboard=main_keyboard,
      )
      return PlainTextResponse("ok")
    vk_user_states[user_id] = WAITING_FOR_PLAYED_BEFORE
    await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_PLAYED_BEFORE_Q.value, keyboard=played_before_keyboard)
    return PlainTextResponse("ok")

  if vk_user_states.get(user_id) == WAITING_FOR_PLAYED_BEFORE:
    normalized_text = text.lower()
    if normalized_text == Buttons.registration_flow.YES.value.lower():
      async with SessionFactory() as session:
        repository = UserRepository(session)
        candidates = await repository.list_approved_without_vk_id()
      vk_user_states.pop(user_id, None)
      await send_vk_message(
        user_id=user_id,
        message=Text.user.REGISTRATION_PLAYED_BEFORE_Y.value,
        keyboard=registration_candidates_keyboard(users=candidates),
      )
      return PlainTextResponse("ok")
    if normalized_text == Buttons.registration_flow.NO.value.lower():
      vk_user_states[user_id] = WAITING_FOR_NEW_NAME
      await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_NEW_NAME_PROMPT.value)
      return PlainTextResponse("ok")
    await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_PLAYED_BEFORE_Q.value, keyboard=played_before_keyboard)
    return PlainTextResponse("ok")

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
        await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_READ_ERROR.value)
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

  if vk_user_states.get(user_id) == WAITING_FOR_OPTIONAL_PHONE:
    normalized_phone = _normalize_phone(text)
    if normalized_phone is None:
      await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_PHONE_INVALID.value)
      return PlainTextResponse("ok")
    context = vk_user_contexts.setdefault(user_id, {})
    context["tel_number"] = normalized_phone
    existing_bank = context.get("bank_name")
    if existing_bank:
      registration_name = context.get("registration_name")
      if not registration_name:
        vk_user_states.pop(user_id, None)
        vk_user_contexts.pop(user_id, None)
        await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_READ_ERROR.value)
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

  if vk_user_states.get(user_id) == WAITING_FOR_OPTIONAL_DETAILS_ACTION:
    await send_vk_message(
      user_id=user_id,
      message=Text.user.REGISTRATION_OPTIONAL_DETAILS_PROMPT.value,
      keyboard=registration_optional_details_keyboard(),
    )
    return PlainTextResponse("ok")

  return None
