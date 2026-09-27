from app.db.repositories.buyin_data_repository import BuyinDataRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_room_denied_repository import PokerRoomDeniedRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.user_repository import UserRepository


class CashierCandidateNotParticipantError(Exception):
  pass


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

  async def add_player_to_active_poker_and_allow(
    self,
    *,
    player_id: int,
    player_name: str,
    is_prev_winner: bool = False,
  ):
    session = self.poker_repository.session
    try:
      active = await self.poker_repository.get_started()
      if active is None:
        return None
      poker, _ = active
      participant = await self.poker_data_repository.get_player(
        date=poker.date,
        player_id=player_id,
      )
      if participant is None:
        participant = await self.poker_data_repository.add_player_without_commit(
          date=poker.date,
          player_id=player_id,
          player_name=player_name,
          is_prev_winner=is_prev_winner,
        )
      if self.poker_room_denied_repository is not None:
        await self.poker_room_denied_repository.remove_without_commit(
          user_row_id=player_id,
        )
      await session.commit()
      return participant
    except Exception:
      await session.rollback()
      raise

  async def list_active_poker_players(self):
    active = await self.poker_repository.get_started()
    if active is None:
      return []
    poker, _ = active
    return await self.poker_data_repository.list_players(date=poker.date)

  async def set_cashier_for_active_poker(self, *, cashier_id: int):
    session = self.poker_repository.session
    try:
      active = await self.poker_repository.get_started()
      if active is None:
        return None
      poker, _ = active
      participant = await self.poker_data_repository.get_player(
        date=poker.date,
        player_id=cashier_id,
      )
      if participant is None:
        raise CashierCandidateNotParticipantError
      updated = await self.poker_repository.set_cashier_without_commit(
        poker,
        cashier_id=cashier_id,
      )
      await session.commit()
      return updated
    except Exception:
      await session.rollback()
      raise

  async def remove_player_from_active_poker(self, *, player_id: int) -> bool | None:
    session = self.poker_repository.session
    try:
      active = await self.poker_repository.get_started()
      if active is None:
        return None
      poker, _ = active
      player = await self.poker_data_repository.get_player(
        date=poker.date, player_id=player_id
      )
      if player is None:
        return False

      if self.buyin_data_repository is not None:
        await self.buyin_data_repository.delete_for_player_on_date_without_commit(
          poker_date=poker.date,
          player_id=player_id,
        )
      removed = await self.poker_data_repository.remove_player_without_commit(
        date=poker.date, player_id=player_id
      )
      if removed and self.poker_room_denied_repository is not None:
        user = None
        if self.user_repository is not None:
          user = await self.user_repository.get_by_row_id(int(player_id))
        if user is not None and not user.is_admin:
          await self.poker_room_denied_repository.add_without_commit(
            user_row_id=int(user.row_id),
          )
      await session.commit()
      return removed
    except Exception:
      await session.rollback()
      raise

  async def is_denied_for_active_poker(self, *, user_row_id: int) -> bool:
    if self.poker_room_denied_repository is None:
      return False
    return await self.poker_room_denied_repository.is_denied(
      user_row_id=user_row_id,
    )

  async def list_denied_for_active_poker(self):
    if self.poker_room_denied_repository is None:
      return []
    return await self.poker_room_denied_repository.list_all()

  async def remove_denied_for_active_poker(self, *, user_row_id: int) -> bool:
    if self.poker_room_denied_repository is None:
      return False
    return await self.poker_room_denied_repository.remove(
      user_row_id=user_row_id,
    )

  async def list_players_for_chips_entry(self):
    poker = await self.poker_repository.get_latest_ready_for_chips()
    if poker is None:
      return []
    return await self.poker_data_repository.list_players(date=poker.date)
