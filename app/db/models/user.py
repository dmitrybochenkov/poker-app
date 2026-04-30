from sqlalchemy import BigInteger, Boolean, CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
  __tablename__ = "users"

  row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

  telegram_id: Mapped[int | None] = mapped_column(
    BigInteger,
    nullable=True,
    unique=True,
    index=True,
  )
  vk_id: Mapped[int | None] = mapped_column(
    BigInteger,
    nullable=True,
    unique=True,
    index=True,
  )

  name: Mapped[str] = mapped_column(String(255), nullable=False)
  is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
  is_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

  tel_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
  bank_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

  __table_args__ = (
    CheckConstraint(
      "(telegram_id IS NOT NULL) OR (vk_id IS NOT NULL)",
      name="check_at_least_one_id",
    ),
  )
