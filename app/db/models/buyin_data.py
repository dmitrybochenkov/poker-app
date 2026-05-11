from sqlalchemy import BigInteger, Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BuyinData(Base):
  __tablename__ = "buyin_data"

  row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  poker_date: Mapped[Date] = mapped_column("date", Date, nullable=False, index=True)
  player_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
  player_name: Mapped[str] = mapped_column(String(255), nullable=False)
  buyins_count: Mapped[int] = mapped_column("buyin", Integer, nullable=False)
