from __future__ import annotations

from pathlib import Path

from app.services.receipt_ocr import (
  extract_amount_rub,
  extract_operation_id,
  extract_phone_tail4,
  ocr_text_from_image_bytes,
)


def _print_report(path: Path, recipient_phone: str) -> None:
  if not path.exists():
    print(f"{path}: NOT FOUND")
    return
  raw = path.read_bytes()
  text = ocr_text_from_image_bytes(raw)
  amount_rub = extract_amount_rub(text)
  operation_id = extract_operation_id(text)
  recipient_tail4 = extract_phone_tail4(text, recipient_phone)

  print("=" * 72)
  print(f"file: {path}")
  print(f"text_len: {len(text)}")
  print(f"amount_rub: {amount_rub if amount_rub is not None else 'NOT FOUND'}")
  print(f"recipient_tail4: {recipient_tail4 if recipient_tail4 is not None else 'NOT FOUND'}")
  print(f"operation_id: {operation_id if operation_id is not None else 'NOT FOUND'}")
  print("- text preview -")
  preview = " ".join(text.split())[:500]
  print(preview if preview else "<empty>")


def main() -> None:
  # Update this number if recipient changes.
  recipient_phone = "+7 917 529-71-81"
  root = Path(__file__).resolve().parents[1]
  files = [
    root / "receipt_test_1.pdf",
    root / "receipt_test_2.pdf",
  ]
  for file_path in files:
    _print_report(file_path, recipient_phone)


if __name__ == "__main__":
  main()
