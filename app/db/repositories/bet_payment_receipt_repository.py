from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.bet_payment_receipt import BetPaymentReceipt


class BetPaymentReceiptRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def get_by_platform_and_external_file_id(self, *, platform: str, external_file_id: str) -> BetPaymentReceipt | None:
    result = await self.session.execute(
      select(BetPaymentReceipt).where(
        BetPaymentReceipt.platform == platform,
        BetPaymentReceipt.external_file_id == external_file_id,
      )
    )
    return result.scalar_one_or_none()

  async def get_by_operation_id(self, *, operation_id: str) -> BetPaymentReceipt | None:
    result = await self.session.execute(
      select(BetPaymentReceipt).where(BetPaymentReceipt.operation_id == operation_id)
    )
    return result.scalar_one_or_none()

  async def get_by_row_id(self, *, row_id: int) -> BetPaymentReceipt | None:
    result = await self.session.execute(
      select(BetPaymentReceipt).where(BetPaymentReceipt.row_id == row_id)
    )
    return result.scalar_one_or_none()

  async def create(
    self,
    *,
    user_row_id: int,
    platform: str,
    external_file_id: str | None,
    operation_id: str | None,
    amount_kopecks_ocr: int | None,
    recipient_tail4_ocr: str | None,
    status: str,
  ) -> BetPaymentReceipt:
    row = BetPaymentReceipt(
      user_row_id=user_row_id,
      platform=platform,
      external_file_id=external_file_id,
      operation_id=operation_id,
      amount_kopecks_ocr=amount_kopecks_ocr,
      recipient_tail4_ocr=recipient_tail4_ocr,
      status=status,
    )
    self.session.add(row)
    await self.session.flush()
    return row
