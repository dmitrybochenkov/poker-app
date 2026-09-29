from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Bet(Base):
  __tablename__ = "bets"
  __table_args__ = (
    Index("ix_bets_date", "date"),
    UniqueConstraint("date", "better_id", name="uq_bets_date_better_id"),
    UniqueConstraint("poker_id", "better_id", name="uq_bets_poker_better_id"),
  )

  row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  poker_id: Mapped[int] = mapped_column(
    ForeignKey("pokers.row_id", ondelete="RESTRICT"), nullable=False
  )
  params_id: Mapped[int | None] = mapped_column(
    ForeignKey("bet_params.row_id", ondelete="RESTRICT"), nullable=True
  )
  date: Mapped[Date | None] = mapped_column(Date, nullable=True)
  better_name: Mapped[str] = mapped_column(String(255), nullable=False)
  better_id: Mapped[int] = mapped_column(
    ForeignKey("users.row_id", ondelete="RESTRICT"), nullable=False
  )
  amount_kopecks: Mapped[int] = mapped_column("size_kopecks", Integer, nullable=False)
  winner_id: Mapped[int] = mapped_column(
    ForeignKey("users.row_id", ondelete="RESTRICT"), nullable=False
  )
  winner_name: Mapped[str | None] = mapped_column("winner", String(255), nullable=True)
  loser_id: Mapped[int] = mapped_column(
    ForeignKey("users.row_id", ondelete="RESTRICT"), nullable=False
  )
  loser_name: Mapped[str | None] = mapped_column("looser", String(255), nullable=True)
  score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
  is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
  created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
  updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

  @property
  def tournament_type(self) -> str:
    return "regular"
