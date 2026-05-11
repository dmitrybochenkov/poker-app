from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BetParam(Base):
  __tablename__ = "bet_params"

  row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  small_pic: Mapped[str] = mapped_column(String(16), nullable=False, default="🐤")
  small_size_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
  small_score: Mapped[int] = mapped_column(Integer, nullable=False)
  small_score_combo: Mapped[int] = mapped_column(Integer, nullable=False)
  big_pic: Mapped[str] = mapped_column(String(16), nullable=False, default="🐔")
  big_size_kopecks: Mapped[int] = mapped_column(Integer, nullable=False)
  big_score: Mapped[int] = mapped_column(Integer, nullable=False)
  big_score_combo: Mapped[int] = mapped_column(Integer, nullable=False)
  percent_to_regular_bank_if_it_is_going: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
