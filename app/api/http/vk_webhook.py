from fastapi import APIRouter, HTTPException, status
from fastapi.responses import PlainTextResponse

from app.application.exceptions import (
  UserAlreadyApprovedError,
  UserAlreadyRegisteredError,
  UserIdentityRequiredError,
  UserLinkConflictError,
  UserNameRequiredError,
  UserNotFoundError,
  UserRegistrationPendingError,
)
from app.application.use_cases.approve_user import ApproveUserUseCase
from app.application.use_cases.correct_user import CorrectUserUseCase
from app.application.use_cases.link_pending_user import LinkPendingUserUseCase
from app.application.use_cases.reject_user import RejectUserUseCase
from app.application.use_cases.request_registration import RequestRegistrationUseCase
from app.bot.shared.buttons import Buttons
from app.bot.shared.texts import Text
from app.bot.vk.api import send_vk_message, send_vk_message_event_answer
from app.bot.vk.keyboards import (
  link_candidates_keyboard,
  main_keyboard,
  played_before_keyboard,
  registration_candidates_keyboard,
  registration_optional_details_keyboard,
  registration_link_review_keyboard as vk_registration_link_review_keyboard,
  registration_review_keyboard as vk_registration_review_keyboard,
)
from app.bot.vk.notifications import (
  notify_admins_about_registration,
)
from app.bot.telegram.notifications import notify_admins_about_registration as notify_tg_admins_about_registration
from app.bot.telegram.keyboards import (
  registration_link_review_keyboard as tg_registration_link_review_keyboard,
  registration_review_keyboard as tg_registration_review_keyboard,
)
from app.bot.vk.state import (
  WAITING_FOR_ADMIN_CORRECTED_NAME,
  WAITING_FOR_NEW_NAME,
  WAITING_FOR_OPTIONAL_BANK,
  WAITING_FOR_OPTIONAL_DETAILS_ACTION,
  WAITING_FOR_OPTIONAL_PHONE,
  WAITING_FOR_PLAYED_BEFORE,
  vk_user_contexts,
  vk_user_states,
)
from app.config.settings import settings
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory

router = APIRouter(prefix="/webhooks/vk", tags=["vk"])


def _format_platform_candidates_for_user(users: list) -> str:
  if not users:
    return Text.user.REGISTRATION_PLATFORM_CANDIDATES_EMPTY.value

  lines = [Text.user.REGISTRATION_PLATFORM_CANDIDATES.value]
  for user in users[:10]:
    lines.append(f"{user.row_id} — {user.name}")

  if len(users) > 10:
    lines.append("...")

  return "\n".join(lines)


async def _submit_registration_request(
  *,
  user_id: int,
  name: str,
  success_message: str,
  linked_to_user=None,
  bank_name: str | None = None,
  tel_number: str | None = None,
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
      )
    except UserIdentityRequiredError:
      await send_vk_message(
        user_id=user_id,
        message=Text.user.REGISTRATION_ID_ERROR.value,
      )
      return
    except UserNameRequiredError:
      await send_vk_message(
        user_id=user_id,
        message=Text.user.REGISTRATION_EMPTY_NAME.value,
      )
      return
    except UserAlreadyRegisteredError:
      vk_user_states.pop(user_id, None)
      vk_user_contexts.pop(user_id, None)
      await send_vk_message(
        user_id=user_id,
        message=Text.user.REGISTRATION_EXIST.value,
        keyboard=main_keyboard,
      )
      return
    except UserRegistrationPendingError:
      vk_user_states.pop(user_id, None)
      vk_user_contexts.pop(user_id, None)
      await send_vk_message(
        user_id=user_id,
        message=Text.user.REGISTRATION_PENDING.value,
        keyboard=main_keyboard,
      )
      return

    admin_ids = await repository.list_admin_vk_ids()
    tg_admin_chat_ids = await repository.list_admin_tg_ids()
    all_users = await repository.list_all()
    approved_users = await repository.list_approved()

  vk_user_states.pop(user_id, None)
  vk_user_contexts.pop(user_id, None)
  await notify_tg_admins_about_registration(
    row_id=user.row_id,
    name=name,
    telegram_id=None,
    all_users=all_users,
    admin_chat_ids=tg_admin_chat_ids,
    linked_to_user=linked_to_user,
    reply_markup=(
      tg_registration_link_review_keyboard(row_id=user.row_id)
      if linked_to_user is not None
      else tg_registration_review_keyboard(row_id=user.row_id)
    ),
  )
  await notify_admins_about_registration(
    row_id=user.row_id,
    name=name,
    vk_id=user_id,
    admin_ids=admin_ids,
    all_users=all_users,
    approved_users=approved_users,
    linked_to_user=linked_to_user,
    keyboard=(
      vk_registration_link_review_keyboard(row_id=user.row_id)
      if linked_to_user is not None
      else vk_registration_review_keyboard(row_id=user.row_id)
    ),
  )
  await send_vk_message(
    user_id=user_id,
    message=success_message,
    keyboard=main_keyboard,
  )


