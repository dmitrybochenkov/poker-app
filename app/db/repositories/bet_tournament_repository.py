from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.bet_tournament import BetTournament


class BetTournamentRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def get_by_type(self, *, tournament_type: str) -> BetTournament | None:
    result = await self.session.execute(
      select(BetTournament).where(BetTournament.tournament_type == tournament_type)
    )
    return result.scalars().first()

  async def get_or_create_by_type(self, *, tournament_type: str) -> BetTournament:
    tournament = await self.get_by_type(tournament_type=tournament_type)
    if tournament is not None:
      return tournament
    tournament = BetTournament(
      params_id=1,
      tournament_type=tournament_type,
      current_bank_kopecks=0,
    )
    self.session.add(tournament)
    await self.session.flush()
    return tournament

  async def add_to_bank(self, *, tournament_type: str, amount_kopecks: int) -> BetTournament:
    tournament = await self.get_or_create_by_type(tournament_type=tournament_type)
    tournament.current_bank_kopecks += amount_kopecks
    await self.session.flush()
    return tournament

  async def list_active(self) -> list[BetTournament]:
    result = await self.session.execute(select(BetTournament).order_by(BetTournament.row_id.asc()))
    return list(result.scalars().all())
