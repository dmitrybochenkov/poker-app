from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.poker_param import PokerParam


class PokerParamRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def list_all(self) -> list[PokerParam]:
    result = await self.session.execute(select(PokerParam).order_by(PokerParam.row_id))
    return list(result.scalars().all())

  async def get_by_row_id(self, row_id: int) -> PokerParam | None:
    result = await self.session.execute(select(PokerParam).where(PokerParam.row_id == row_id))
    return result.scalar_one_or_none()
