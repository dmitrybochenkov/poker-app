from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.bet_tournament_param import BetTournamentParam


class BetTournamentParamRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def get_by_tournament_type(self, *, tournament_type: str) -> BetTournamentParam | None:
    result = await self.session.execute(
      select(BetTournamentParam).where(BetTournamentParam.tournament_type == tournament_type)
    )
    return result.scalars().first()
