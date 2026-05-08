from html import escape

from aiogram.types import InlineKeyboardMarkup

from app.bot.shared.texts import Text
from app.db.models.user import User


async def notify_admins_about_registration(
  *,
  name: str,
  telegram_id: int | None,
  vk_id: int | None = None,
  requester_platform: str,
  admin_chat_ids: list[int],
  linked_to_user: User | None = None,
  reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
  from app.bot.telegram.runtime import telegram_bot

  if telegram_bot is None or not admin_chat_ids:
    return

  kind_line = (
    Text.admin.NEW_REGISTRATION_KIND_LINK.value
    if linked_to_user is not None
    else Text.admin.NEW_REGISTRATION_KIND_NEW.value
  )
  text = (
    f"{Text.admin.NEW_REGISTRATION.value}\n\n"
    f"{kind_line}\n"
    f"Имя: {escape(name)}\n"
    f"Платформа: {requester_platform.upper()}"
  )
  if telegram_id is not None:
    profile_link = f'<a href="tg://user?id={telegram_id}">{Text.admin.PROFILE_LINK_LABEL.value}</a>'
    text = f"{text}\n{Text.admin.PROFILE_LINK_LABEL.value}: {profile_link}"
  elif vk_id is not None:
    text = f"{text}\n{Text.admin.PROFILE_LINK_LABEL.value}: https://vk.com/id{vk_id}"
  if linked_to_user is not None:
    text = f"{text}\nСуществующая запись: {escape(linked_to_user.name)}"
  for chat_id in admin_chat_ids:
    await telegram_bot.send_message(
      chat_id=chat_id,
      text=text,
      parse_mode="HTML",
      reply_markup=reply_markup,
    )


async def notify_user_about_approval(*, telegram_id: int, approved: bool) -> None:
  from app.bot.telegram.runtime import telegram_bot

  if telegram_bot is None:
    return

  text = (
    Text.user.REGISTRATION_APPROVED.value
    if approved
    else Text.user.REGISTRATION_NOT_APPROVED.value
  )
  await telegram_bot.send_message(chat_id=telegram_id, text=text)
