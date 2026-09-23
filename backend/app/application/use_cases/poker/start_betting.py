from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.exceptions import ApplicationError
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.user_repository import UserRepository


class StartBettingNotAuthorizedError(ApplicationError):
    """The canonical actor is missing, unapproved, or not an administrator."""


class ActivePokerNotFoundError(ApplicationError):
    """There is no active poker game whose betting can be opened."""


class PokerAwaitingChipsError(ApplicationError):
    """The poker game is already waiting for chip input."""


class BettingAlreadyOpenError(ApplicationError):
    """Betting has already been opened for the active poker game."""


@dataclass(frozen=True)
class StartBettingResult:
    poker_id: int
    recipient_user_ids: tuple[int, ...]


class StartBettingUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.poker_repository = PokerRepository(session)
        self.user_repository = UserRepository(session)

    async def execute(self, *, actor_user_id: int) -> StartBettingResult:
        try:
            actor = await self.user_repository.get_by_row_id(actor_user_id)
            if actor is None or not actor.is_approved or not actor.is_admin:
                raise StartBettingNotAuthorizedError

            active = await self.poker_repository.get_started()
            if active is None:
                raise ActivePokerNotFoundError
            poker, _ = active
            if poker.is_ready_for_chips_entering:
                raise PokerAwaitingChipsError
            if poker.is_bettable:
                raise BettingAlreadyOpenError

            recipient_user_ids = (
                await self.user_repository.list_approved_notification_user_ids()
            )
            changed = await self.poker_repository.mark_betting_started(poker_id=int(poker.row_id))
            if not changed:
                raise BettingAlreadyOpenError

            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        return StartBettingResult(
            poker_id=int(poker.row_id),
            recipient_user_ids=tuple(recipient_user_ids),
        )
