from app.db.repositories.buyin_data_repository import BuyinDataRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_room_denied_repository import PokerRoomDeniedRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.user_repository import UserRepository


class ManagePokerPlayersUseCase:
  def __init__(
    self,
    poker_repository: PokerRepository,
    poker_data_repository: PokerDataRepository,
    buyin_data_repository: BuyinDataRepository | None = None,
    poker_room_denied_repository: PokerRoomDeniedRepository | None = None,
    user_repository: UserRepository | None = None,
  ) -> None:
    self.poker_repository = poker_repository
    self.poker_data_repository = poker_data_repository
    self.buyin_data_repository = buyin_data_repository
    self.poker_room_denied_repository = poker_room_denied_repository
    self.user_repository = user_repository

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
    removed = await self.poker_data_repository.remove_player(date=poker.date, player_id=player_id)
    if removed and self.poker_room_denied_repository is not None:
      is_admin = False
      if self.user_repository is not None:
        tg_user = await self.user_repository.get_by_telegram_id(int(player_id))
        vk_user = await self.user_repository.get_by_vk_id(int(player_id))
        is_admin = bool((tg_user and tg_user.is_admin) or (vk_user and vk_user.is_admin))
      if not is_admin:
        platform = "tg" if int(player_id) < 2_000_000_000 else "vk"
        await self.poker_room_denied_repository.add(
          date=poker.date,
          player_id=player_id,
          platform=platform,
        )
    return removed

  async def is_denied_for_active_poker(self, *, player_id: int) -> bool:
    if self.poker_room_denied_repository is None:
      return False
    active = await self.poker_repository.get_started()
    if active is None:
      return False
    poker, _ = active
    return await self.poker_room_denied_repository.is_denied(
      date=poker.date,
      player_id=player_id,
    )

  async def list_denied_for_active_poker(self):
    if self.poker_room_denied_repository is None:
      return []
    active = await self.poker_repository.get_started()
    if active is None:
      return []
    poker, _ = active
    return await self.poker_room_denied_repository.list_by_date(date=poker.date)

  async def remove_denied_for_active_poker(self, *, player_id: int) -> bool:
    if self.poker_room_denied_repository is None:
      return False
    active = await self.poker_repository.get_started()
    if active is None:
      return False
    poker, _ = active
    return await self.poker_room_denied_repository.remove(
      date=poker.date,
      player_id=player_id,
    )

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

  async def list_players_for_chips_entry(self):
    poker = await self.poker_repository.get_latest_ready_for_chips()
    if poker is None:
      return []
    return await self.poker_data_repository.list_players(date=poker.date)

  async def set_chips_for_ready_poker_player(self, *, player_id: int, chips: int):
    poker = await self.poker_repository.get_latest_ready_for_chips()
    if poker is None:
      return None
    return await self.poker_data_repository.set_chips(
      date=poker.date,
      player_id=player_id,
      chips=chips,
    )
