from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.poker_param import PokerParam


class PokerParamRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def create(
    self,
    *,
    buyin_size_chips: int,
    buyin_size_rub: int,
    bb_size_chips: int,
    max_buyins: int,
    big_buyin: int | None = None,
    big_buyin_pic: str | None = None,
    super_buyin: int | None = None,
    super_buyin_pic: str | None = None,
  ) -> PokerParam:
    item = PokerParam(
      buyin_size_chips=buyin_size_chips,
      buyin_size_rub=buyin_size_rub,
      bb_size_chips=bb_size_chips,
      max_buyins=max_buyins,
      big_buyin=big_buyin,
      big_buyin_pic=big_buyin_pic,
      super_buyin=super_buyin,
      super_buyin_pic=super_buyin_pic,
    )
    self.session.add(item)
    await self.session.commit()
    await self.session.refresh(item)
    return item

  async def list_all(self) -> list[PokerParam]:
    result = await self.session.execute(select(PokerParam).order_by(PokerParam.row_id))
    return list(result.scalars().all())

  async def get_by_row_id(self, row_id: int) -> PokerParam | None:
    result = await self.session.execute(select(PokerParam).where(PokerParam.row_id == row_id))
    return result.scalar_one_or_none()
