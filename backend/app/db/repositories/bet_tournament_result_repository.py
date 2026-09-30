from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.bet_tournament_result import BetTournamentResult


class BetTournamentResultRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def add_many(self, *, tournament_id: int, payouts: tuple) -> list[BetTournamentResult]:
    rows = [
      BetTournamentResult(
        tournament_id=int(tournament_id),
        user_id=int(item.user_id),
        position=int(item.position),
        score=int(item.score),
        payout_kopecks=int(item.amount_kopecks),
        name_snapshot=str(item.player_name),
      )
      for item in payouts
    ]
    self.session.add_all(rows)
    await self.session.flush()
    return rows

  async def list_for_tournament(self, *, tournament_id: int) -> list[BetTournamentResult]:
    result = await self.session.execute(
      select(BetTournamentResult)
      .where(BetTournamentResult.tournament_id == tournament_id)
      .order_by(BetTournamentResult.position, BetTournamentResult.user_id)
    )
    return list(result.scalars().all())

  async def list_all(self) -> list[BetTournamentResult]:
    result = await self.session.execute(
      select(BetTournamentResult).order_by(
        BetTournamentResult.tournament_id,
        BetTournamentResult.position,
        BetTournamentResult.user_id,
      )
    )
    return list(result.scalars().all())
