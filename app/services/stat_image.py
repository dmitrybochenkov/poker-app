from __future__ import annotations

from io import BytesIO
from unicodedata import category

from PIL import Image, ImageDraw, ImageFont

EMOJI_SCALE = 1.35
EMOJI_MAX_CELL_RATIO = 1.35
EMOJI_PAIR_GAP_RATIO = 0.35


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
  cell_bbox = draw.textbbox((0, 0), "M", font=text_font)
  cell_w = max(1, cell_bbox[2] - cell_bbox[0])
  width = len(text) * cell_w
  emoji_pairs = 0
  prev_emoji = False
  for ch in text:
    is_emoji = _is_emoji_char(ch)
    if is_emoji and prev_emoji:
      emoji_pairs += 1
    prev_emoji = is_emoji
  width += emoji_pairs * max(1, int(round(cell_w * EMOJI_PAIR_GAP_RATIO)))
  return width


def _line_height(draw: ImageDraw.ImageDraw, text: str, text_font: ImageFont.ImageFont) -> int:
  text_bbox = draw.textbbox((0, 0), "M", font=text_font)
  base_text_height = max(16, text_bbox[3] - text_bbox[1])
  target_emoji_height = max(16, int(round(base_text_height * EMOJI_SCALE)))
  has_emoji = any(_is_emoji_char(ch) for ch in text)
  return max(base_text_height, target_emoji_height if has_emoji else 0)


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
  cell_w = max(1, text_bbox[2] - text_bbox[0])
  target_emoji_height = max(16, int(round((text_bbox[3] - text_bbox[1]) * EMOJI_SCALE)))
  line_h = _line_height(draw, text, text_font)
  cursor_x = x
  prev_was_emoji = False
  for ch in text:
    is_emoji = _is_emoji_char(ch)
    if is_emoji and prev_was_emoji:
      # Add visible spacing between adjacent emoji clusters in headers/tables.
      cursor_x += max(1, int(round(cell_w * EMOJI_PAIR_GAP_RATIO)))
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
        # Do not let emoji overflow into neighbouring cell.
        max_cell_w = max(1, int(round(cell_w * EMOJI_MAX_CELL_RATIO)))
        if scaled_w > max_cell_w:
          scaled_w = max_cell_w
        resized = temp.resize((scaled_w, target_emoji_height), Image.Resampling.LANCZOS)
        paste_x = cursor_x + max(0, (cell_w - scaled_w) // 2)
        paste_y = y + max(0, (line_h - target_emoji_height) // 2)
        image.paste(resized, (paste_x, paste_y), resized)
        cursor_x += cell_w
        continue
      if glyph_w > cell_w:
        # Render & shrink even if height is already close enough.
        temp = Image.new("RGBA", (glyph_w, glyph_h), (255, 255, 255, 0))
        temp_draw = ImageDraw.Draw(temp)
        temp_draw.text((-bbox[0], -bbox[1]), ch, font=font, embedded_color=True)
        max_cell_w = max(1, int(round(cell_w * EMOJI_MAX_CELL_RATIO)))
        scale = min(max_cell_w / glyph_w, target_emoji_height / glyph_h)
        scaled_w = max(1, int(round(glyph_w * scale)))
        scaled_h = max(1, int(round(glyph_h * scale)))
        resized = temp.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
        paste_x = cursor_x + max(0, (cell_w - scaled_w) // 2)
        paste_y = y + max(0, (line_h - scaled_h) // 2)
        image.paste(resized, (paste_x, paste_y), resized)
        cursor_x += cell_w
        continue
      glyph_w = max(1, bbox[2] - bbox[0])
      glyph_h = max(1, bbox[3] - bbox[1])
      draw_x = cursor_x + max(0, (cell_w - glyph_w) // 2)
      draw_y = y + max(0, (line_h - glyph_h) // 2)
      draw.text((draw_x, draw_y), ch, font=font, embedded_color=True)
      cursor_x += cell_w
      prev_was_emoji = True
      continue

    # Keep normal text rendering unchanged so names stay visually correct.
    draw.text((cursor_x, y), ch, font=font, fill=fill)
    bbox = draw.textbbox((0, 0), ch, font=font)
    cursor_x += bbox[2] - bbox[0]
    prev_was_emoji = False


def render_stat_table_png(*, title: str, report: str) -> bytes:
  lines = [line.rstrip("\n") for line in report.splitlines()]
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
  title_height = max(title_bbox[3] - title_bbox[1], _line_height(draw, title, title_font))
  title_width = _line_width(draw, title, title_font, title_emoji_font)

  line_heights: list[int] = []
  max_line_width = 0
  for line in lines:
    if line == "":
      h = max(8, int(round(_line_height(draw, "M", body_font) * 0.75)))
      line_heights.append(h)
      continue
    w = _line_width(draw, line, body_font, emoji_font)
    h = _line_height(draw, line, body_font)
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
    if line != "":
      _draw_line(image, draw, x=left_pad, y=y, text=line, fill="#111827", text_font=body_font, emoji_font=emoji_font)
    y += line_heights[i] + line_gap

  output = BytesIO()
  image.save(output, format="PNG", optimize=True)
  return output.getvalue()
