from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.bet_payment_receipt import BetPaymentReceipt, BetPaymentReceiptBet


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
    expected_amount_kopecks: int | None = None,
    intended_bet_ids: list[int] | None = None,
  ) -> BetPaymentReceipt:
    row = BetPaymentReceipt(
      user_row_id=user_row_id,
      platform=platform,
      external_file_id=external_file_id,
      operation_id=operation_id,
      amount_kopecks_ocr=amount_kopecks_ocr,
      expected_amount_kopecks=expected_amount_kopecks,
      recipient_tail4_ocr=recipient_tail4_ocr,
      status=status,
    )
    self.session.add(row)
    await self.session.flush()
    if intended_bet_ids:
      await self.replace_intended_bets(
        receipt_row_id=int(row.row_id), bet_ids=intended_bet_ids
      )
    return row

  async def list_intended_bet_ids(self, *, receipt_row_id: int) -> list[int]:
    result = await self.session.execute(
      select(BetPaymentReceiptBet.bet_id)
      .where(BetPaymentReceiptBet.receipt_id == receipt_row_id)
      .order_by(BetPaymentReceiptBet.bet_id)
    )
    return list(result.scalars().all())

  async def replace_intended_bets(
    self, *, receipt_row_id: int, bet_ids: list[int]
  ) -> None:
    await self.session.execute(
      delete(BetPaymentReceiptBet).where(
        BetPaymentReceiptBet.receipt_id == receipt_row_id
      )
    )
    self.session.add_all(
      BetPaymentReceiptBet(receipt_id=receipt_row_id, bet_id=bet_id)
      for bet_id in sorted(set(bet_ids))
    )
    await self.session.flush()
