from sqlalchemy import insert, select, update
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

  async def create_if_none_started(self, *, params_id: int) -> Poker | None:
    active_exists = select(Poker.row_id).where(Poker.is_going.is_(True)).exists()
    statement = (
      insert(Poker)
      .from_select(
        [Poker.params_id],
        select(params_id).where(~active_exists),
      )
      .returning(Poker.row_id)
    )
    row_id = await self.session.scalar(statement)
    if row_id is None:
      return None
    await self.session.flush()
    return await self.session.get(Poker, int(row_id))

  async def get_started(self) -> tuple[Poker, PokerParam] | None:
    result = await self.session.execute(
      select(Poker, PokerParam)
      .join(PokerParam, Poker.params_id == PokerParam.row_id)
      .where(Poker.is_going.is_(True))
      .order_by(Poker.row_id.desc())
    )
    return result.first()

  async def finish(self, poker: Poker) -> Poker:
    # Move poker to chips-entry stage and close room/betting access.
    poker.is_going = False
    poker.is_bettable = False
    poker.is_ready_for_chips_entering = True
    await self.session.commit()
    await self.session.refresh(poker)
    return poker

  async def mark_finished_for_chips(self, *, poker_id: int) -> bool:
    result = await self.session.execute(
      update(Poker)
      .where(Poker.row_id == poker_id)
      .where(Poker.is_going.is_(True))
      .values(
        is_going=False,
        is_bettable=False,
        is_ready_for_chips_entering=True,
      )
    )
    await self.session.flush()
    return result.rowcount == 1

  async def get_latest_ready_for_chips(self) -> Poker | None:
    result = await self.session.execute(
      select(Poker)
      .where(Poker.is_ready_for_chips_entering.is_(True))
      .order_by(Poker.row_id.desc())
    )
    return result.scalar_one_or_none()

  async def get_latest_ready_for_chips_with_params(self) -> tuple[Poker, PokerParam] | None:
    result = await self.session.execute(
      select(Poker, PokerParam)
      .join(PokerParam, Poker.params_id == PokerParam.row_id)
      .where(Poker.is_ready_for_chips_entering.is_(True))
      .order_by(Poker.row_id.desc())
    )
    return result.first()

  async def set_cashier(self, poker: Poker, *, cashier_id: int) -> Poker:
    poker.cashier_id = cashier_id
    await self.session.commit()
    await self.session.refresh(poker)
    return poker

  async def finish_chips_entering(self, poker: Poker, *, winners: str, loosers: str) -> Poker:
    poker.is_going = False
    poker.is_ready_for_chips_entering = False
    poker.winners = winners
    poker.loosers = loosers
    await self.session.commit()
    await self.session.refresh(poker)
    return poker

  async def finish_chips_entering_without_commit(
    self, *, poker_id: int, winners: str, loosers: str
  ) -> bool:
    result = await self.session.execute(
      update(Poker)
      .where(Poker.row_id == poker_id)
      .where(Poker.is_ready_for_chips_entering.is_(True))
      .values(
        is_going=False,
        is_ready_for_chips_entering=False,
        winners=winners,
        loosers=loosers,
      )
    )
    await self.session.flush()
    return result.rowcount == 1

  async def start_betting(self, poker: Poker) -> Poker:
    poker.is_bettable = True
    await self.session.commit()
    await self.session.refresh(poker)
    return poker

  async def mark_betting_started(self, *, poker_id: int) -> bool:
    result = await self.session.execute(
      update(Poker)
      .where(Poker.row_id == poker_id)
      .where(Poker.is_going.is_(True))
      .where(Poker.is_ready_for_chips_entering.is_(False))
      .where(Poker.is_bettable.is_(False))
      .values(is_bettable=True)
    )
    await self.session.flush()
    return result.rowcount == 1

  async def list_all(self) -> list[Poker]:
    result = await self.session.execute(
      select(Poker).order_by(Poker.row_id.asc())
    )
    return list(result.scalars().all())
