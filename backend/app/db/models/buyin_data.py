from datetime import datetime

from sqlalchemy import BigInteger, Date, DateTime, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BuyinData(Base):
  __tablename__ = "buyins_data"
  __table_args__ = (
    UniqueConstraint("operation_id", name="uq_buyins_data_operation_id"),
    Index("ix_buyin_data_poker_date", "date"),
    Index("ix_buyin_data_player_id", "player_id"),
    Index("ix_buyin_data_created_at", "created_at"),
  )

  row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  poker_date: Mapped[Date] = mapped_column("date", Date, nullable=False)
  player_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
  player_name: Mapped[str] = mapped_column(String(255), nullable=False)
  buyins_count: Mapped[int] = mapped_column("buyin", Integer, nullable=False)
  operation_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
  created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
  updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
