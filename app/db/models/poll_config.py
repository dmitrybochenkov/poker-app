from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PollConfig(Base):
  __tablename__ = "poll_configs"

  row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  poll_month: Mapped[date | None] = mapped_column(Date, nullable=True)
  is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
  updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
