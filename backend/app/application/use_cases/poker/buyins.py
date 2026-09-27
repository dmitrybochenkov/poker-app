from dataclasses import dataclass
from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.buyin_data_repository import BuyinDataRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.user_repository import UserRepository


class BuyinNotAuthorizedError(Exception):
  pass


class ActivePokerNotFoundError(Exception):
  pass


class PokerReadyForChipsError(Exception):
  pass


class PokerCashierRequiredError(Exception):
  pass


class BuyinPlayerNotFoundError(Exception):
  pass


class InvalidBuyinCountError(Exception):
  pass


@dataclass(frozen=True)
class BuyinResult:
  poker_date: date
  cashier_user_id: int
  player_user_id: int
  player_name: str
  added_buyins: int
  total_buyins: int
  big_buyin_count: int
  super_buyin_count: int
  applied: bool = True


@dataclass(frozen=True)
class CorrectBuyinResult:
  poker_date: date
  player_user_id: int
  player_name: str
  previous_buyins: int
  total_buyins: int
  big_buyin_count: int
  super_buyin_count: int


class AddBuyinUseCase:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def execute(
    self,
    *,
    actor_user_id: int | None,
    target_user_id: int,
    buyins_count: int,
    operation_id: str | None = None,
  ) -> BuyinResult:
    if int(buyins_count) <= 0:
      raise InvalidBuyinCountError
    async with self.session.begin():
      users = UserRepository(self.session)
      pokers = PokerRepository(self.session)
      players = PokerDataRepository(self.session)
      buyins = BuyinDataRepository(self.session)
      actor = await users.get_by_row_id(int(actor_user_id or -1))
      if actor is None or not actor.is_approved:
        raise BuyinNotAuthorizedError
      if int(actor.row_id) != int(target_user_id) and not actor.is_admin:
        raise BuyinNotAuthorizedError
      active = await pokers.get_started()
      if active is None:
        raise ActivePokerNotFoundError
      poker, params = active
      if poker.is_ready_for_chips_entering:
        raise PokerReadyForChipsError
      if poker.cashier_id is None:
        raise PokerCashierRequiredError
      player = await players.get_player(date=poker.date, player_id=int(target_user_id))
      if player is None:
        raise BuyinPlayerNotFoundError

      if operation_id is not None:
        existing = await buyins.get_by_operation_id(operation_id=operation_id)
        if existing is not None:
          return self._result_from_player(
            poker=poker,
            player=player,
            added_buyins=int(existing.buyins_count),
            applied=False,
          )
        try:
          async with self.session.begin_nested():
            await buyins.add_buyin(
              poker_date=poker.date,
              player_id=int(target_user_id),
              player_name=player.player_name,
              buyins_count=int(buyins_count),
              operation_id=operation_id,
            )
        except IntegrityError:
          existing = await buyins.get_by_operation_id(operation_id=operation_id)
          if existing is None:
            raise
          return self._result_from_player(
            poker=poker,
            player=player,
            added_buyins=int(existing.buyins_count),
            applied=False,
          )

      big_count, super_count = _special_buyin_counts(
        buyins_count=int(buyins_count),
        max_buyins=int(params.max_buyins),
        big_buyin=params.big_buyin,
        king_buyin=params.king_buyin,
        super_buyin=params.super_buyin,
        is_previous_winner=bool(player.is_prev_winner),
        current_big_count=int(player.big_buyin_count),
        current_super_count=int(player.super_buyin_count),
      )
      updated = await players.add_buyins_without_commit(
        date=poker.date,
        player_id=int(target_user_id),
        buyins_count=int(buyins_count),
        big_buyin_count=big_count,
        super_buyin_count=super_count,
      )
      if updated is None:
        raise BuyinPlayerNotFoundError
      if operation_id is None:
        await buyins.add_buyin(
          poker_date=poker.date,
          player_id=int(target_user_id),
          player_name=updated.player_name,
          buyins_count=int(buyins_count),
        )
      result = self._result_from_player(
        poker=poker,
        player=updated,
        added_buyins=int(buyins_count),
        applied=True,
      )
    return result

  @staticmethod
  def _result_from_player(*, poker, player, added_buyins: int, applied: bool) -> BuyinResult:
    return BuyinResult(
      poker.date,
      int(poker.cashier_id),
      int(player.player_id),
      player.player_name,
      added_buyins,
      int(player.buyins),
      int(player.big_buyin_count),
      int(player.super_buyin_count),
      applied,
    )


class CorrectBuyinUseCase:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def execute(
    self, *, actor_user_id: int | None, target_user_id: int, total_buyins: int
  ) -> CorrectBuyinResult:
    if int(total_buyins) < 0:
      raise InvalidBuyinCountError
    async with self.session.begin():
      users = UserRepository(self.session)
      pokers = PokerRepository(self.session)
      players = PokerDataRepository(self.session)
      actor = await users.get_by_row_id(int(actor_user_id or -1))
      if actor is None or not actor.is_approved or not actor.is_admin:
        raise BuyinNotAuthorizedError
      active = await pokers.get_started()
      if active is None:
        raise ActivePokerNotFoundError
      poker, _ = active
      player = await players.get_player(date=poker.date, player_id=int(target_user_id))
      if player is None:
        raise BuyinPlayerNotFoundError
      previous = int(player.buyins)
      if int(total_buyins) != previous:
        updated = await players.add_buyins_without_commit(
          date=poker.date,
          player_id=int(target_user_id),
          buyins_count=int(total_buyins) - previous,
        )
        if updated is None:
          raise BuyinPlayerNotFoundError
      else:
        updated = player
      result = CorrectBuyinResult(
        poker.date,
        int(updated.player_id),
        updated.player_name,
        previous,
        int(updated.buyins),
        int(updated.big_buyin_count),
        int(updated.super_buyin_count),
      )
    return result


def _special_buyin_counts(
  *,
  buyins_count: int,
  max_buyins: int,
  big_buyin: int | None,
  king_buyin: int | None,
  super_buyin: int | None,
  is_previous_winner: bool,
  current_big_count: int,
  current_super_count: int,
) -> tuple[int, int]:
  if max_buyins != 2:
    return 0, 0
  big_threshold = int(big_buyin or 5)
  super_threshold = int(super_buyin or 10)
  king_threshold = int(king_buyin or 15)
  allowed = set()
  if current_super_count == 0 and current_big_count < 2:
    allowed.add(big_threshold)
  if current_super_count == 0 and current_big_count == 0:
    allowed.add(super_threshold)
    if is_previous_winner:
      allowed.add(king_threshold)
  if buyins_count > max_buyins and buyins_count not in allowed:
    raise InvalidBuyinCountError
  if (
    is_previous_winner
    and current_big_count == 0
    and current_super_count == 0
    and buyins_count >= king_threshold
  ):
    return 1, 1
  if buyins_count >= super_threshold:
    if current_big_count == 0 and current_super_count == 0:
      return 0, 1
    if current_super_count == 0 and current_big_count < 2 and buyins_count >= big_threshold:
      return 1, 0
  if current_super_count == 0 and current_big_count < 2 and buyins_count >= big_threshold:
    return 1, 0
  return 0, 0
