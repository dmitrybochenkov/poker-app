import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.ports.notifications import CanonicalRecipientNotifier
from app.application.use_cases.poker.start_poker import StartPokerResult, StartPokerUseCase
from app.db.session import SessionFactory

logger = logging.getLogger(__name__)


class StartPokerFlow:
  def __init__(
    self,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    notifier: CanonicalRecipientNotifier,
  ) -> None:
    self.session_factory = session_factory
    self.notifier = notifier

  async def execute(self, *, actor_user_id: int, params_id: int) -> StartPokerResult:
    async with self.session_factory() as session:
      result = await StartPokerUseCase(session).execute(
        actor_user_id=actor_user_id,
        params_id=params_id,
      )

    try:
      await self.notifier.notify(user_ids=result.recipient_user_ids)
    except Exception:
      logger.exception(
        "Failed to run post-commit Start Poker notifications for poker %s",
        result.poker_id,
      )
    return result


async def execute_start_poker(*, actor_user_id: int, params_id: int) -> StartPokerResult:
  from app.services.start_poker_notifications import PokerStartedNotificationAdapter

  return await StartPokerFlow(
    session_factory=SessionFactory,
    notifier=PokerStartedNotificationAdapter(),
  ).execute(actor_user_id=actor_user_id, params_id=params_id)
