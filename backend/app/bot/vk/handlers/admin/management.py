from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.guards import is_vk_admin
from app.bot.shared.texts.texts import Text
from app.bot.vk.api import (
    send_vk_message,
)
from app.bot.vk.keyboards import (
    make_admin_candidates_keyboard,
)
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory
from fastapi.responses import PlainTextResponse

from .common import (
    HANDLER_UNMATCHED,
)


async def _text_1_08(*, user_id, text):
    if text == Buttons.admin_main.MAKE_ADMIN.value:
        async with SessionFactory() as session:
            repository = UserRepository(session)
            if not await is_vk_admin(session=session, vk_id=user_id):
                await send_vk_message(user_id=user_id, message=Text.admin.NO_RIGHTS.value)
                return PlainTextResponse("ok")
            approved_users = await repository.list_approved()
            candidates = [user for user in approved_users if not user.is_admin]
            if not candidates:
                await send_vk_message(user_id=user_id, message=Text.admin.MAKE_ADMIN_EMPTY.value)
                return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id,
            message=Text.admin.MAKE_ADMIN_PROMPT.value,
            keyboard=make_admin_candidates_keyboard(users=candidates),
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED
