from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PokerRoomDenied(Base):
  __tablename__ = "poker_room_denied"

  user_row_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
