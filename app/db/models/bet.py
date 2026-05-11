from sqlalchemy import Boolean, Date, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Bet(Base):
  __tablename__ = "bets"
  __table_args__ = (
    UniqueConstraint("date", "better_name", name="uq_bets_date_better_name"),
  )

  row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  poker_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
  date: Mapped[Date | None] = mapped_column(Date, nullable=True, index=True)
  better_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
  better_name: Mapped[str] = mapped_column(String(255), nullable=False)
  tournament_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
  params_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
  amount_kopecks: Mapped[int] = mapped_column("size_kopecks", Integer, nullable=False)
  winner_name: Mapped[str | None] = mapped_column("winner", String(255), nullable=True)
  loser_name: Mapped[str | None] = mapped_column("looser", String(255), nullable=True)
  score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
  is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
  created_at: Mapped[DateTime | None] = mapped_column(DateTime, server_default=func.now(), nullable=True)
