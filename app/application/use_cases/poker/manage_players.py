from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository


class ManagePokerPlayersUseCase:
  def __init__(
    self,
    poker_repository: PokerRepository,
    poker_data_repository: PokerDataRepository,
  ) -> None:
    self.poker_repository = poker_repository
    self.poker_data_repository = poker_data_repository

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
