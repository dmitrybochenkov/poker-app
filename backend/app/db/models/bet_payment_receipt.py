from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BetPaymentReceipt(Base):
  __tablename__ = "bet_payment_receipts"
  __table_args__ = (
    UniqueConstraint("platform", "external_file_id", name="uq_receipt_platform_external_file_id"),
    UniqueConstraint("operation_id", name="uq_receipt_operation_id"),
  )

  row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
  user_row_id: Mapped[int] = mapped_column(Integer, nullable=False)
  platform: Mapped[str] = mapped_column(String(8), nullable=False)
  external_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
  operation_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
  amount_kopecks_ocr: Mapped[int | None] = mapped_column(Integer, nullable=True)
  expected_amount_kopecks: Mapped[int | None] = mapped_column(Integer, nullable=True)
  recipient_tail4_ocr: Mapped[str | None] = mapped_column(String(8), nullable=True)
  status: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
  created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
  updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
  intended_bets: Mapped[list["BetPaymentReceiptBet"]] = relationship(
    back_populates="receipt", cascade="all, delete-orphan"
  )


class BetPaymentReceiptBet(Base):
  __tablename__ = "bet_payment_receipt_bets"

  receipt_id: Mapped[int] = mapped_column(
    ForeignKey("bet_payment_receipts.row_id", ondelete="CASCADE"), primary_key=True
  )
  bet_id: Mapped[int] = mapped_column(
    ForeignKey("bets.row_id", ondelete="CASCADE"), primary_key=True
  )
  receipt: Mapped[BetPaymentReceipt] = relationship(back_populates="intended_bets")
