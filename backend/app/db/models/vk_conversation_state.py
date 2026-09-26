from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VkConversationState(Base):
  __tablename__ = "vk_conversation_states"

  vk_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
  user_row_id: Mapped[int | None] = mapped_column(
    ForeignKey("users.row_id", ondelete="CASCADE"), nullable=True, index=True
  )
  state_type: Mapped[str] = mapped_column(String(64), nullable=False)
  payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
  updated_at: Mapped[datetime] = mapped_column(
    DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
  )
