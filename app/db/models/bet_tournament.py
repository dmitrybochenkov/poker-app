from datetime import date

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BetTournament(Base):
  __tablename__ = "bet_tournaments"

  row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  params_id: Mapped[int] = mapped_column(Integer, nullable=False)
  tournament_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
  current_bank_kopecks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

  @property
  def start_date(self) -> date | None:
    return None

  @property
  def end_date(self) -> date | None:
    return None

  @property
  def first_place_name(self) -> str | None:
    return None

  @property
  def second_place_name(self) -> str | None:
    return None

  @property
  def third_place_name(self) -> str | None:
    return None

  @property
  def is_paid(self) -> bool:
    return False
