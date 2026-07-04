from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SyncState(Base):
  __tablename__ = "sync_states"

  table_name: Mapped[str] = mapped_column(String(64), primary_key=True)
  last_synced_row_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
  last_synced_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
  created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
  updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
