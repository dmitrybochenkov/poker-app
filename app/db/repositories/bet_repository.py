from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.bet import Bet


class BetRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def create(
    self,
    *,
    poker_id: int,
    better_id: int,
    better_name: str,
    tournament_type: str,
    amount_kopecks: int,
    params_id: int | None = None,
    winner_name: str | None = None,
    loser_name: str | None = None,
  ) -> Bet:
    bet = Bet(
      poker_id=poker_id,
      better_id=better_id,
      better_name=better_name,
      tournament_type=tournament_type,
      params_id=params_id,
      amount_kopecks=amount_kopecks,
      winner_name=winner_name,
      loser_name=loser_name,
    )
    self.session.add(bet)
    await self.session.flush()
    return bet

  async def get_by_poker_user_and_tournament(
    self,
    *,
    poker_id: int,
    better_id: int,
    tournament_type: str,
  ) -> Bet | None:
    result = await self.session.execute(
      select(Bet).where(
        Bet.poker_id == poker_id,
        Bet.better_id == better_id,
        Bet.tournament_type == tournament_type,
      )
    )
    return result.scalars().first()

  async def list_for_poker(self, *, poker_id: int) -> list[Bet]:
    result = await self.session.execute(
      select(Bet).where(Bet.poker_id == poker_id).order_by(desc(Bet.created_at), desc(Bet.row_id))
    )
    return list(result.scalars().all())

  async def list_for_user_in_poker(self, *, poker_id: int, better_id: int) -> list[Bet]:
    result = await self.session.execute(
      select(Bet)
      .where(Bet.poker_id == poker_id, Bet.better_id == better_id)
      .order_by(desc(Bet.created_at), desc(Bet.row_id))
    )
    return list(result.scalars().all())

  async def update_score(self, *, bet: Bet, score: int) -> Bet:
    bet.score = int(score)
    await self.session.flush()
    return bet
