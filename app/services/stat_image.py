from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont


def _load_font(size: int) -> ImageFont.ImageFont:
  font_candidates = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
  ]
  for path in font_candidates:
    try:
      return ImageFont.truetype(path, size=size)
    except Exception:
      continue
  return ImageFont.load_default()


def render_stat_table_png(*, title: str, report: str) -> bytes:
  lines = [line.rstrip("\n") for line in report.splitlines() if line.strip() != ""]
  if not lines:
    lines = ["Нет данных"]

  title_font = _load_font(28)
  body_font = _load_font(24)
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
  title_width = title_bbox[2] - title_bbox[0]

  line_heights: list[int] = []
  max_line_width = 0
  for line in lines:
    bbox = draw.textbbox((0, 0), line, font=body_font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    max_line_width = max(max_line_width, w)
    line_heights.append(h)

  width = max(900, left_pad + max(title_width, max_line_width) + right_pad)
  height = top_pad + title_height + section_gap
  height += sum(line_heights) + line_gap * max(0, len(line_heights) - 1)
  height += bottom_pad

  image = Image.new("RGB", (width, height), "#ffffff")
  draw = ImageDraw.Draw(image)
  draw.text((left_pad, top_pad), title, font=title_font, fill="#1f2937")

  y = top_pad + title_height + section_gap
  for i, line in enumerate(lines):
    draw.text((left_pad, y), line, font=body_font, fill="#111827")
    y += line_heights[i] + line_gap

  output = BytesIO()
  image.save(output, format="PNG", optimize=True)
  return output.getvalue()

