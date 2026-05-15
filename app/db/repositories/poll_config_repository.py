from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.poll_config import PollConfig


class PollConfigRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def get_latest(self) -> PollConfig | None:
    result = await self.session.execute(
      select(PollConfig).order_by(PollConfig.row_id.desc())
    )
    return result.scalars().first()

  async def get_active_month(self) -> date | None:
    latest = await self.get_latest()
    if latest is None or not bool(latest.is_active) or latest.poll_month is None:
      return None
    return latest.poll_month

  async def set_active_month(self, *, month: date) -> PollConfig:
    latest = await self.get_latest()
    if latest is None:
      latest = PollConfig(poll_month=month, is_active=True, updated_at=datetime.utcnow())
      self.session.add(latest)
    else:
      latest.poll_month = month
      latest.is_active = True
      latest.updated_at = datetime.utcnow()
    await self.session.flush()
    return latest
