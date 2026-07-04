from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.stat_indicator import StatIndicator


class StatIndicatorRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def list_by_type(self, *, indicator_type: str) -> list[StatIndicator]:
    result = await self.session.execute(
      select(StatIndicator).where(StatIndicator.type == indicator_type).order_by(StatIndicator.row_id.asc())
    )
    return list(result.scalars().all())
