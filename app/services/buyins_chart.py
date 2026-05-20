from __future__ import annotations

from datetime import date
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont


def _load_font(size: int) -> ImageFont.ImageFont:
  candidates = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
  ]
  for path in candidates:
    try:
      return ImageFont.truetype(path, size=size)
    except Exception:
      continue
  return ImageFont.load_default()


def render_buyins_history_chart_png(
  *,
  title: str,
  series: dict[str, list[tuple[date, int]]],
) -> bytes:
  width = 1280
  height = 720
  pad_left = 90
  pad_right = 340
  pad_top = 90
  pad_bottom = 90
  plot_w = width - pad_left - pad_right
  plot_h = height - pad_top - pad_bottom
  if plot_w < 200 or plot_h < 200:
    plot_w = 200
    plot_h = 200

  image = Image.new("RGB", (width, height), "#ffffff")
  draw = ImageDraw.Draw(image)
  title_font = _load_font(36)
  body_font = _load_font(20)
  small_font = _load_font(16)

  draw.text((pad_left, 28), title, fill="#111827", font=title_font)

  all_dates = sorted({d for points in series.values() for d, _ in points})
  if not all_dates:
    draw.text((pad_left, pad_top), "Нет данных для графика", fill="#6b7280", font=body_font)
    out = BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()

  max_buyins = max((max(v for _, v in points) for points in series.values() if points), default=1)
  y_max = max(1, max_buyins)
  y_steps = min(6, y_max) if y_max > 0 else 1

  x0 = pad_left
  y0 = pad_top + plot_h
  x1 = pad_left + plot_w
  y1 = pad_top
  draw.line([(x0, y0), (x1, y0)], fill="#374151", width=2)
  draw.line([(x0, y0), (x0, y1)], fill="#374151", width=2)

  for i in range(y_steps + 1):
    ratio = i / y_steps if y_steps else 0
    value = int(round(y_max * ratio))
    y = int(round(y0 - ratio * plot_h))
    draw.line([(x0, y), (x1, y)], fill="#e5e7eb", width=1)
    draw.text((x0 - 52, y - 10), str(value), fill="#6b7280", font=small_font)

  if len(all_dates) == 1:
    date_ticks = [all_dates[0]]
  else:
    step = max(1, len(all_dates) // 6)
    date_ticks = [all_dates[i] for i in range(0, len(all_dates), step)]
    if date_ticks[-1] != all_dates[-1]:
      date_ticks.append(all_dates[-1])

  def x_for_date(d: date) -> int:
    if len(all_dates) == 1:
      return x0 + plot_w // 2
    idx = all_dates.index(d)
    return int(round(x0 + (idx / (len(all_dates) - 1)) * plot_w))

  for d in date_ticks:
    x = x_for_date(d)
    draw.line([(x, y0), (x, y0 + 8)], fill="#9ca3af", width=1)
    draw.text((x - 28, y0 + 14), d.strftime("%d.%m"), fill="#6b7280", font=small_font)

  palette = [
    "#2563eb",
    "#dc2626",
    "#16a34a",
    "#7c3aed",
    "#ea580c",
    "#0d9488",
    "#db2777",
    "#4b5563",
    "#0891b2",
    "#65a30d",
  ]

  legend_x = x1 + 24
  legend_y = y1 + 8
  sorted_series = sorted(series.items(), key=lambda item: item[1][-1][1] if item[1] else 0, reverse=True)

  for idx, (name, points) in enumerate(sorted_series):
    if not points:
      continue
    color = palette[idx % len(palette)]
    coords: list[tuple[int, int]] = []
    for d, buyins in points:
      x = x_for_date(d)
      y = int(round(y0 - (max(0, int(buyins)) / y_max) * plot_h))
      coords.append((x, y))
    if len(coords) >= 2:
      draw.line(coords, fill=color, width=3, joint="curve")
    for x, y in coords:
      r = 4
      draw.ellipse((x - r, y - r, x + r, y + r), fill=color, outline="#ffffff", width=1)

    ly = legend_y + idx * 28
    draw.line([(legend_x, ly + 10), (legend_x + 24, ly + 10)], fill=color, width=3)
    draw.text((legend_x + 34, ly), f"{name} ({points[-1][1]})", fill="#111827", font=small_font)

  draw.text((pad_left, y1 - 34), "Закупы", fill="#6b7280", font=small_font)
  draw.text((x1 - 32, y0 + 44), "Время", fill="#6b7280", font=small_font)

  out = BytesIO()
  image.save(out, format="PNG", optimize=True)
  return out.getvalue()
