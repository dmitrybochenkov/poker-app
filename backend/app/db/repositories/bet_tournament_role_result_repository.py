from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.bet_tournament_role_result import BetTournamentRoleResult


class BetTournamentRoleResultRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def add_many(self, *, tournament_id: int, snapshots: tuple) -> list[BetTournamentRoleResult]:
    rows = [
      BetTournamentRoleResult(
        tournament_id=int(tournament_id),
        bettor_user_id=int(item.bettor_user_id),
        target_user_id=int(item.target_user_id),
        role=str(item.role),
        score_units=int(item.score_units),
      )
      for item in snapshots
    ]
    self.session.add_all(rows)
    await self.session.flush()
    return rows

  async def list_all(self) -> list[BetTournamentRoleResult]:
    result = await self.session.execute(
      select(BetTournamentRoleResult).order_by(
        BetTournamentRoleResult.tournament_id,
        BetTournamentRoleResult.bettor_user_id,
        BetTournamentRoleResult.target_user_id,
        BetTournamentRoleResult.role,
      )
    )
    return list(result.scalars().all())
