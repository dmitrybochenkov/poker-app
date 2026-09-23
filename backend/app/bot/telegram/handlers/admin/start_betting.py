from aiogram.types import CallbackQuery, Message

from app.application.use_cases.poker.start_betting import (
    ActivePokerNotFoundError,
    BettingAlreadyOpenError,
    PokerAwaitingChipsError,
    StartBettingNotAuthorizedError,
)
from app.bot.shared.texts.texts import Text
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory
from app.services.start_betting_flow import execute_start_betting

from .common import _clear_inline_keyboard


async def _execute_for_telegram_id(telegram_id: int) -> str:
    async with SessionFactory() as session:
        actor = await UserRepository(session).get_by_telegram_id(telegram_id)
        actor_user_id = int(actor.row_id) if actor is not None else -1

    try:
        await execute_start_betting(actor_user_id=actor_user_id)
    except StartBettingNotAuthorizedError:
        return Text.admin.NO_RIGHTS.value
    except ActivePokerNotFoundError:
        return Text.admin.POKER_ACTIVE_NOT_FOUND.value
    except PokerAwaitingChipsError:
        return Text.user.FINISH_CHIPS_NOT_READY.value
    except BettingAlreadyOpenError:
        return Text.admin.BETTING_ALREADY_OPEN.value
    return Text.admin.BETTING_START_SUCCESS.value


async def start_betting(message: Message) -> None:
    if message.from_user is None:
        await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
        return
    await message.answer(await _execute_for_telegram_id(int(message.from_user.id)))


async def start_betting_inline(callback: CallbackQuery) -> None:
    if callback.from_user is None:
        await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
        return

    result_text = await _execute_for_telegram_id(int(callback.from_user.id))
    await callback.answer(result_text, show_alert=True)
    if result_text == Text.admin.NO_RIGHTS.value:
        return
    await _clear_inline_keyboard(callback)
    if callback.message is not None:
        try:
            await callback.message.delete()
        except Exception:
            pass
