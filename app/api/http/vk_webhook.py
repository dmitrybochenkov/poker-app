from fastapi import APIRouter, HTTPException, status
from fastapi.responses import PlainTextResponse

from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.texts.texts import Text
from app.bot.vk.api import send_vk_message
from app.bot.vk.handlers_admin import handle_admin_text_commands, handle_message_event
from app.bot.vk.handlers_user import handle_user_message_event, handle_user_message_new
from app.bot.vk.keyboards import main_keyboard
from app.bot.vk.state import vk_user_contexts, vk_user_states
from app.config.settings import settings

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

  if event_type == "message_event":
    event_object = payload.get("object", {})
    admin_response = await handle_message_event(event_object)
    if admin_response is not None:
      return admin_response
    user_response = await handle_user_message_event(event_object)
    if user_response is not None:
      return user_response
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

  admin_cmd_response = await handle_admin_text_commands(user_id=user_id, text=text)
  if admin_cmd_response is not None:
    return admin_cmd_response

  user_response = await handle_user_message_new(user_id=user_id, text=text)
  if user_response is not None:
    return user_response

  if text == Buttons.new_user.ABOUT.value:
    await send_vk_message(
      user_id=user_id,
      message=Text.user.BOT_INFO.value,
      keyboard=main_keyboard,
    )
    return PlainTextResponse("ok")

  return PlainTextResponse("ok")
