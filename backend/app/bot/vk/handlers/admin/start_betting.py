from fastapi.responses import PlainTextResponse

from app.application.use_cases.poker.start_betting import (
    ActivePokerNotFoundError,
    BettingAlreadyOpenError,
    PokerAwaitingChipsError,
    StartBettingNotAuthorizedError,
)
from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.identity import resolve_vk_user_id
from app.bot.shared.texts.texts import Text
from app.bot.vk.api import send_vk_message
from app.db.session import SessionFactory
from app.services.start_betting_flow import execute_start_betting

from .common import HANDLER_UNMATCHED


async def handle_admin_room_start_betting_text(*, user_id, text):
    if text != Buttons.admin_room.START_BETTING.value:
        return HANDLER_UNMATCHED

    async with SessionFactory() as session:
        actor_user_id = await resolve_vk_user_id(session=session, vk_id=int(user_id))

    try:
        await execute_start_betting(actor_user_id=actor_user_id or -1)
    except StartBettingNotAuthorizedError:
        response_text = Text.admin.NO_RIGHTS.value
    except ActivePokerNotFoundError:
        response_text = Text.admin.POKER_ACTIVE_NOT_FOUND.value
    except PokerAwaitingChipsError:
        response_text = Text.user.FINISH_CHIPS_NOT_READY.value
    except BettingAlreadyOpenError:
        response_text = Text.admin.BETTING_ALREADY_OPEN.value
    else:
        response_text = Text.admin.BETTING_START_SUCCESS.value

    await send_vk_message(user_id=user_id, message=response_text)
    return PlainTextResponse("ok")
