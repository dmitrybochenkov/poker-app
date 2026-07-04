from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.achievement import Achievement


class AchievementRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def list_by_type(self, *, achievement_type: str) -> list[Achievement]:
    result = await self.session.execute(
      select(Achievement)
      .where(Achievement.type == achievement_type)
      .order_by(Achievement.row_id.asc())
    )
    return list(result.scalars().all())
