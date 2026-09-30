from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BetTournamentResult(Base):
  __tablename__ = "bet_tournament_results"
  __table_args__ = (
    UniqueConstraint("tournament_id", "user_id", name="uq_bet_tournament_results_tournament_user"),
    CheckConstraint("position BETWEEN 1 AND 3", name="ck_bet_tournament_results_position"),
    CheckConstraint("payout_kopecks >= 0", name="ck_bet_tournament_results_payout_nonnegative"),
    Index("ix_bet_tournament_results_user_id", "user_id"),
    Index("ix_bet_tournament_results_tournament_position", "tournament_id", "position"),
  )

  row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  tournament_id: Mapped[int] = mapped_column(
    ForeignKey("bet_tournaments.row_id", ondelete="RESTRICT"), nullable=False
  )
  user_id: Mapped[int] = mapped_column(
    ForeignKey("users.row_id", ondelete="RESTRICT"), nullable=False
  )
  position: Mapped[int] = mapped_column(Integer, nullable=False)
  score: Mapped[int] = mapped_column(Integer, nullable=False)
  payout_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
  name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
