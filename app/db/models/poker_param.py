from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PokerParam(Base):
  __tablename__ = "poker_params"

  row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  buyin_size_chips: Mapped[int] = mapped_column(Integer, nullable=False)
  buyin_size_kopecks: Mapped[int] = mapped_column(BigInteger, nullable=False)
  bb_size_chips: Mapped[int] = mapped_column(Integer, nullable=False)
  max_buyins: Mapped[int] = mapped_column(Integer, nullable=False)

  big_buyin: Mapped[int | None] = mapped_column(Integer, nullable=True)
  big_buyin_pic: Mapped[str | None] = mapped_column(String(16), nullable=True)
  king_buyin: Mapped[int | None] = mapped_column(Integer, nullable=True)
  king_buyin_pic: Mapped[str | None] = mapped_column(String(16), nullable=True)
  super_buyin: Mapped[int | None] = mapped_column(Integer, nullable=True)
  super_buyin_pic: Mapped[str | None] = mapped_column(String(16), nullable=True)
