from aiogram.types import InlineKeyboardMarkup


async def notify_admins_about_registration(
  *,
  row_id: int,
  name: str,
  telegram_id: int,
  admin_chat_ids: list[int],
  reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
  from app.bot.telegram.runtime import telegram_bot

  if telegram_bot is None or not admin_chat_ids:
    return

  text = (
    "Новая заявка на регистрацию\n\n"
    f"Row ID: {row_id}\n"
    f"Имя: {name}\n"
    f"Telegram ID: {telegram_id}"
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
    "Твоя регистрация подтверждена. Добро пожаловать!"
    if approved
    else "Твоя заявка была отклонена администратором."
  )
  await telegram_bot.send_message(chat_id=telegram_id, text=text)
