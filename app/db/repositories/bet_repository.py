from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.bet import Bet


class BetRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def create(
    self,
    *,
    poker_id: int | None = None,
    date=None,
    better_id: int,
    better_name: str,
    tournament_type: str | None = None,
    amount_kopecks: int,
    params_id: int | None = None,
    winner_name: str | None = None,
    loser_name: str | None = None,
    is_paid: bool = False,
  ) -> Bet:
    bet = Bet(
      params_id=params_id,
      date=date,
      better_id=better_id,
      better_name=better_name,
      amount_kopecks=amount_kopecks,
      winner_name=winner_name,
      loser_name=loser_name,
      is_paid=is_paid,
    )
    self.session.add(bet)
    await self.session.flush()
    return bet

  async def get_by_poker_user_and_tournament(
    self,
    *,
    poker_id: int | None = None,
    date=None,
    better_id: int,
    tournament_type: str | None = None,
  ) -> Bet | None:
    if date is None:
      return None
    result = await self.session.execute(
      select(Bet).where(
        Bet.date == date,
        Bet.better_id == better_id,
      )
    )
    return result.scalars().first()

  async def list_for_poker(self, *, poker_id: int | None = None, date=None) -> list[Bet]:
    if date is None:
      return []
    result = await self.session.execute(
      select(Bet).where(Bet.date == date).order_by(Bet.row_id.desc())
    )
    return list(result.scalars().all())

  async def list_for_user_in_poker(self, *, poker_id: int | None = None, date=None, better_id: int) -> list[Bet]:
    if date is None:
      return []
    result = await self.session.execute(
      select(Bet)
      .where(Bet.date == date, Bet.better_id == better_id)
      .order_by(Bet.row_id.desc())
    )
    return list(result.scalars().all())

  async def update_score(self, *, bet: Bet, score: int) -> Bet:
    bet.score = int(score)
    await self.session.flush()
    return bet

  async def list_for_latest_poker(self) -> list[Bet]:
    latest_date_result = await self.session.execute(
      select(Bet.date).where(Bet.date.is_not(None)).order_by(Bet.date.desc())
    )
    latest_date = latest_date_result.scalars().first()
    if latest_date is None:
      return []
    return await self.list_for_poker(date=latest_date)

  async def list_all(self) -> list[Bet]:
    result = await self.session.execute(
      select(Bet).order_by(Bet.row_id.desc())
    )
    return list(result.scalars().all())
