from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.poker_room_denied import PokerRoomDenied


class PokerRoomDeniedRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def add(self, *, date, user_row_id: int) -> PokerRoomDenied:
    existing = await self.get(date=date, user_row_id=user_row_id)
    if existing is not None:
      return existing
    item = PokerRoomDenied(
      date=date,
      user_row_id=user_row_id,
    )
    self.session.add(item)
    await self.session.commit()
    await self.session.refresh(item)
    return item

  async def get(self, *, date, user_row_id: int) -> PokerRoomDenied | None:
    result = await self.session.execute(
      select(PokerRoomDenied)
      .where(PokerRoomDenied.date == date)
      .where(PokerRoomDenied.user_row_id == user_row_id)
    )
    return result.scalar_one_or_none()

  async def is_denied(self, *, date, user_row_id: int) -> bool:
    item = await self.get(date=date, user_row_id=user_row_id)
    return item is not None

  async def remove(self, *, date, user_row_id: int) -> bool:
    item = await self.get(date=date, user_row_id=user_row_id)
    if item is None:
      return False
    await self.session.delete(item)
    await self.session.commit()
    return True

  async def list_by_date(self, *, date) -> list[PokerRoomDenied]:
    result = await self.session.execute(
      select(PokerRoomDenied)
      .where(PokerRoomDenied.date == date)
      .order_by(PokerRoomDenied.row_id.asc())
    )
    return list(result.scalars().all())

  async def clear_all(self) -> None:
    result = await self.session.execute(select(PokerRoomDenied))
    items = list(result.scalars().all())
    for item in items:
      await self.session.delete(item)
    await self.session.commit()
