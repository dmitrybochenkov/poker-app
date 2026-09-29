from dataclasses import dataclass

from app.db.models.bet_payment_receipt import BetPaymentReceipt
from app.db.repositories.bet_payment_receipt_repository import BetPaymentReceiptRepository
from app.db.repositories.bet_repository import BetRepository


@dataclass(frozen=True)
class ReceiptPaymentResult:
  ok: bool
  status: str
  message: str
  closed_count: int = 0
  debt_kopecks: int | None = None


async def validate_intended_bets(*, session, user_row_id: int, intended_bet_ids: list[int]):
  ids = sorted(set(int(item) for item in intended_bet_ids))
  bets = await BetRepository(session).list_by_ids_for_user(
    bet_ids=ids, better_id=int(user_row_id)
  )
  if not ids or len(bets) != len(ids):
    return None
  if any(bet.is_paid for bet in bets):
    return None
  return bets


async def apply_exact_receipt_payment(
  *, session, receipt: BetPaymentReceipt
) -> ReceiptPaymentResult:
  receipt_repo = BetPaymentReceiptRepository(session)
  bet_repo = BetRepository(session)
  intended_ids = await receipt_repo.list_intended_bet_ids(
    receipt_row_id=int(receipt.row_id)
  )
  expected = receipt.expected_amount_kopecks
  if expected is None or not intended_ids:
    return ReceiptPaymentResult(False, "legacy", "Receipt has no durable intent.")

  bets = await bet_repo.list_by_ids_for_user(
    bet_ids=intended_ids, better_id=int(receipt.user_row_id)
  )
  if len(bets) != len(intended_ids) or sum(int(b.amount_kopecks) for b in bets) != int(expected):
    receipt.status = "manual_conflict"
    await session.flush()
    return ReceiptPaymentResult(False, receipt.status, "Payment intent is no longer valid.")

  nested = await session.begin_nested()
  affected = await bet_repo.claim_unpaid_exact(
    bet_ids=intended_ids, better_id=int(receipt.user_row_id)
  )
  if affected != len(intended_ids):
    await nested.rollback()
    receipt.status = "manual_conflict"
    await session.flush()
    return ReceiptPaymentResult(False, receipt.status, "Some intended bets were already paid.")
  await nested.commit()
  receipt.status = "accepted_auto"
  await session.flush()
  remaining = await bet_repo.list_unpaid_for_user(better_id=int(receipt.user_row_id))
  return ReceiptPaymentResult(
    True, receipt.status, "Payment accepted.", len(intended_ids),
    sum(int(item.amount_kopecks) for item in remaining),
  )


async def change_receipt_intent(
  *, session, receipt_row_id: int, intended_bet_ids: list[int]
) -> ReceiptPaymentResult:
  receipt_repo = BetPaymentReceiptRepository(session)
  receipt = await receipt_repo.get_by_row_id(row_id=int(receipt_row_id))
  if receipt is None:
    return ReceiptPaymentResult(False, "not_found", "Receipt not found.")
  if str(receipt.status).startswith(("accepted", "rejected")):
    return ReceiptPaymentResult(False, str(receipt.status), "Receipt already processed.")
  bets = await validate_intended_bets(
    session=session,
    user_row_id=int(receipt.user_row_id),
    intended_bet_ids=intended_bet_ids,
  )
  if bets is None:
    return ReceiptPaymentResult(False, "manual_conflict", "Selected bets are invalid.")
  receipt.expected_amount_kopecks = sum(int(b.amount_kopecks) for b in bets)
  receipt.status = "manual"
  await receipt_repo.replace_intended_bets(
    receipt_row_id=int(receipt.row_id),
    bet_ids=[int(b.row_id) for b in bets],
  )
  return ReceiptPaymentResult(True, receipt.status, "Payment intent updated.")


async def confirm_receipt_payment(*, session, receipt_row_id: int) -> ReceiptPaymentResult:
  receipt_repo = BetPaymentReceiptRepository(session)
  receipt = await receipt_repo.get_by_row_id(row_id=int(receipt_row_id))
  if receipt is None:
    return ReceiptPaymentResult(False, "not_found", "Receipt not found.")
  if str(receipt.status).startswith(("accepted", "rejected")):
    return ReceiptPaymentResult(False, str(receipt.status), "Receipt already processed.")
  intended_ids = await receipt_repo.list_intended_bet_ids(receipt_row_id=int(receipt.row_id))
  if receipt.expected_amount_kopecks is not None and intended_ids:
    result = await apply_exact_receipt_payment(session=session, receipt=receipt)
    if result.ok:
      receipt.status = "accepted_manual"
      await session.flush()
      return ReceiptPaymentResult(
        True, receipt.status, result.message, result.closed_count, result.debt_kopecks
      )
    return result

  amount = int(receipt.amount_kopecks_ocr or 0)
  unpaid = await BetRepository(session).list_unpaid_for_user(
    better_id=int(receipt.user_row_id)
  )
  selected = []
  running = 0
  for bet in unpaid:
    running += int(bet.amount_kopecks)
    selected.append(bet)
    if running >= amount:
      break
  if amount <= 0 or running != amount:
    receipt.status = "approved_no_match"
    await session.flush()
    return ReceiptPaymentResult(False, receipt.status, "Legacy FIFO amount did not match.")
  await BetRepository(session).mark_paid(bets=selected)
  receipt.status = "accepted_manual_legacy"
  await session.flush()
  remaining = await BetRepository(session).list_unpaid_for_user(
    better_id=int(receipt.user_row_id)
  )
  return ReceiptPaymentResult(
    True,
    receipt.status,
    "Legacy payment accepted.",
    len(selected),
    sum(int(item.amount_kopecks) for item in remaining),
  )


async def reject_receipt_payment(*, session, receipt_row_id: int) -> ReceiptPaymentResult:
  receipt = await BetPaymentReceiptRepository(session).get_by_row_id(row_id=receipt_row_id)
  if receipt is None:
    return ReceiptPaymentResult(False, "not_found", "Receipt not found.")
  if str(receipt.status).startswith(("accepted", "rejected")):
    return ReceiptPaymentResult(False, str(receipt.status), "Receipt already processed.")
  receipt.status = "rejected_manual"
  await session.flush()
  return ReceiptPaymentResult(True, receipt.status, "Receipt rejected.")
