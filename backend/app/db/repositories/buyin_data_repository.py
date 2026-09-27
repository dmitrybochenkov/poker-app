from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.buyin_data import BuyinData


class BuyinDataRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def add_buyin(
    self,
    *,
    poker_date,
    player_id: int,
    player_name: str,
    buyins_count: int,
    operation_id: str | None = None,
  ) -> BuyinData:
    item = BuyinData(
      poker_date=poker_date,
      player_id=player_id,
      player_name=player_name,
      buyins_count=buyins_count,
      operation_id=operation_id,
      created_at=datetime.utcnow(),
    )
    self.session.add(item)
    await self.session.flush()
    return item

  async def get_by_operation_id(self, *, operation_id: str) -> BuyinData | None:
    result = await self.session.execute(
      select(BuyinData).where(BuyinData.operation_id == operation_id)
    )
    return result.scalar_one_or_none()

  async def list_for_player(self, *, player_id: int, limit: int = 100) -> list[BuyinData]:
    result = await self.session.execute(
      select(BuyinData)
      .where(BuyinData.player_id == player_id)
      .order_by(BuyinData.row_id.desc())
      .limit(limit)
    )
    return list(result.scalars().all())

  async def list_for_date(self, *, poker_date) -> list[BuyinData]:
    result = await self.session.execute(
      select(BuyinData)
      .where(BuyinData.poker_date == poker_date)
      .order_by(BuyinData.created_at.asc(), BuyinData.row_id.asc())
    )
    return list(result.scalars().all())

  async def delete_for_player_on_date_without_commit(
    self, *, poker_date, player_id: int
  ) -> int:
    result = await self.session.execute(
      delete(BuyinData)
      .where(BuyinData.poker_date == poker_date)
      .where(BuyinData.player_id == player_id)
    )
    await self.session.flush()
    return int(result.rowcount or 0)
