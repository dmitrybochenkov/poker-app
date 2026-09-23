import logging

from app.bot.shared.texts.texts import Text
from app.bot.telegram import runtime as telegram_runtime
from app.bot.telegram.keyboards import main_dynamic_keyboard as tg_main_dynamic_keyboard
from app.bot.vk.api import send_vk_message
from app.bot.vk.keyboards import main_dynamic_keyboard as vk_main_dynamic_keyboard
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory

logger = logging.getLogger(__name__)


class PokerFinishedNotificationAdapter:
    async def notify(self, *, user_ids: tuple[int, ...]) -> None:
        async with SessionFactory() as session:
            recipients = await UserRepository(session).list_by_row_ids(user_ids)

        for user in recipients:
            if user.is_admin or user.notification_platform is None:
                continue
            if user.notification_platform == "tg" and user.telegram_id is not None:
                if telegram_runtime.telegram_bot is None:
                    continue
                try:
                    await telegram_runtime.telegram_bot.send_message(
                        chat_id=int(user.telegram_id),
                        text=Text.user.POKER_FINISHED_ENTER_CHIPS.value,
                        reply_markup=tg_main_dynamic_keyboard(
                            is_admin=False,
                            has_active_poker=False,
                            has_active_poll=False,
                        ),
                    )
                except Exception:
                    logger.exception(
                        "Failed to request chips from Telegram user %s",
                        user.telegram_id,
                    )
            elif user.notification_platform == "vk" and user.vk_id is not None:
                try:
                    await send_vk_message(
                        user_id=int(user.vk_id),
                        message=Text.user.POKER_FINISHED_ENTER_CHIPS.value,
                        keyboard=vk_main_dynamic_keyboard(
                            is_admin=False,
                            has_active_poker=False,
                            has_active_poll=False,
                        ),
                    )
                except Exception:
                    logger.exception(
                        "Failed to request chips from VK user %s",
                        user.vk_id,
                    )
