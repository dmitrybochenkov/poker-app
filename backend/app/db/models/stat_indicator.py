from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StatIndicator(Base):
  __tablename__ = "stat_indicators"

  row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  type: Mapped[str] = mapped_column(String(16), nullable=False)
  description: Mapped[str] = mapped_column(String(255), nullable=False)
  description_full: Mapped[str] = mapped_column(String(1024), nullable=False)
  pic: Mapped[str] = mapped_column(String(32), nullable=False)
  for_current_tournaments: Mapped[str] = mapped_column(String(16), nullable=False)
  is_for_achievement: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
  created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
  updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
