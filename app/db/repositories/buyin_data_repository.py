from datetime import datetime

from app.db.models.buyin_data import BuyinData
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


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
  ) -> BuyinData:
    item = BuyinData(
      poker_date=poker_date,
      player_id=player_id,
      player_name=player_name,
      buyins_count=buyins_count,
      created_at=datetime.utcnow(),
    )
    self.session.add(item)
    await self.session.flush()
    return item

  async def list_for_player(self, *, player_id: int, limit: int = 100) -> list[BuyinData]:
    result = await self.session.execute(
      select(BuyinData)
      .where(BuyinData.player_id == player_id)
      .order_by(BuyinData.row_id.desc())
      .limit(limit)
    )
    return list(result.scalars().all())
