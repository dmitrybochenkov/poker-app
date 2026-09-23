import logging

from fastapi.responses import PlainTextResponse

from app.application.use_cases.poker.finish_poker import (
    ActivePokerNotFoundError,
    FinishPokerNotAuthorizedError,
)
from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.identity import resolve_vk_user_id
from app.bot.shared.texts.texts import Text
from app.bot.vk.api import send_vk_message
from app.db.session import SessionFactory
from app.services.finish_poker_flow import execute_finish_poker

from .common import HANDLER_UNMATCHED, _upsert_vk_admin_chips_status

logger = logging.getLogger(__name__)


async def handle_admin_room_finish_poker_text(*, user_id, text):
    if text != Buttons.admin_room.FINISH_POKER.value:
        return HANDLER_UNMATCHED

    async with SessionFactory() as session:
        actor_user_id = await resolve_vk_user_id(
            session=session,
            vk_id=int(user_id),
        )

    try:
        result = await execute_finish_poker(actor_user_id=actor_user_id or -1)
    except FinishPokerNotAuthorizedError:
        response_text = Text.admin.NO_RIGHTS.value
        result = None
    except ActivePokerNotFoundError:
        response_text = Text.admin.POKER_ACTIVE_NOT_FOUND.value
        result = None
    else:
        response_text = Text.admin.POKER_FINISH_SUCCESS.value

    await send_vk_message(user_id=user_id, message=response_text)
    if result is not None and result.recipient_user_ids:
        try:
            async with SessionFactory() as session:
                await _upsert_vk_admin_chips_status(
                    session=session,
                    poker_date=result.poker_date,
                )
        except Exception:
            logger.exception(
                "Failed to refresh VK chips status for poker %s",
                result.poker_id,
            )
    return PlainTextResponse("ok")
