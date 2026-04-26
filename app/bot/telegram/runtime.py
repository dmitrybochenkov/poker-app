from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

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
