from dataclasses import dataclass

from app.services.bet_payment import confirm_receipt_payment, reject_receipt_payment


@dataclass
class ManualReceiptDecisionResult:
  ok: bool
  message: str
  status: str
  closed_count: int = 0
  debt_kopecks: int | None = None


async def apply_manual_receipt_decision(*, session, receipt_row_id: int, approve: bool) -> ManualReceiptDecisionResult:
  decision = (
    await confirm_receipt_payment(session=session, receipt_row_id=receipt_row_id)
    if approve
    else await reject_receipt_payment(session=session, receipt_row_id=receipt_row_id)
  )
  await session.commit()
  return ManualReceiptDecisionResult(
    ok=decision.ok,
    message=decision.message,
    status=decision.status,
    closed_count=decision.closed_count,
    debt_kopecks=decision.debt_kopecks,
  )
