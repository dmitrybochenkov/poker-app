from datetime import date

from sqlalchemy import Boolean, Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BetTournament(Base):
  __tablename__ = "bet_tournaments"

  row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  params_id: Mapped[int] = mapped_column(Integer, nullable=False)
  tournament_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
  start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
  end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
  current_bank_kopecks: Mapped[int] = mapped_column("current_bank_size_kopecks", Integer, nullable=False, default=0)
  first_place_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
  second_place_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
  third_place_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
  is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
