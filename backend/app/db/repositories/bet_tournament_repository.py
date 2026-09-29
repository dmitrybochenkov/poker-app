from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.bet_tournament import BetTournament


class BetTournamentRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def get_by_type(self, *, tournament_type: str) -> BetTournament | None:
    result = await self.session.execute(
      select(BetTournament)
      .where(BetTournament.tournament_type == tournament_type)
      .order_by(BetTournament.row_id.desc())
    )
    return result.scalars().first()

  async def list_active(self) -> list[BetTournament]:
    result = await self.session.execute(select(BetTournament).order_by(BetTournament.row_id.asc()))
    return list(result.scalars().all())

  async def get_by_id(self, *, row_id: int) -> BetTournament | None:
    return await self.session.get(BetTournament, row_id)

  async def list_eligible_for_finalization(self, *, today) -> list[BetTournament]:
    result = await self.session.execute(
      select(BetTournament).where(
        BetTournament.end_date < today, BetTournament.is_paid.is_(False)
      ).order_by(BetTournament.end_date, BetTournament.row_id)
    )
    return list(result.scalars().all())

  async def finalize_if_unpaid(self, *, tournament_id: int, first_place_name: str, second_place_name: str, third_place_name: str) -> bool:
    result = await self.session.execute(
      update(BetTournament).where(
        BetTournament.row_id == tournament_id, BetTournament.is_paid.is_(False)
      ).values(is_paid=True, first_place_name=first_place_name,
               second_place_name=second_place_name, third_place_name=third_place_name)
    )
    return int(result.rowcount or 0) == 1
