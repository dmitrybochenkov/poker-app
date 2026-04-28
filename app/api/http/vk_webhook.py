from fastapi import APIRouter, HTTPException, status
from fastapi.responses import PlainTextResponse

from app.application.exceptions import (
  UserAlreadyApprovedError,
  UserAlreadyRegisteredError,
  UserIdentityRequiredError,
  UserLinkConflictError,
  UserNotFoundError,
  UserRegistrationPendingError,
)
from app.application.use_cases.approve_user import ApproveUserUseCase
from app.application.use_cases.link_pending_user import LinkPendingUserUseCase
from app.application.use_cases.reject_user import RejectUserUseCase
from app.application.use_cases.request_registration import RequestRegistrationUseCase
from app.bot.shared.buttons import Buttons
from app.bot.shared.texts import Text
from app.bot.vk.api import send_vk_message
from app.bot.vk.keyboards import main_keyboard
from app.bot.vk.notifications import (
  notify_admins_about_registration,
)
from app.bot.vk.state import WAITING_FOR_NAME, vk_user_states
from app.config.settings import settings
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory

router = APIRouter(prefix="/webhooks/vk", tags=["vk"])


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

  if event_type != "message_new":
    return PlainTextResponse("ok")

  message = payload.get("object", {}).get("message", {})
  user_id = message.get("from_id")
  text = (message.get("text") or "").strip()

  if not user_id:
    return PlainTextResponse("ok")

  if text.lower() in {"начать", "start", "/start"}:
    vk_user_states.pop(user_id, None)
    await send_vk_message(
      user_id=user_id,
      message=Text.user.BOT_INFO.value,
      keyboard=main_keyboard,
    )
    return PlainTextResponse("ok")

  if text.lower().startswith("approve "):
    parts = text.split()
    if len(parts) != 2 or not parts[1].isdigit():
      await send_vk_message(
        user_id=user_id,
        message=Text.admin.APPROVE_COMMAND_USAGE.value,
      )
      return PlainTextResponse("ok")

    async with SessionFactory() as session:
      repository = UserRepository(session)
      admin_ids = await repository.list_vk_admin_ids()
      if user_id not in admin_ids:
        await send_vk_message(
          user_id=user_id,
          message=Text.admin.NO_RIGHTS.value,
        )
        return PlainTextResponse("ok")

      use_case = ApproveUserUseCase(repository)
      try:
        approved_user = await use_case.execute(row_id=int(parts[1]))
      except UserNotFoundError:
        await send_vk_message(
          user_id=user_id,
          message=Text.admin.REQUEST_NOT_FOUND.value,
        )
        return PlainTextResponse("ok")

    if approved_user.vk_id is not None:
      await send_vk_message(
        user_id=approved_user.vk_id,
        message=Text.user.REGISTRATION_APPROVED.value,
        keyboard=main_keyboard,
      )
    await send_vk_message(
      user_id=user_id,
      message=(
        f"{Text.admin.APPROVE_ACTION.value}\n\n"
        f"Row ID: {approved_user.row_id}\n"
        f"Имя: {approved_user.name}\n"
        f"Telegram ID: {approved_user.telegram_id}\n"
        f"VK ID: {approved_user.vk_id}"
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

    async with SessionFactory() as session:
      repository = UserRepository(session)
      admin_ids = await repository.list_vk_admin_ids()
      if user_id not in admin_ids:
        await send_vk_message(
          user_id=user_id,
          message=Text.admin.NO_RIGHTS.value,
        )
        return PlainTextResponse("ok")

      pending_user = await repository.get_by_row_id(int(parts[1]))
      if pending_user is None:
        await send_vk_message(
          user_id=user_id,
          message=Text.admin.REQUEST_NOT_FOUND.value,
        )
        return PlainTextResponse("ok")

      pending_vk_id = pending_user.vk_id
      use_case = RejectUserUseCase(repository)
      try:
        await use_case.execute(row_id=int(parts[1]))
      except UserNotFoundError:
        await send_vk_message(
          user_id=user_id,
          message=Text.admin.REQUEST_NOT_FOUND.value,
        )
        return PlainTextResponse("ok")
      except UserAlreadyApprovedError:
        await send_vk_message(
          user_id=user_id,
          message=Text.admin.REQUEST_ALREADY_APPROVED.value,
        )
        return PlainTextResponse("ok")

    if pending_vk_id is not None:
      await send_vk_message(
        user_id=pending_vk_id,
        message=Text.user.REGISTRATION_NOT_APPROVED.value,
        keyboard=main_keyboard,
      )
    await send_vk_message(
      user_id=user_id,
      message=(
        f"{Text.admin.REJECT_ACTION.value}\n\n"
        f"Row ID: {parts[1]}"
      ),
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

    async with SessionFactory() as session:
      repository = UserRepository(session)
      admin_ids = await repository.list_vk_admin_ids()
      if user_id not in admin_ids:
        await send_vk_message(
          user_id=user_id,
          message=Text.admin.NO_RIGHTS.value,
        )
        return PlainTextResponse("ok")

      use_case = LinkPendingUserUseCase(repository)
      try:
        linked_user = await use_case.execute(
          pending_row_id=int(parts[1]),
          existing_row_id=int(parts[2]),
        )
      except UserNotFoundError:
        await send_vk_message(
          user_id=user_id,
          message=Text.admin.USER_NOT_FOUND.value,
        )
        return PlainTextResponse("ok")
      except UserLinkConflictError:
        await send_vk_message(
          user_id=user_id,
          message=Text.admin.LINK_CONFLICT.value,
        )
        return PlainTextResponse("ok")

    await send_vk_message(
      user_id=user_id,
      message=(
        f"{Text.admin.LINK_SUCCESS.value}\n\n"
        f"Row ID: {linked_user.row_id}\n"
        f"Имя: {linked_user.name}\n"
        f"Telegram ID: {linked_user.telegram_id}\n"
        f"VK ID: {linked_user.vk_id}"
      ),
    )
    return PlainTextResponse("ok")

  if text == Buttons.new_user.REGISTRATION.value:
    vk_user_states[user_id] = WAITING_FOR_NAME
    await send_vk_message(
      user_id=user_id,
      message=Text.user.REGISTRATION_NEW_USER.value,
    )
    return PlainTextResponse("ok")

  if text == Buttons.new_user.ALREADY_REGISTERED_TG.value:
    vk_user_states[user_id] = WAITING_FOR_NAME
    await send_vk_message(
      user_id=user_id,
      message=Text.user.REGISTRATION_LINK_TG.value,
    )
    return PlainTextResponse("ok")

  if vk_user_states.get(user_id) == WAITING_FOR_NAME:
    name = " ".join(text.split())
    if len(name.split()) < 2:
      await send_vk_message(
        user_id=user_id,
        message=Text.user.REGISTRATION_INVALID_NAME.value,
      )
      return PlainTextResponse("ok")

    async with SessionFactory() as session:
      repository = UserRepository(session)
      use_case = RequestRegistrationUseCase(repository)

      try:
        user = await use_case.execute(name=name, vk_id=user_id)
      except UserIdentityRequiredError:
        await send_vk_message(
          user_id=user_id,
          message=Text.user.REGISTRATION_ID_ERROR.value,
        )
        return PlainTextResponse("ok")
      except UserAlreadyRegisteredError:
        vk_user_states.pop(user_id, None)
        await send_vk_message(
          user_id=user_id,
          message=Text.user.REGISTRATION_EXIST.value,
          keyboard=main_keyboard,
        )
        return PlainTextResponse("ok")
      except UserRegistrationPendingError:
        vk_user_states.pop(user_id, None)
        await send_vk_message(
          user_id=user_id,
          message=Text.user.REGISTRATION_PENDING.value,
          keyboard=main_keyboard,
        )
        return PlainTextResponse("ok")

      admin_ids = await repository.list_vk_admin_ids()
      approved_users = await repository.list_approved()

    vk_user_states.pop(user_id, None)
    await notify_admins_about_registration(
      row_id=user.row_id,
      name=name,
      vk_id=user_id,
      admin_ids=admin_ids,
      approved_users=approved_users,
    )
    await send_vk_message(
      user_id=user_id,
      message=Text.user.REGISTRATION_WAIT.value,
      keyboard=main_keyboard,
    )

  return PlainTextResponse("ok")
