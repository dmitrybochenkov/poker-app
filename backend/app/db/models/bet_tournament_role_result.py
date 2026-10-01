from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BetTournamentRoleResult(Base):
  __tablename__ = "bet_tournament_role_results"
  __table_args__ = (
    UniqueConstraint(
      "tournament_id", "bettor_user_id", "target_user_id", "role",
      name="uq_bet_tournament_role_results_identity",
    ),
    CheckConstraint("role IN ('winner', 'loser')", name="ck_bet_tournament_role_results_role"),
    CheckConstraint("score_units > 0", name="ck_bet_tournament_role_results_score_units"),
    Index("ix_bet_tournament_role_results_target_role", "target_user_id", "role"),
  )

  row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  tournament_id: Mapped[int] = mapped_column(
    ForeignKey("bet_tournaments.row_id", ondelete="RESTRICT"), nullable=False
  )
  bettor_user_id: Mapped[int] = mapped_column(
    ForeignKey("users.row_id", ondelete="RESTRICT"), nullable=False
  )
  target_user_id: Mapped[int] = mapped_column(
    ForeignKey("users.row_id", ondelete="RESTRICT"), nullable=False
  )
  role: Mapped[str] = mapped_column(String(6), nullable=False)
  score_units: Mapped[int] = mapped_column(Integer, nullable=False)
