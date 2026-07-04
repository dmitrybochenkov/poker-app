from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PollVote(Base):
  __tablename__ = "poll_votes"
  __table_args__ = (
    UniqueConstraint("poll_date", "player_row_id", name="uq_poll_votes_date_player"),
  )

  row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  poll_date: Mapped[date] = mapped_column(Date, nullable=False)
  player_row_id: Mapped[int] = mapped_column(Integer, nullable=False)
  created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
  updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
