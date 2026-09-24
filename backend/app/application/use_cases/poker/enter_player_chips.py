from dataclasses import dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.user_repository import UserRepository


class EnterPlayerChipsNotAuthorizedError(Exception):
  pass


class PokerNotReadyForChipsError(Exception):
  pass


class PokerPlayerNotFoundError(Exception):
  pass


class InvalidChipStepError(Exception):
  def __init__(self, *, step: int) -> None:
    self.step = step


@dataclass(frozen=True)
class EnterPlayerChipsResult:
  poker_date: date
  player_id: int
  player_name: str
  buyins: int
  chips: int
  money_kopecks: int


class EnterPlayerChipsUseCase:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session
    self.user_repository = UserRepository(session)
    self.poker_repository = PokerRepository(session)
    self.poker_data_repository = PokerDataRepository(session)

  async def execute(
    self,
    *,
    actor_user_id: int,
    player_user_id: int,
    chips: int,
  ) -> EnterPlayerChipsResult:
    try:
      actor = await self.user_repository.get_by_row_id(int(actor_user_id))
      if actor is None or not actor.is_approved:
        raise EnterPlayerChipsNotAuthorizedError
      if int(actor.row_id) != int(player_user_id) and not actor.is_admin:
        raise EnterPlayerChipsNotAuthorizedError

      ready = await self.poker_repository.get_latest_ready_for_chips_with_params()
      if ready is None:
        raise PokerNotReadyForChipsError
      poker, params = ready

      step = max(1, int(params.bb_size_chips or 10) // 2)
      if int(chips) % step != 0:
        raise InvalidChipStepError(step=step)

      player = await self.poker_data_repository.get_player(
        date=poker.date,
        player_id=int(player_user_id),
      )
      if player is None:
        raise PokerPlayerNotFoundError

      money_kopecks = (
        (int(chips) - int(player.buyins) * int(params.buyin_size_chips))
        * int(params.buyin_size_kopecks)
      ) // int(params.buyin_size_chips)
      updated = await self.poker_data_repository.set_chips_and_cashout_without_commit(
        date=poker.date,
        player_id=int(player_user_id),
        chips=int(chips),
        money_kopecks=int(money_kopecks),
      )
      if updated is None:
        raise PokerPlayerNotFoundError
      await self.session.commit()
      await self.session.refresh(updated)
      return EnterPlayerChipsResult(
        poker_date=poker.date,
        player_id=int(updated.player_id),
        player_name=updated.player_name,
        buyins=int(updated.buyins),
        chips=int(updated.chips),
        money_kopecks=int(updated.money_kopecks),
      )
    except Exception:
      await self.session.rollback()
      raise
