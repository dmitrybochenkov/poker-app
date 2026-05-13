from datetime import datetime

from sqlalchemy import BigInteger, Date, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BuyinData(Base):
  __tablename__ = "buyins_data"

  row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  poker_date: Mapped[Date] = mapped_column("date", Date, nullable=False, index=True)
  player_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
  player_name: Mapped[str] = mapped_column(String(255), nullable=False)
  buyins_count: Mapped[int] = mapped_column("buyin", Integer, nullable=False)
  created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
