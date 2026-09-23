from aiogram.types import Message

from app.application.use_cases.poker.finish_poker import (
    ActivePokerNotFoundError,
    FinishPokerNotAuthorizedError,
)
from app.bot.shared.identity import resolve_telegram_user_id
from app.bot.shared.texts.texts import Text
from app.db.session import SessionFactory
from app.services.finish_poker_flow import execute_finish_poker

from .common import _upsert_tg_admin_chips_status, logger


async def finish_poker(message: Message) -> None:
    if message.from_user is None:
        await message.answer(Text.admin.IDENTIFY_USER_ERROR.value)
        return

    async with SessionFactory() as session:
        actor_user_id = await resolve_telegram_user_id(
            session=session,
            telegram_id=int(message.from_user.id),
        )

    try:
        result = await execute_finish_poker(actor_user_id=actor_user_id or -1)
    except FinishPokerNotAuthorizedError:
        await message.answer(Text.admin.NO_RIGHTS.value)
        return
    except ActivePokerNotFoundError:
        await message.answer(Text.admin.POKER_ACTIVE_NOT_FOUND.value)
        return

    await message.answer(Text.admin.POKER_FINISH_SUCCESS.value)
    if result.recipient_user_ids:
        try:
            async with SessionFactory() as session:
                await _upsert_tg_admin_chips_status(
                    session=session,
                    poker_date=result.poker_date,
                )
        except Exception:
            logger.exception(
                "Failed to refresh Telegram chips status for poker %s",
                result.poker_id,
            )
