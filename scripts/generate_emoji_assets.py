#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
from pathlib import Path
from unicodedata import category

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "app" / "assets" / "emoji"
DEFAULT_DB = ROOT / "data" / "poker_app.db"


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


def collect_required_emoji(db_path: Path) -> set[str]:
  conn = sqlite3.connect(str(db_path))
  try:
    cur = conn.cursor()
    rows: list[str] = []
    for table in ("stat_indicators", "achievements"):
      cur.execute(f"SELECT pic FROM {table}")
      rows.extend(str(item[0] or "") for item in cur.fetchall())
  finally:
    conn.close()

  chars: set[str] = set()
  for value in rows:
    for ch in value:
      if is_emoji_char(ch) and ord(ch) not in {0xFE0F, 0x200D}:
        chars.add(ch)
  return chars


def load_emoji_font(size: int) -> ImageFont.FreeTypeFont | None:
  candidates = [
    "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
    "/usr/share/fonts/truetype/noto/NotoEmoji-Regular.ttf",
    "/System/Library/Fonts/Apple Color Emoji.ttc",
    "/System/Library/Fonts/AppleColorEmoji.ttc",
  ]
  sizes = [size, 109, 128, 96, 72, 64, 48, 32]
  for path in candidates:
    for s in sizes:
      try:
        return ImageFont.truetype(path, size=s)
      except Exception:
        continue
  return None


def render_emoji_png(ch: str, out_path: Path, *, canvas: int = 128) -> bool:
  font = load_emoji_font(size=canvas - 8)
  if font is None:
    return False

  image = Image.new("RGBA", (canvas, canvas), (255, 255, 255, 0))
  draw = ImageDraw.Draw(image)
  bbox = draw.textbbox((0, 0), ch, font=font)
  w = max(1, bbox[2] - bbox[0])
  h = max(1, bbox[3] - bbox[1])
  x = (canvas - w) // 2 - bbox[0]
  y = (canvas - h) // 2 - bbox[1]
  try:
    draw.text((x, y), ch, font=font, embedded_color=True)
  except TypeError:
    draw.text((x, y), ch, font=font)
  image.save(out_path, format="PNG", optimize=True)
  return True


def main() -> int:
  db_path = DEFAULT_DB
  if not db_path.exists():
    print(f"DB not found: {db_path}")
    return 1

  ASSETS_DIR.mkdir(parents=True, exist_ok=True)
  chars = collect_required_emoji(db_path)
  if not chars:
    print("No emoji found in stat_indicators/achievements.")
    return 0

  created = 0
  skipped = 0
  failed = 0
  for ch in sorted(chars, key=lambda c: ord(c)):
    out = ASSETS_DIR / emoji_filename(ch)
    if out.exists():
      skipped += 1
      continue
    ok = render_emoji_png(ch, out)
    if ok:
      created += 1
    else:
      failed += 1
      print(f"FAILED {ch} -> {out.name}")

  print(f"Created: {created}")
  print(f"Skipped existing: {skipped}")
  print(f"Failed: {failed}")
  print(f"Dir: {ASSETS_DIR}")
  return 0 if failed == 0 else 2


if __name__ == "__main__":
  raise SystemExit(main())
