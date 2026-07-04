#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from unicodedata import category

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "backend" / "app" / "assets" / "emoji"


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
  if len(sys.argv) < 2:
    print("Usage: python -m scripts.add_emoji_asset '👨'")
    return 1
  value = str(sys.argv[1])
  chars = [ch for ch in value if is_emoji_char(ch) and ord(ch) not in {0xFE0F, 0x200D}]
  if not chars:
    print("No emoji characters found in input.")
    return 1

  ASSETS_DIR.mkdir(parents=True, exist_ok=True)
  created = 0
  skipped = 0
  failed = 0
  for ch in chars:
    out = ASSETS_DIR / emoji_filename(ch)
    if out.exists():
      skipped += 1
      print(f"EXISTS {ch} -> {out}")
      continue
    if render_emoji_png(ch, out):
      created += 1
      print(f"CREATED {ch} -> {out}")
    else:
      failed += 1
      print(f"FAILED {ch} -> {out}")
  print(f"Created: {created}, skipped: {skipped}, failed: {failed}")
  return 0 if failed == 0 else 2


if __name__ == "__main__":
  raise SystemExit(main())
