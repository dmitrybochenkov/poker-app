from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.bet_param import BetParam


class BetParamRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def get_by_id(self, *, row_id: int) -> BetParam | None:
    result = await self.session.execute(select(BetParam).where(BetParam.row_id == row_id))
    return result.scalars().first()
