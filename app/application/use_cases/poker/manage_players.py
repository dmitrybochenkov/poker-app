from app.db.repositories.buyin_data_repository import BuyinDataRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository


class ManagePokerPlayersUseCase:
  def __init__(
    self,
    poker_repository: PokerRepository,
    poker_data_repository: PokerDataRepository,
    buyin_data_repository: BuyinDataRepository | None = None,
  ) -> None:
    self.poker_repository = poker_repository
    self.poker_data_repository = poker_data_repository
    self.buyin_data_repository = buyin_data_repository

  async def add_player_to_active_poker(
    self,
    *,
    player_id: int,
    player_name: str,
    is_prev_winner: bool = False,
  ):
    active = await self.poker_repository.get_started()
    if active is None:
      return None
    poker, _ = active
    existing = await self.poker_data_repository.get_player(date=poker.date, player_id=player_id)
    if existing is not None:
      return existing
    return await self.poker_data_repository.add_player(
      date=poker.date,
      player_id=player_id,
      player_name=player_name,
      is_prev_winner=is_prev_winner,
    )

  async def list_active_poker_players(self):
    active = await self.poker_repository.get_started()
    if active is None:
      return []
    poker, _ = active
    return await self.poker_data_repository.list_players(date=poker.date)

  async def set_cashier_for_active_poker(self, *, cashier_id: int):
    active = await self.poker_repository.get_started()
    if active is None:
      return None
    poker, _ = active
    return await self.poker_repository.set_cashier(poker, cashier_id=cashier_id)

  async def remove_player_from_active_poker(self, *, player_id: int) -> bool | None:
    active = await self.poker_repository.get_started()
    if active is None:
      return None
    poker, _ = active
    return await self.poker_data_repository.remove_player(date=poker.date, player_id=player_id)

  async def add_buyin_to_active_player(self, *, player_id: int, buyins_count: int):
    active = await self.poker_repository.get_started()
    if active is None:
      return None
    poker, _ = active
    updated = await self.poker_data_repository.add_buyins(
      date=poker.date,
      player_id=player_id,
      buyins_count=buyins_count,
    )
    if updated is None:
      return None
    if self.buyin_data_repository is not None:
      await self.buyin_data_repository.add_buyin(
        poker_date=poker.date,
        player_id=player_id,
        player_name=updated.player_name,
        buyins_count=buyins_count,
      )
      await self.buyin_data_repository.session.commit()
    return updated

  async def set_cashout_for_active_player(self, *, player_id: int, money_kopecks: int):
    active = await self.poker_repository.get_started()
    if active is None:
      return None
    poker, _ = active
    return await self.poker_data_repository.set_cashout(
      date=poker.date,
      player_id=player_id,
      money_kopecks=money_kopecks,
    )
