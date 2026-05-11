from sqlalchemy import Boolean, Date, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Poker(Base):
  __tablename__ = "pokers"

  row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  params_id: Mapped[int] = mapped_column(
    Integer,
    ForeignKey("poker_params.row_id", ondelete="RESTRICT"),
    nullable=False,
  )
  date: Mapped[Date] = mapped_column(Date, server_default=func.current_date(), nullable=False)
  cashier_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

  is_going: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
  is_bettable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  is_ready_for_chips_entering: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
