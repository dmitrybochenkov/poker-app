from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.http.health import router as health_router
from app.api.http.registration import router as registration_router
from app.api.http.telegram_webhook import router as telegram_webhook_router
from app.api.http.users import router as users_router
from app.api.http.vk_webhook import router as vk_webhook_router
from app.bot.telegram.runtime import setup_telegram_webhook, shutdown_telegram_bot
from app.config.settings import settings
from app.db.session import finalize_database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
  await setup_telegram_webhook()
  yield
  await shutdown_telegram_bot()
  await finalize_database()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.include_router(health_router)
app.include_router(registration_router)
app.include_router(telegram_webhook_router)
app.include_router(vk_webhook_router)
app.include_router(users_router)
