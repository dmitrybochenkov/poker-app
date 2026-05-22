from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BetTournamentParam(Base):
  __tablename__ = "bet_tournament_params"

  row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  tournament_type: Mapped[str] = mapped_column(String(16), nullable=False)
  bet_param_id: Mapped[int] = mapped_column(Integer, nullable=False)
  percent_to_first: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
  percent_to_second: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
  percent_to_third: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
  duration_months: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
  created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
  updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