def _normalize_phone(value: str) -> str | None:
  digits = "".join(ch for ch in value if ch.isdigit())
  if digits.startswith("7") and len(digits) == 11:
    return f"+{digits}"
  return None


async def _process_vk_approve(*, admin_user_id: int, row_id: int) -> str:
  async with SessionFactory() as session:
    repository = UserRepository(session)
    admin_ids = await repository.list_vk_admin_ids()
    if admin_user_id not in admin_ids:
      return Text.admin.NO_RIGHTS.value

    use_case = ApproveUserUseCase(repository)
    try:
      approved_user = await use_case.execute(row_id=row_id)
    except UserNotFoundError:
      return Text.admin.REQUEST_NOT_FOUND.value

  if approved_user.vk_id is not None:
    await send_vk_message(
      user_id=approved_user.vk_id,
      message=Text.user.REGISTRATION_APPROVED.value,
      keyboard=main_keyboard,
    )

  return (
    f"{Text.admin.APPROVE_ACTION.value}\n\n"
    f"Row ID: {approved_user.row_id}\n"
    f"Имя: {approved_user.name}\n"
    f"Telegram ID: {approved_user.telegram_id}\n"
    f"VK ID: {approved_user.vk_id}"
  )


async def _process_vk_reject(*, admin_user_id: int, row_id: int) -> str:
  async with SessionFactory() as session:
    repository = UserRepository(session)
    admin_ids = await repository.list_vk_admin_ids()
    if admin_user_id not in admin_ids:
      return Text.admin.NO_RIGHTS.value

    pending_user = await repository.get_by_row_id(row_id)
    if pending_user is None:
      return Text.admin.REQUEST_NOT_FOUND.value

    pending_vk_id = pending_user.vk_id
    use_case = RejectUserUseCase(repository)
    try:
      await use_case.execute(row_id=row_id)
    except UserNotFoundError:
      return Text.admin.REQUEST_NOT_FOUND.value
    except UserAlreadyApprovedError:
      return Text.admin.REQUEST_ALREADY_APPROVED.value

  if pending_vk_id is not None:
    await send_vk_message(
      user_id=pending_vk_id,
      message=Text.user.REGISTRATION_NOT_APPROVED.value,
      keyboard=main_keyboard,
    )

  return f"{Text.admin.REJECT_ACTION.value}\n\nRow ID: {row_id}"


async def _process_vk_correct(
  *,
  admin_user_id: int,
  row_id: int,
  corrected_name: str,
) -> str:
  async with SessionFactory() as session:
    repository = UserRepository(session)
    admin_ids = await repository.list_vk_admin_ids()
    if admin_user_id not in admin_ids:
      return Text.admin.NO_RIGHTS.value

    use_case = CorrectUserUseCase(repository)
    try:
      corrected_user = await use_case.execute(
        row_id=row_id,
        corrected_name=corrected_name,
      )
    except UserNotFoundError:
      return Text.admin.REQUEST_NOT_FOUND.value
    except UserNameRequiredError:
      return Text.admin.EMPTY_CORRECTED_NAME.value
    except UserAlreadyApprovedError:
      return Text.admin.REQUEST_ALREADY_APPROVED.value

  if corrected_user.vk_id is not None:
    await send_vk_message(
      user_id=corrected_user.vk_id,
      message=Text.user.REGISTRATION_APPROVED.value,
      keyboard=main_keyboard,
    )

  return (
    f"{Text.admin.CORRECT_ACTION.value}\n\n"
    f"Row ID: {corrected_user.row_id}\n"
    f"Имя: {corrected_user.name}\n"
    f"Telegram ID: {corrected_user.telegram_id}\n"
    f"VK ID: {corrected_user.vk_id}"
  )


