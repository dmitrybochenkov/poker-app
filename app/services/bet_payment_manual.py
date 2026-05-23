from dataclasses import dataclass

from app.db.repositories.bet_payment_receipt_repository import BetPaymentReceiptRepository
from app.db.repositories.bet_repository import BetRepository


@dataclass
class ManualReceiptDecisionResult:
  ok: bool
  message: str
  status: str
  closed_count: int = 0
  debt_kopecks: int | None = None


def _pick_fifo_bets_to_close(*, bets: list, paid_kopecks: int) -> list:
  selected: list = []
  running = 0
  for bet in bets:
    running += int(bet.amount_kopecks)
    selected.append(bet)
    if running == paid_kopecks:
      return selected
    if running > paid_kopecks:
      return []
  return []


async def apply_manual_receipt_decision(*, session, receipt_row_id: int, approve: bool) -> ManualReceiptDecisionResult:
  receipt_repo = BetPaymentReceiptRepository(session)
  bet_repo = BetRepository(session)
  receipt = await receipt_repo.get_by_row_id(row_id=int(receipt_row_id))
  if receipt is None:
    return ManualReceiptDecisionResult(ok=False, message="Квитанция не найдена.", status="not_found")
  if str(receipt.status).startswith("accepted"):
    return ManualReceiptDecisionResult(ok=False, message="Квитанция уже была принята.", status=str(receipt.status))
  if str(receipt.status).startswith("rejected"):
    return ManualReceiptDecisionResult(ok=False, message="Квитанция уже была отклонена.", status=str(receipt.status))

  if not approve:
    receipt.status = "rejected_manual"
    await session.commit()
    return ManualReceiptDecisionResult(ok=True, message="Квитанция отклонена.", status=str(receipt.status))

  amount_kopecks = int(receipt.amount_kopecks_ocr or 0)
  if amount_kopecks <= 0:
    receipt.status = "approved_no_amount"
    await session.commit()
    return ManualReceiptDecisionResult(
      ok=False,
      message="Не удалось применить: в квитанции не распознана сумма.",
      status=str(receipt.status),
    )

  unpaid = await bet_repo.list_unpaid_for_user(better_id=int(receipt.user_row_id))
  to_close = _pick_fifo_bets_to_close(bets=unpaid, paid_kopecks=amount_kopecks)
  if not to_close:
    receipt.status = "approved_no_match"
    await session.commit()
    return ManualReceiptDecisionResult(
      ok=False,
      message="Не удалось применить: сумма не бьется по FIFO с неоплаченными ставками.",
      status=str(receipt.status),
    )

  await bet_repo.mark_paid(bets=to_close)
  receipt.status = "accepted_manual"
  await session.commit()
  remaining = await bet_repo.list_unpaid_for_user(better_id=int(receipt.user_row_id))
  debt = sum(int(item.amount_kopecks) for item in remaining)
  return ManualReceiptDecisionResult(
    ok=True,
    message="Квитанция принята, ставки закрыты.",
    status=str(receipt.status),
    closed_count=len(to_close),
    debt_kopecks=debt,
  )
