from sqlalchemy import BigInteger, Date, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PokerRoomDenied(Base):
  __tablename__ = "poker_room_denied"

  row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
  player_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
  platform: Mapped[str] = mapped_column(String(8), nullable=False)

  __table_args__ = (
    UniqueConstraint("date", "player_id", name="uq_poker_room_denied_date_player"),
  )