async def _process_vk_link(
  *,
  admin_user_id: int,
  pending_row_id: int,
  existing_row_id: int,
) -> str:
  async with SessionFactory() as session:
    repository = UserRepository(session)
    admin_ids = await repository.list_vk_admin_ids()
    if admin_user_id not in admin_ids:
      return Text.admin.NO_RIGHTS.value

    use_case = LinkPendingUserUseCase(repository)
    try:
      linked_user = await use_case.execute(
        pending_row_id=pending_row_id,
        existing_row_id=existing_row_id,
      )
    except UserNotFoundError:
      return Text.admin.USER_NOT_FOUND.value
    except UserLinkConflictError:
      return Text.admin.LINK_CONFLICT.value

  return (
    f"{Text.admin.LINK_SUCCESS.value}\n\n"
    f"Row ID: {linked_user.row_id}\n"
    f"Имя: {linked_user.name}\n"
    f"Telegram ID: {linked_user.telegram_id}\n"
    f"VK ID: {linked_user.vk_id}"
  )


@router.post("")
async def vk_webhook(payload: dict) -> PlainTextResponse:
  event_type = payload.get("type")

  if payload.get("secret") and settings.vk_secret_key:
    if payload["secret"] != settings.vk_secret_key:
      raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid VK secret",
      )

  if event_type == "confirmation":
    return PlainTextResponse(settings.vk_confirmation_token)

  if event_type == "message_event":
    event_object = payload.get("object", {})
    admin_user_id = event_object.get("user_id")
    peer_id = event_object.get("peer_id")
    event_id = event_object.get("event_id")
    callback_payload = event_object.get("payload") or {}

    action = callback_payload.get("action")
    if not admin_user_id or not peer_id or not event_id:
      return PlainTextResponse("ok")

    if action == "approve":
      row_id = callback_payload.get("row_id")
      if not isinstance(row_id, int):
        return PlainTextResponse("ok")
      result_text = await _process_vk_approve(admin_user_id=admin_user_id, row_id=row_id)
      await send_vk_message_event_answer(
        event_id=event_id,
        user_id=admin_user_id,
        peer_id=peer_id,
        text=Text.admin.APPROVE_ACTION.value if result_text.startswith(Text.admin.APPROVE_ACTION.value) else result_text,
      )
      await send_vk_message(user_id=admin_user_id, message=result_text)
      return PlainTextResponse("ok")

    if action == "reject":
      row_id = callback_payload.get("row_id")
      if not isinstance(row_id, int):
        return PlainTextResponse("ok")
      result_text = await _process_vk_reject(admin_user_id=admin_user_id, row_id=row_id)
      await send_vk_message_event_answer(
        event_id=event_id,
        user_id=admin_user_id,
        peer_id=peer_id,
        text=Text.admin.REJECT_ACTION.value if result_text.startswith(Text.admin.REJECT_ACTION.value) else result_text,
      )
      await send_vk_message(user_id=admin_user_id, message=result_text)
      return PlainTextResponse("ok")

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
      await send_vk_message(
        user_id=admin_user_id,
        message=Text.admin.CORRECT_PROMPT.value,
      )
      return PlainTextResponse("ok")

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
      await send_vk_message(
        user_id=admin_user_id,
        message=Text.admin.LINK_PROMPT.value,
        keyboard=link_candidates_keyboard(
          pending_row_id=row_id,
          users=approved_users,
        ),
      )
      return PlainTextResponse("ok")

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
            user_id=admin_user_id,
            peer_id=peer_id,
            text=Text.user.REGISTRATION_CHOOSE_FROM_LIST.value,
          )
          return PlainTextResponse("ok")

      await send_vk_message_event_answer(
        event_id=event_id,
        user_id=admin_user_id,
        peer_id=peer_id,
        text=Text.user.REGISTRATION_LINK_WAIT.value,
      )
      await _submit_registration_request(
        user_id=admin_user_id,
        name=selected_user.name,
        success_message=Text.user.REGISTRATION_LINK_WAIT.value,
        linked_to_user=selected_user,
      )
      return PlainTextResponse("ok")

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
        text=Text.admin.LINK_SUCCESS.value if result_text.startswith(Text.admin.LINK_SUCCESS.value) else result_text,
      )
      await send_vk_message(user_id=admin_user_id, message=result_text)
      return PlainTextResponse("ok")

    if action == "registration_optional_bank":
      if "registration_name" not in vk_user_contexts.get(admin_user_id, {}):
        await send_vk_message_event_answer(
          event_id=event_id,
          user_id=admin_user_id,
          peer_id=peer_id,
          text=Text.user.REGISTRATION_READ_ERROR.value,
        )
        return PlainTextResponse("ok")
      vk_user_states[admin_user_id] = WAITING_FOR_OPTIONAL_BANK
      await send_vk_message_event_answer(
        event_id=event_id,
        user_id=admin_user_id,
        peer_id=peer_id,
        text=Text.user.REGISTRATION_BANK_PROMPT.value,
      )
      await send_vk_message(user_id=admin_user_id, message=Text.user.REGISTRATION_BANK_PROMPT.value)
      return PlainTextResponse("ok")

    if action == "registration_optional_phone":
      if "registration_name" not in vk_user_contexts.get(admin_user_id, {}):
        await send_vk_message_event_answer(
          event_id=event_id,
          user_id=admin_user_id,
          peer_id=peer_id,
          text=Text.user.REGISTRATION_READ_ERROR.value,
        )
        return PlainTextResponse("ok")
      vk_user_states[admin_user_id] = WAITING_FOR_OPTIONAL_PHONE
      await send_vk_message_event_answer(
        event_id=event_id,
        user_id=admin_user_id,
        peer_id=peer_id,
        text=Text.user.REGISTRATION_PHONE_PROMPT.value,
      )
      await send_vk_message(user_id=admin_user_id, message=Text.user.REGISTRATION_PHONE_PROMPT.value)
      return PlainTextResponse("ok")

    if action == "registration_optional_skip":
      context = vk_user_contexts.get(admin_user_id, {})
      registration_name = context.get("registration_name")
      if not registration_name:
        await send_vk_message_event_answer(
          event_id=event_id,
          user_id=admin_user_id,
          peer_id=peer_id,
          text=Text.user.REGISTRATION_READ_ERROR.value,
        )
        return PlainTextResponse("ok")
      await send_vk_message_event_answer(
        event_id=event_id,
        user_id=admin_user_id,
        peer_id=peer_id,
        text=Text.user.REGISTRATION_WAIT.value,
      )
      await _submit_registration_request(
        user_id=admin_user_id,
        name=registration_name,
        success_message=Text.user.REGISTRATION_WAIT.value,
        bank_name=context.get("bank_name"),
        tel_number=context.get("tel_number"),
      )
      return PlainTextResponse("ok")

    return PlainTextResponse("ok")

  if event_type != "message_new":
    return PlainTextResponse("ok")

  message = payload.get("object", {}).get("message", {})
  user_id = message.get("from_id")
  text = (message.get("text") or "").strip()

  if not user_id:
    return PlainTextResponse("ok")

  if text.lower() in {"начать", "start", "/start"}:
    vk_user_states.pop(user_id, None)
    vk_user_contexts.pop(user_id, None)
    await send_vk_message(
      user_id=user_id,
      message=Text.user.BOT_INFO.value,
      keyboard=main_keyboard,
    )
    return PlainTextResponse("ok")

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

  if text.lower().startswith("approve "):
    parts = text.split()
    if len(parts) != 2 or not parts[1].isdigit():
      await send_vk_message(
        user_id=user_id,
        message=Text.admin.APPROVE_COMMAND_USAGE.value,
      )
      return PlainTextResponse("ok")

    await send_vk_message(
      user_id=user_id,
      message=await _process_vk_approve(admin_user_id=user_id, row_id=int(parts[1])),
    )
    return PlainTextResponse("ok")

  if text.lower().startswith("correct "):
    parts = text.split(maxsplit=2)
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].strip():
      await send_vk_message(
        user_id=user_id,
        message=Text.admin.CORRECT_COMMAND_USAGE.value,
      )
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

  if text.lower().startswith("reject "):
    parts = text.split()
    if len(parts) != 2 or not parts[1].isdigit():
      await send_vk_message(
        user_id=user_id,
        message=Text.admin.REJECT_COMMAND_USAGE.value,
      )
      return PlainTextResponse("ok")

    await send_vk_message(
      user_id=user_id,
      message=await _process_vk_reject(admin_user_id=user_id, row_id=int(parts[1])),
    )
    return PlainTextResponse("ok")

  if text.lower().startswith("link "):
    parts = text.split()
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
      await send_vk_message(
        user_id=user_id,
        message=Text.admin.LINK_COMMAND_USAGE.value,
      )
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

  if text == Buttons.new_user.REGISTRATION.value:
    async with SessionFactory() as session:
      repository = UserRepository(session)
      existing_user = await repository.get_by_vk_id(user_id)

    if existing_user is not None:
      vk_user_states.pop(user_id, None)
      vk_user_contexts.pop(user_id, None)
      await send_vk_message(
        user_id=user_id,
        message=(
          Text.user.REGISTRATION_EXIST.value
          if existing_user.is_approved
          else Text.user.REGISTRATION_PENDING.value
        ),
        keyboard=main_keyboard,
      )
      return PlainTextResponse("ok")

    vk_user_states[user_id] = WAITING_FOR_PLAYED_BEFORE
    await send_vk_message(
      user_id=user_id,
      message=Text.user.REGISTRATION_PLAYED_BEFORE.value,
      keyboard=played_before_keyboard,
    )
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
        message=Text.user.REGISTRATION_EXISTING_ROW_ID_PROMPT.value,
        keyboard=registration_candidates_keyboard(users=candidates),
      )
      return PlainTextResponse("ok")
    if normalized_text == Buttons.registration_flow.NO.value.lower():
      vk_user_states[user_id] = WAITING_FOR_NEW_NAME
      await send_vk_message(
        user_id=user_id,
        message=Text.user.REGISTRATION_NEW_NAME_PROMPT.value,
      )
      return PlainTextResponse("ok")

    await send_vk_message(
      user_id=user_id,
      message=Text.user.REGISTRATION_PLAYED_BEFORE.value,
      keyboard=played_before_keyboard,
    )
    return PlainTextResponse("ok")

  if vk_user_states.get(user_id) == WAITING_FOR_NEW_NAME:
    name = " ".join(text.split())
    vk_user_states[user_id] = WAITING_FOR_OPTIONAL_DETAILS_ACTION
    vk_user_contexts[user_id] = {
      "registration_name": name,
      "bank_name": "",
      "tel_number": "",
    }
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
    vk_user_states[user_id] = WAITING_FOR_OPTIONAL_DETAILS_ACTION
    await send_vk_message(
      user_id=user_id,
      message=Text.user.REGISTRATION_BANK_SAVED.value,
      keyboard=registration_optional_details_keyboard(),
    )
    return PlainTextResponse("ok")

  if vk_user_states.get(user_id) == WAITING_FOR_OPTIONAL_PHONE:
    normalized_phone = _normalize_phone(text)
    if normalized_phone is None:
      await send_vk_message(user_id=user_id, message=Text.user.REGISTRATION_PHONE_INVALID.value)
      return PlainTextResponse("ok")
    context = vk_user_contexts.setdefault(user_id, {})
    context["tel_number"] = normalized_phone
    vk_user_states[user_id] = WAITING_FOR_OPTIONAL_DETAILS_ACTION
    await send_vk_message(
      user_id=user_id,
      message=Text.user.REGISTRATION_PHONE_SAVED.value,
      keyboard=registration_optional_details_keyboard(),
    )
    return PlainTextResponse("ok")

  if vk_user_states.get(user_id) == WAITING_FOR_OPTIONAL_DETAILS_ACTION:
    await send_vk_message(
      user_id=user_id,
      message=Text.user.REGISTRATION_OPTIONAL_DETAILS_PROMPT.value,
      keyboard=registration_optional_details_keyboard(),
    )
    return PlainTextResponse("ok")

  if text == Buttons.new_user.ABOUT.value:
    await send_vk_message(
      user_id=user_id,
      message=Text.user.BOT_INFO.value,
      keyboard=main_keyboard,
    )
    return PlainTextResponse("ok")

  return PlainTextResponse("ok")
