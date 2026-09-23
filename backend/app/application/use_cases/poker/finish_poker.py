from dataclasses import dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.exceptions import ApplicationError
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.poker_room_denied_repository import PokerRoomDeniedRepository
from app.db.repositories.user_repository import UserRepository


class FinishPokerNotAuthorizedError(ApplicationError):
    """The canonical actor is missing, unapproved, or not an administrator."""


class ActivePokerNotFoundError(ApplicationError):
    """There is no active poker game to finish."""


@dataclass(frozen=True)
class FinishPokerResult:
    poker_id: int
    poker_date: date
    participant_user_ids: tuple[int, ...]


class FinishPokerUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.poker_repository = PokerRepository(session)
        self.poker_data_repository = PokerDataRepository(session)
        self.poker_room_denied_repository = PokerRoomDeniedRepository(session)
        self.user_repository = UserRepository(session)

    async def execute(self, *, actor_user_id: int) -> FinishPokerResult:
        try:
            actor = await self.user_repository.get_by_row_id(actor_user_id)
            if actor is None or not actor.is_approved or not actor.is_admin:
                raise FinishPokerNotAuthorizedError

            active = await self.poker_repository.get_started()
            if active is None:
                raise ActivePokerNotFoundError
            poker, _ = active
            players = await self.poker_data_repository.list_players(date=poker.date)

            changed = await self.poker_repository.mark_finished_for_chips(
                poker_id=int(poker.row_id)
            )
            if not changed:
                raise ActivePokerNotFoundError

            await self.poker_room_denied_repository.clear_all_without_commit()
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        return FinishPokerResult(
            poker_id=int(poker.row_id),
            poker_date=poker.date,
            participant_user_ids=tuple(int(player.player_id) for player in players),
        )
