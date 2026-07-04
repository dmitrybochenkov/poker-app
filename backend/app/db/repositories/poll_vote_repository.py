from datetime import date, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.poll_vote import PollVote


class PollVoteRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def get_user_month_votes(self, *, player_row_id: int, month_start: date, month_end: date) -> list[date]:
    result = await self.session.execute(
      select(PollVote.poll_date)
      .where(PollVote.player_row_id == int(player_row_id))
      .where(PollVote.poll_date >= month_start)
      .where(PollVote.poll_date <= month_end)
      .order_by(PollVote.poll_date.asc())
    )
    return list(result.scalars().all())

  async def replace_user_month_votes(
    self,
    *,
    player_row_id: int,
    month_start: date,
    month_end: date,
    selected_dates: list[date],
  ) -> None:
    await self.session.execute(
      delete(PollVote)
      .where(PollVote.player_row_id == int(player_row_id))
      .where(PollVote.poll_date >= month_start)
      .where(PollVote.poll_date <= month_end)
    )
    now = datetime.utcnow()
    for item in sorted(set(selected_dates)):
      vote = PollVote(
        poll_date=item,
        player_row_id=int(player_row_id),
        created_at=now,
        updated_at=now,
      )
      self.session.add(vote)
    await self.session.flush()

  async def get_month_counts(self, *, month_start: date, month_end: date) -> list[tuple[date, int]]:
    result = await self.session.execute(
      select(PollVote.poll_date, func.count(PollVote.row_id))
      .where(PollVote.poll_date >= month_start)
      .where(PollVote.poll_date <= month_end)
      .where(PollVote.player_row_id > 0)
      .group_by(PollVote.poll_date)
      .order_by(PollVote.poll_date.asc())
    )
    rows = result.all()
    return [(item[0], int(item[1])) for item in rows]

  async def get_month_votes(self, *, month_start: date, month_end: date) -> list[tuple[date, int]]:
    result = await self.session.execute(
      select(PollVote.poll_date, PollVote.player_row_id)
      .where(PollVote.poll_date >= month_start)
      .where(PollVote.poll_date <= month_end)
      .where(PollVote.player_row_id > 0)
      .order_by(PollVote.poll_date.asc(), PollVote.player_row_id.asc())
    )
    rows = result.all()
    return [(item[0], int(item[1])) for item in rows]

  async def get_month_extra_dates(self, *, month_start: date, month_end: date) -> list[date]:
    result = await self.session.execute(
      select(PollVote.poll_date)
      .where(PollVote.player_row_id == 0)
      .where(PollVote.poll_date >= month_start)
      .where(PollVote.poll_date <= month_end)
      .order_by(PollVote.poll_date.asc())
    )
    return list(result.scalars().all())

  async def add_month_extra_date(self, *, poll_date: date) -> None:
    existing = await self.session.execute(
      select(PollVote.row_id)
      .where(PollVote.player_row_id == 0)
      .where(PollVote.poll_date == poll_date)
      .limit(1)
    )
    if existing.scalar_one_or_none() is None:
      now = datetime.utcnow()
      self.session.add(
        PollVote(
          poll_date=poll_date,
          player_row_id=0,
          created_at=now,
          updated_at=now,
        )
      )
    await self.session.flush()
