from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.poker import Poker
from app.db.models.poker_data import PokerData


class PokerDataRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def _validate_poker_date(self, *, poker_id: int, date) -> None:
    poker_date = await self.session.scalar(
      select(Poker.date).where(Poker.row_id == int(poker_id))
    )
    if poker_date is None:
      raise ValueError(f"Poker {poker_id} does not exist")
    if poker_date != date:
      raise ValueError(
        f"PokerData date {date} does not match Poker {poker_id} date {poker_date}"
      )

  async def add_player(
    self,
    *,
    poker_id: int,
    date,
    player_id: int,
    player_name: str,
    is_prev_winner: bool = False,
  ) -> PokerData:
    await self._validate_poker_date(poker_id=poker_id, date=date)
    item = PokerData(
      poker_id=poker_id,
      date=date,
      player_id=player_id,
      player_name=player_name,
      is_prev_winner=is_prev_winner,
    )
    self.session.add(item)
    await self.session.commit()
    await self.session.refresh(item)
    return item

  async def add_player_without_commit(
    self,
    *,
    poker_id: int,
    date,
    player_id: int,
    player_name: str,
    is_prev_winner: bool = False,
  ) -> PokerData:
    await self._validate_poker_date(poker_id=poker_id, date=date)
    item = PokerData(
      poker_id=poker_id,
      date=date,
      player_id=player_id,
      player_name=player_name,
      is_prev_winner=is_prev_winner,
    )
    self.session.add(item)
    await self.session.flush()
    return item

  async def get_player(self, *, poker_id: int, player_id: int) -> PokerData | None:
    statement = select(PokerData).where(
      PokerData.poker_id == poker_id,
      PokerData.player_id == player_id,
    )
    result = await self.session.execute(statement)
    return result.scalar_one_or_none()

  async def list_players(self, *, poker_id: int) -> list[PokerData]:
    statement = select(PokerData).where(PokerData.poker_id == poker_id)
    result = await self.session.execute(statement.order_by(PokerData.row_id))
    return list(result.scalars().all())

  async def list_players_for_date(self, *, date) -> list[PokerData]:
    result = await self.session.execute(
      select(PokerData)
      .where(PokerData.date == date)
      .order_by(PokerData.row_id)
    )
    return list(result.scalars().all())

  async def list_all(self) -> list[PokerData]:
    result = await self.session.execute(
      select(PokerData)
      .order_by(PokerData.date.asc(), PokerData.row_id.asc())
    )
    return list(result.scalars().all())

  async def add_buyins_without_commit(
    self,
    *,
    poker_id: int,
    player_id: int,
    buyins_count: int,
    big_buyin_count: int = 0,
    super_buyin_count: int = 0,
  ) -> PokerData | None:
    item = await self.get_player(poker_id=poker_id, player_id=player_id)
    if item is None:
      return None
    item.buyins = int(item.buyins) + int(buyins_count)
    item.big_buyin_count = int(item.big_buyin_count) + int(big_buyin_count)
    item.super_buyin_count = int(item.super_buyin_count) + int(super_buyin_count)
    await self.session.flush()
    return item

  async def remove_player_without_commit(
    self, *, poker_id: int, player_id: int
  ) -> bool:
    item = await self.get_player(poker_id=poker_id, player_id=player_id)
    if item is None:
      return False
    await self.session.delete(item)
    await self.session.flush()
    return True

  async def set_cashout_without_commit(
    self,
    *,
    player_id: int,
    money_kopecks: int,
    poker_id: int,
  ) -> PokerData | None:
    item = await self.get_player(poker_id=poker_id, player_id=player_id)
    if item is None:
      return None
    item.money_kopecks = int(money_kopecks)
    await self.session.flush()
    return item

  async def set_chips_and_cashout_without_commit(
    self,
    *,
    player_id: int,
    chips: int,
    money_kopecks: int,
    poker_id: int,
  ) -> PokerData | None:
    item = await self.get_player(poker_id=poker_id, player_id=player_id)
    if item is None:
      return None
    item.chips = int(chips)
    item.money_kopecks = int(money_kopecks)
    await self.session.flush()
    return item
