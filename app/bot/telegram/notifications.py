from aiogram.types import InlineKeyboardMarkup

from app.bot.shared.texts import Text


async def notify_admins_about_registration(
  *,
  row_id: int,
  name: str,
  name_needs_correction: bool,
  telegram_id: int,
  admin_chat_ids: list[int],
  reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
  from app.bot.telegram.runtime import telegram_bot

  if telegram_bot is None or not admin_chat_ids:
    return

  correction_note = (
    f"\n{Text.admin.NAME_REQUIRES_CORRECTION.value}"
    if name_needs_correction
    else ""
  )
  text = (
    f"{Text.admin.NEW_REGISTRATION.value}\n\n"
    f"Row ID: {row_id}\n"
    f"Имя: {name}\n"
    f"Telegram ID: {telegram_id}"
    f"{correction_note}"
  )
  for chat_id in admin_chat_ids:
    await telegram_bot.send_message(
      chat_id=chat_id,
      text=text,
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
