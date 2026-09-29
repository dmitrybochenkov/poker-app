from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.exceptions import ApplicationError
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_param_repository import PokerParamRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.user_repository import UserRepository


class StartPokerNotAuthorizedError(ApplicationError):
  """The canonical actor is missing, unapproved, or not an administrator."""


class PokerAlreadyStartedError(ApplicationError):
  """An active poker game already exists."""


class PokerParamsNotFoundError(ApplicationError):
  """The selected poker parameters do not exist."""


@dataclass(frozen=True)
class StartPokerResult:
  poker_id: int
  recipient_user_ids: tuple[int, ...]


class StartPokerUseCase:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session
    self.poker_repository = PokerRepository(session)
    self.poker_param_repository = PokerParamRepository(session)
    self.poker_data_repository = PokerDataRepository(session)
    self.user_repository = UserRepository(session)

  async def get_start_data(self) -> tuple[bool, list]:
    started = await self.poker_repository.get_started()
    if started is not None:
      return False, []
    params = await self.poker_param_repository.list_all()
    return True, params

  async def execute(self, *, actor_user_id: int, params_id: int) -> StartPokerResult:
    try:
      actor = await self.user_repository.get_by_row_id(actor_user_id)
      if actor is None or not actor.is_approved or not actor.is_admin:
        raise StartPokerNotAuthorizedError

      param = await self.poker_param_repository.get_by_row_id(params_id)
      if param is None:
        raise PokerParamsNotFoundError

      poker = await self.poker_repository.create_if_none_started(params_id=params_id)
      if poker is None:
        raise PokerAlreadyStartedError

      await self.poker_data_repository.add_player_without_commit(
        poker_id=int(poker.row_id),
        date=poker.date,
        player_id=int(actor.row_id),
        player_name=actor.name,
      )
      recipient_user_ids = await self.user_repository.list_approved_user_ids()
      await self.session.commit()
    except Exception:
      await self.session.rollback()
      raise

    return StartPokerResult(
      poker_id=int(poker.row_id),
      recipient_user_ids=tuple(recipient_user_ids),
    )
