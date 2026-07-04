from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Date, Integer, String, UniqueConstraint
from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PokerData(Base):
  __tablename__ = "poker_data"

  row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
  player_name: Mapped[str] = mapped_column(String(255), nullable=False)
  player_id: Mapped[int] = mapped_column(Integer, nullable=False)

  is_prev_winner: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  buyins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  big_buyin_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  super_buyin_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
  chips: Mapped[int | None] = mapped_column(Integer, default=None, nullable=True)
  money_kopecks: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
  created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
  updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

  __table_args__ = (
    UniqueConstraint("date", "player_id", name="uq_poker_data_date_player"),
  )
