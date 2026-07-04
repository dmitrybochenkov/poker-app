from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.poker_data import PokerData


class PokerDataRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def add_player(
    self,
    *,
    date,
    player_id: int,
    player_name: str,
    is_prev_winner: bool = False,
  ) -> PokerData:
    item = PokerData(
      date=date,
      player_id=player_id,
      player_name=player_name,
      is_prev_winner=is_prev_winner,
    )
    self.session.add(item)
    await self.session.commit()
    await self.session.refresh(item)
    return item

  async def get_player(self, *, date, player_id: int) -> PokerData | None:
    result = await self.session.execute(
      select(PokerData)
      .where(PokerData.date == date)
      .where(PokerData.player_id == player_id)
    )
    return result.scalar_one_or_none()

  async def list_players(self, *, date) -> list[PokerData]:
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

  async def add_buyins(
    self,
    *,
    date,
    player_id: int,
    buyins_count: int,
    big_buyin_count: int = 0,
    super_buyin_count: int = 0,
  ) -> PokerData | None:
    item = await self.get_player(date=date, player_id=player_id)
    if item is None:
      return None
    item.buyins = int(item.buyins) + int(buyins_count)
    item.big_buyin_count = int(item.big_buyin_count) + int(big_buyin_count)
    item.super_buyin_count = int(item.super_buyin_count) + int(super_buyin_count)
    await self.session.commit()
    await self.session.refresh(item)
    return item

  async def remove_player(self, *, date, player_id: int) -> bool:
    item = await self.get_player(date=date, player_id=player_id)
    if item is None:
      return False
    await self.session.delete(item)
    await self.session.commit()
    return True

  async def set_cashout(self, *, date, player_id: int, money_kopecks: int) -> PokerData | None:
    item = await self.get_player(date=date, player_id=player_id)
    if item is None:
      return None
    item.money_kopecks = int(money_kopecks)
    await self.session.commit()
    await self.session.refresh(item)
    return item

  async def set_chips(self, *, date, player_id: int, chips: int) -> PokerData | None:
    item = await self.get_player(date=date, player_id=player_id)
    if item is None:
      return None
    item.chips = int(chips)
    await self.session.commit()
    await self.session.refresh(item)
    return item
