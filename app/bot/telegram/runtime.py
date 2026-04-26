from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup

from app.bot.telegram.handlers import router
from app.config.settings import settings

telegram_dispatcher = Dispatcher(storage=MemoryStorage())
telegram_dispatcher.include_router(router)

telegram_bot = Bot(token=settings.telegram_bot_token) if settings.telegram_bot_token else None


async def setup_telegram_webhook() -> None:
  if telegram_bot is None or not settings.public_base_url:
    return

  await telegram_bot.set_webhook(
    url=f"{settings.public_base_url.rstrip('/')}/webhooks/telegram",
    secret_token=settings.telegram_webhook_secret or None,
    drop_pending_updates=True,
  )


async def shutdown_telegram_bot() -> None:
  if telegram_bot is None:
    return

  await telegram_bot.session.close()


async def notify_admins_about_registration(
  *,
  row_id: int,
  name: str,
  telegram_id: int,
  admin_chat_ids: list[int],
  reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
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
  if telegram_bot is None:
    return

  text = (
    "Твоя регистрация подтверждена. Добро пожаловать!"
    if approved
    else "Твоя заявка была отклонена администратором."
  )
  await telegram_bot.send_message(chat_id=telegram_id, text=text)
