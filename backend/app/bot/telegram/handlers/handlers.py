from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import ErrorEvent

from app.bot.telegram.handlers.handlers_admin import router as admin_router
from app.bot.telegram.handlers.handlers_user import router as user_router

router = Router()
router.include_router(user_router)
router.include_router(admin_router)


@router.error()
async def ignore_not_modified_error(event: ErrorEvent) -> bool:
  exception = event.exception
  if isinstance(exception, TelegramBadRequest) and "message is not modified" in str(exception).lower():
    return True
  return False
