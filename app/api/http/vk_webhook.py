from fastapi import APIRouter, HTTPException, status

from app.application.exceptions import (
  UserAlreadyRegisteredError,
  UserIdentityRequiredError,
  UserRegistrationPendingError,
)
from app.application.use_cases.request_registration import RequestRegistrationUseCase
from app.bot.shared.buttons import Buttons
from app.bot.shared.texts import Text
from app.bot.vk.api import send_vk_message
from app.bot.vk.keyboards import main_keyboard
from app.bot.vk.notifications import notify_admins_about_registration
from app.bot.vk.state import WAITING_FOR_NAME, vk_user_states
from app.config.settings import settings
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory

router = APIRouter(prefix="/webhooks/vk", tags=["vk"])


@router.post("")
async def vk_webhook(payload: dict) -> str | dict[str, bool]:
  event_type = payload.get("type")

  if payload.get("secret") and settings.vk_secret_key:
    if payload["secret"] != settings.vk_secret_key:
      raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid VK secret",
      )

  if event_type == "confirmation":
    return settings.vk_confirmation_token

  if event_type != "message_new":
    return "ok"

  message = payload.get("object", {}).get("message", {})
  user_id = message.get("from_id")
  text = (message.get("text") or "").strip()

  if not user_id:
    return "ok"

  if text.lower() in {"начать", "start", "/start"}:
    vk_user_states.pop(user_id, None)
    await send_vk_message(
      user_id=user_id,
      message=Text.user.BOT_INFO.value,
      keyboard=main_keyboard,
    )
    return "ok"

  if text == Buttons.new_user.REGISTRATION.value:
    vk_user_states[user_id] = WAITING_FOR_NAME
    await send_vk_message(
      user_id=user_id,
      message=Text.user.REGISTRATION_NEW_USER.value,
    )
    return "ok"

  if vk_user_states.get(user_id) == WAITING_FOR_NAME:
    name = " ".join(text.split())
    if len(name.split()) < 2:
      await send_vk_message(
        user_id=user_id,
        message=Text.user.REGISTRATION_INVALID_NAME.value,
      )
      return "ok"

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
        return "ok"
      except UserAlreadyRegisteredError:
        vk_user_states.pop(user_id, None)
        await send_vk_message(
          user_id=user_id,
          message=Text.user.REGISTRATION_EXIST.value,
          keyboard=main_keyboard,
        )
        return "ok"
      except UserRegistrationPendingError:
        vk_user_states.pop(user_id, None)
        await send_vk_message(
          user_id=user_id,
          message=Text.user.REGISTRATION_PENDING.value,
          keyboard=main_keyboard,
        )
        return "ok"

      admin_ids = await repository.list_vk_admin_ids()

    vk_user_states.pop(user_id, None)
    await notify_admins_about_registration(
      row_id=user.row_id,
      name=name,
      vk_id=user_id,
      admin_ids=admin_ids,
    )
    await send_vk_message(
      user_id=user_id,
      message=Text.user.REGISTRATION_WAIT.value,
      keyboard=main_keyboard,
    )

  return "ok"
