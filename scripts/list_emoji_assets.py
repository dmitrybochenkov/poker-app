#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from unicodedata import category

ROOT = Path(__file__).resolve().parents[1]


def is_emoji_char(ch: str) -> bool:
  code = ord(ch)
  return (
    0x1F300 <= code <= 0x1FAFF
    or 0x2600 <= code <= 0x27BF
    or code in {0xFE0F, 0x200D}
    or category(ch) == "So"
  )


def emoji_filename(ch: str) -> str:
  return f"{ord(ch):x}.png"


def collect_chars(raw: str) -> set[str]:
  return {ch for ch in raw if is_emoji_char(ch) and ord(ch) not in {0xFE0F, 0x200D}}


def main() -> int:
  db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "poker_app.db"
  if not db_path.exists():
    print(f"DB not found: {db_path}")
    return 1

  conn = sqlite3.connect(str(db_path))
  try:
    cursor = conn.cursor()
    rows: list[str] = []
    for table in ("stat_indicators", "achievements"):
      cursor.execute(f"SELECT pic FROM {table}")
      rows.extend(str(item[0] or "") for item in cursor.fetchall())
  finally:
    conn.close()

  chars: set[str] = set()
  for value in rows:
    chars |= collect_chars(value)

  print("Required emoji assets:")
  for ch in sorted(chars, key=lambda c: ord(c)):
    print(f"{ch} -> {emoji_filename(ch)}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
