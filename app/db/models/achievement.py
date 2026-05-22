from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Achievement(Base):
  __tablename__ = "achievements"

  row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  type: Mapped[str] = mapped_column(String(16), nullable=False)
  sort: Mapped[str] = mapped_column(String(16), nullable=False)
  description: Mapped[str] = mapped_column(String(255), nullable=False)
  pic: Mapped[str] = mapped_column(String(32), nullable=False)
  stat_id: Mapped[int] = mapped_column(Integer, nullable=False)
  is_permanent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
  created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
  updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
