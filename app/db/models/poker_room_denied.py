from sqlalchemy import BigInteger, Date, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PokerRoomDenied(Base):
  __tablename__ = "poker_room_denied"

  row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
  user_row_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

  __table_args__ = (
    UniqueConstraint("date", "user_row_id", name="uq_poker_room_denied_date_user_row"),
  )
