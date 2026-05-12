from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.poker import Poker
from app.db.models.poker_param import PokerParam


class PokerRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def create(self, *, params_id: int) -> Poker:
    poker = Poker(params_id=params_id)
    self.session.add(poker)
    await self.session.commit()
    await self.session.refresh(poker)
    return poker

  async def get_started(self) -> tuple[Poker, PokerParam] | None:
    result = await self.session.execute(
      select(Poker, PokerParam)
      .join(PokerParam, Poker.params_id == PokerParam.row_id)
      .where(Poker.is_going.is_(True))
      .order_by(Poker.row_id.desc())
    )
    return result.first()

  async def finish(self, poker: Poker) -> Poker:
    poker.is_going = False
    poker.is_bettable = False
    poker.is_ready_for_chips_entering = True
    await self.session.commit()
    await self.session.refresh(poker)
    return poker

  async def get_latest_ready_for_chips(self) -> Poker | None:
    result = await self.session.execute(
      select(Poker)
      .where(Poker.is_going.is_(False))
      .where(Poker.is_ready_for_chips_entering.is_(True))
      .order_by(Poker.row_id.desc())
    )
    return result.scalar_one_or_none()

  async def set_cashier(self, poker: Poker, *, cashier_id: int) -> Poker:
    poker.cashier_id = cashier_id
    await self.session.commit()
    await self.session.refresh(poker)
    return poker

  async def start_betting(self, poker: Poker) -> Poker:
    poker.is_bettable = True
    await self.session.commit()
    await self.session.refresh(poker)
    return poker

  async def list_all(self) -> list[Poker]:
    result = await self.session.execute(
      select(Poker).order_by(Poker.row_id.asc())
    )
    return list(result.scalars().all())
