from __future__ import annotations

from io import BytesIO
from unicodedata import category

from PIL import Image, ImageDraw, ImageFont


def _load_font(size: int) -> ImageFont.ImageFont:
  font_candidates = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Menlo.ttc",
  ]
  for path in font_candidates:
    try:
      return ImageFont.truetype(path, size=size)
    except Exception:
      continue
  return ImageFont.load_default()


def _load_emoji_font(size: int) -> ImageFont.ImageFont:
  emoji_candidates = [
    "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
    "/usr/share/fonts/truetype/noto/NotoEmoji-Regular.ttf",
    "/System/Library/Fonts/Apple Color Emoji.ttc",
    "/System/Library/Fonts/AppleColorEmoji.ttc",
  ]
  for path in emoji_candidates:
    # Noto Color Emoji has fixed bitmap strike sizes on many systems.
    # Try requested size first, then common fallback sizes.
    sizes = [size, 109, 128, 64, 32, 24, 20, 18, 16]
    seen: set[int] = set()
    for candidate_size in sizes:
      if candidate_size in seen:
        continue
      seen.add(candidate_size)
      try:
        return ImageFont.truetype(path, size=candidate_size)
      except Exception:
        continue
  return _load_font(size=size)


def _is_emoji_char(ch: str) -> bool:
  code = ord(ch)
  return (
    0x1F300 <= code <= 0x1FAFF
    or 0x2600 <= code <= 0x27BF
    or code in {0xFE0F, 0x200D}
    or category(ch) == "So"
  )


def _line_width(draw: ImageDraw.ImageDraw, text: str, text_font: ImageFont.ImageFont, emoji_font: ImageFont.ImageFont) -> int:
  text_bbox = draw.textbbox((0, 0), "M", font=text_font)
  target_emoji_height = max(16, text_bbox[3] - text_bbox[1])
  width = 0
  for ch in text:
    if _is_emoji_char(ch):
      bbox = draw.textbbox((0, 0), ch, font=emoji_font)
      glyph_w = max(1, bbox[2] - bbox[0])
      glyph_h = max(1, bbox[3] - bbox[1])
      if glyph_h > int(target_emoji_height * 1.35):
        glyph_w = max(1, int(round(glyph_w * (target_emoji_height / glyph_h))))
      width += glyph_w
      continue
    bbox = draw.textbbox((0, 0), ch, font=text_font)
    width += bbox[2] - bbox[0]
  return width


def _draw_line(
  image: Image.Image,
  draw: ImageDraw.ImageDraw,
  *,
  x: int,
  y: int,
  text: str,
  fill: str,
  text_font: ImageFont.ImageFont,
  emoji_font: ImageFont.ImageFont,
) -> None:
  text_bbox = draw.textbbox((0, 0), "M", font=text_font)
  target_emoji_height = max(16, text_bbox[3] - text_bbox[1])
  cursor_x = x
  for ch in text:
    is_emoji = _is_emoji_char(ch)
    font = emoji_font if is_emoji else text_font
    if is_emoji:
      bbox = draw.textbbox((0, 0), ch, font=font)
      glyph_w = max(1, bbox[2] - bbox[0])
      glyph_h = max(1, bbox[3] - bbox[1])
      if glyph_h > int(target_emoji_height * 1.35):
        # Render large color-emoji glyph to temp image and scale down to text row height.
        temp = Image.new("RGBA", (glyph_w, glyph_h), (255, 255, 255, 0))
        temp_draw = ImageDraw.Draw(temp)
        temp_draw.text((-bbox[0], -bbox[1]), ch, font=font, embedded_color=True)
        scaled_w = max(1, int(round(glyph_w * (target_emoji_height / glyph_h))))
        resized = temp.resize((scaled_w, target_emoji_height), Image.Resampling.LANCZOS)
        image.paste(resized, (cursor_x, y), resized)
        cursor_x += scaled_w
        continue
      draw.text((cursor_x, y), ch, font=font, embedded_color=True)
    else:
      draw.text((cursor_x, y), ch, font=font, fill=fill)
    bbox = draw.textbbox((0, 0), ch, font=font)
    cursor_x += bbox[2] - bbox[0]


def render_stat_table_png(*, title: str, report: str) -> bytes:
  lines = [line.rstrip("\n") for line in report.splitlines() if line.strip() != ""]
  if not lines:
    lines = ["Нет данных"]

  title_font = _load_font(28)
  body_font = _load_font(24)
  emoji_font = _load_emoji_font(24)
  title_emoji_font = _load_emoji_font(28)
  left_pad = 36
  right_pad = 36
  top_pad = 28
  bottom_pad = 28
  line_gap = 10
  section_gap = 22

  probe = Image.new("RGB", (32, 32), "white")
  draw = ImageDraw.Draw(probe)

  title_bbox = draw.textbbox((0, 0), title, font=title_font)
  title_height = title_bbox[3] - title_bbox[1]
  title_width = _line_width(draw, title, title_font, title_emoji_font)

  line_heights: list[int] = []
  max_line_width = 0
  for line in lines:
    bbox = draw.textbbox((0, 0), line, font=body_font)
    w = _line_width(draw, line, body_font, emoji_font)
    h = bbox[3] - bbox[1]
    max_line_width = max(max_line_width, w)
    line_heights.append(h)

  width = max(480, left_pad + max(title_width, max_line_width) + right_pad)
  height = top_pad + title_height + section_gap
  height += sum(line_heights) + line_gap * max(0, len(line_heights) - 1)
  height += bottom_pad

  image = Image.new("RGBA", (width, height), "#ffffff")
  draw = ImageDraw.Draw(image)
  _draw_line(image, draw, x=left_pad, y=top_pad, text=title, fill="#1f2937", text_font=title_font, emoji_font=title_emoji_font)

  y = top_pad + title_height + section_gap
  for i, line in enumerate(lines):
    _draw_line(image, draw, x=left_pad, y=y, text=line, fill="#111827", text_font=body_font, emoji_font=emoji_font)
    y += line_heights[i] + line_gap

  output = BytesIO()
  image.save(output, format="PNG", optimize=True)
  return output.getvalue()
