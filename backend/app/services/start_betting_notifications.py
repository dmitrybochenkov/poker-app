import logging

from app.bot.shared.chips_runtime import (
    TG_ADMIN_ROOM_STATUS_MSG_IDS,
    VK_ADMIN_ROOM_STATUS_MSG_IDS,
)
from app.bot.shared.texts.texts import Text
from app.bot.telegram import runtime as telegram_runtime
from app.bot.telegram.keyboards import betting_keyboard as tg_betting_keyboard
from app.bot.vk.api import (
    delete_vk_message_by_id,
    send_vk_message,
    unpin_vk_message,
)
from app.bot.vk.keyboards import betting_keyboard as vk_betting_keyboard
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory

logger = logging.getLogger(__name__)


class BettingStartedNotificationAdapter:
    async def notify(self, *, user_ids: tuple[int, ...]) -> None:
        async with SessionFactory() as session:
            recipients = await UserRepository(session).list_by_row_ids(user_ids)

        await self._clear_room_status_messages()
        for user in recipients:
            if user.notification_platform == "tg" and user.telegram_id is not None:
                if telegram_runtime.telegram_bot is None:
                    continue
                try:
                    await telegram_runtime.telegram_bot.send_message(
                        chat_id=int(user.telegram_id),
                        text=Text.user.START_BETTING.value,
                        reply_markup=tg_betting_keyboard,
                    )
                except Exception:
                    logger.exception(
                        "Failed to announce betting start to Telegram user %s",
                        user.telegram_id,
                    )
            elif user.notification_platform == "vk" and user.vk_id is not None:
                try:
                    await send_vk_message(
                        user_id=int(user.vk_id),
                        message=Text.user.START_BETTING.value,
                        keyboard=vk_betting_keyboard,
                    )
                except Exception:
                    logger.exception(
                        "Failed to announce betting start to VK user %s",
                        user.vk_id,
                    )

    async def _clear_room_status_messages(self) -> None:
        if telegram_runtime.telegram_bot is not None:
            for chat_id, message_id in list(TG_ADMIN_ROOM_STATUS_MSG_IDS.items()):
                try:
                    await telegram_runtime.telegram_bot.unpin_chat_message(
                        chat_id=int(chat_id),
                        message_id=int(message_id),
                    )
                except Exception:
                    pass
                try:
                    await telegram_runtime.telegram_bot.delete_message(
                        chat_id=int(chat_id),
                        message_id=int(message_id),
                    )
                except Exception:
                    pass

        for peer_id, message_id in list(VK_ADMIN_ROOM_STATUS_MSG_IDS.items()):
            try:
                await unpin_vk_message(peer_id=int(peer_id))
            except Exception:
                pass
            try:
                await delete_vk_message_by_id(
                    peer_id=int(peer_id),
                    message_id=int(message_id),
                )
            except Exception:
                pass

        TG_ADMIN_ROOM_STATUS_MSG_IDS.clear()
        VK_ADMIN_ROOM_STATUS_MSG_IDS.clear()
