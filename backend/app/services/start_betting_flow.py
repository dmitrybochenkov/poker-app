import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.ports.notifications import CanonicalRecipientNotifier
from app.application.use_cases.poker.start_betting import (
    StartBettingResult,
    StartBettingUseCase,
)
from app.db.session import SessionFactory

logger = logging.getLogger(__name__)


class StartBettingFlow:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        notifier: CanonicalRecipientNotifier,
    ) -> None:
        self.session_factory = session_factory
        self.notifier = notifier

    async def execute(self, *, actor_user_id: int) -> StartBettingResult:
        async with self.session_factory() as session:
            result = await StartBettingUseCase(session).execute(actor_user_id=actor_user_id)

        try:
            await self.notifier.notify(user_ids=result.recipient_user_ids)
        except Exception:
            logger.exception(
                "Failed to run post-commit Start Betting notifications for poker %s",
                result.poker_id,
            )
        return result


async def execute_start_betting(*, actor_user_id: int) -> StartBettingResult:
    from app.services.start_betting_notifications import BettingStartedNotificationAdapter

    return await StartBettingFlow(
        session_factory=SessionFactory,
        notifier=BettingStartedNotificationAdapter(),
    ).execute(actor_user_id=actor_user_id)
