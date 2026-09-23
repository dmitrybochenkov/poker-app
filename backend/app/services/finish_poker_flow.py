import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.ports.notifications import CanonicalRecipientNotifier
from app.application.use_cases.poker.finish_poker import (
    FinishPokerResult,
    FinishPokerUseCase,
)
from app.db.session import SessionFactory

logger = logging.getLogger(__name__)


class FinishPokerFlow:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        notifier: CanonicalRecipientNotifier,
    ) -> None:
        self.session_factory = session_factory
        self.notifier = notifier

    async def execute(self, *, actor_user_id: int) -> FinishPokerResult:
        async with self.session_factory() as session:
            result = await FinishPokerUseCase(session).execute(actor_user_id=actor_user_id)

        try:
            await self.notifier.notify(recipient_user_ids=result.recipient_user_ids)
        except Exception:
            logger.exception(
                "Failed to run post-commit Finish Poker notifications for poker %s",
                result.poker_id,
            )
        return result


async def execute_finish_poker(*, actor_user_id: int) -> FinishPokerResult:
    from app.services.finish_poker_notifications import PokerFinishedNotificationAdapter

    return await FinishPokerFlow(
        session_factory=SessionFactory,
        notifier=PokerFinishedNotificationAdapter(),
    ).execute(actor_user_id=actor_user_id)
