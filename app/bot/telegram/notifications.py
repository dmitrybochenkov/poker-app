from html import escape

from aiogram.types import InlineKeyboardMarkup

from app.bot.shared.registration_hints import build_similar_users_hint
from app.bot.shared.texts import Text
from app.db.models.user import User


async def notify_admins_about_registration(
  *,
  row_id: int,
  name: str,
  telegram_id: int,
  all_users: list[User],
  admin_chat_ids: list[int],
  reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
  from app.bot.telegram.runtime import telegram_bot

  if telegram_bot is None or not admin_chat_ids:
    return

  profile_link = f'<a href="tg://user?id={telegram_id}">{Text.admin.PROFILE_LINK_LABEL.value}</a>'
  similar_users_hint = build_similar_users_hint(
    row_id=row_id,
    name=name,
    users=all_users,
  )
  text = (
    f"{Text.admin.NEW_REGISTRATION.value}\n\n"
    f"Row ID: {row_id}\n"
    f"Имя: {escape(name)}\n"
    f"Telegram ID: {telegram_id}\n"
    f"{Text.admin.PROFILE_LINK_LABEL.value}: {profile_link}"
  )
  if similar_users_hint:
    text = f"{text}\n\n{escape(similar_users_hint)}"
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
