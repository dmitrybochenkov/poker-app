import calendar
from datetime import date

from app.bot.shared.texts.inline.shared import keyboards_inline as InlineText


class InlineKeyboardBase:
  PAGE_SIZE = 5
  STAT_PAGE_SIZE = 4
  POLL_PAGE_SIZE = 4
  POLL_PAGE_SIZE_VK = 4

  @staticmethod
  def _weekday_ru(value: date) -> str:
    names = [
      InlineText.INLINEKBS__WEEKDAY_RU_TEXT_01,
      InlineText.INLINEKBS__WEEKDAY_RU_TEXT_02,
      InlineText.INLINEKBS__WEEKDAY_RU_TEXT_03,
      InlineText.INLINEKBS__WEEKDAY_RU_TEXT_04,
      InlineText.INLINEKBS__WEEKDAY_RU_TEXT_05,
      InlineText.INLINEKBS__WEEKDAY_RU_TEXT_06,
      InlineText.INLINEKBS__WEEKDAY_RU_TEXT_07,
    ]
    return names[value.weekday()]

  @staticmethod
  def _shift_month(value: date, delta: int) -> date:
    total = value.year * 12 + (value.month - 1) + delta
    year = total // 12
    month = total % 12 + 1
    return date(year, month, 1)

  @staticmethod
  def _poll_days_for_month(month: date, extra_dates: list[date] | None = None) -> list[date]:
    days_in_month = calendar.monthrange(month.year, month.month)[1]
    base_days = [
      date(month.year, month.month, day)
      for day in range(1, days_in_month + 1)
      if date(month.year, month.month, day).weekday() in {4, 5}
    ]
    if not extra_dates:
      return base_days
    merged = set(base_days)
    for item in extra_dates:
      if item.year == month.year and item.month == month.month:
        merged.add(item)
    return sorted(merged)

  @staticmethod
  def _month_label_ru(month: date) -> str:
    names = [
      InlineText.INLINEKBS__MONTH_LABEL_RU_TEXT_01,
      InlineText.INLINEKBS__MONTH_LABEL_RU_TEXT_02,
      InlineText.INLINEKBS__MONTH_LABEL_RU_TEXT_03,
      InlineText.INLINEKBS__MONTH_LABEL_RU_TEXT_04,
      InlineText.INLINEKBS__MONTH_LABEL_RU_TEXT_05,
      InlineText.INLINEKBS__MONTH_LABEL_RU_TEXT_06,
      InlineText.INLINEKBS__MONTH_LABEL_RU_TEXT_07,
      InlineText.INLINEKBS__MONTH_LABEL_RU_TEXT_08,
      InlineText.INLINEKBS__MONTH_LABEL_RU_TEXT_09,
      InlineText.INLINEKBS__MONTH_LABEL_RU_TEXT_10,
      InlineText.INLINEKBS__MONTH_LABEL_RU_TEXT_11,
      InlineText.INLINEKBS__MONTH_LABEL_RU_TEXT_12,
    ]
    return names[month.month - 1]

  @staticmethod
  def _format_rub_from_kopecks(value_kopecks: int) -> str:
    rub = int(value_kopecks) // 100
    kop = int(value_kopecks) % 100
    if kop == 0:
      return str(rub)
    return f"{rub}.{kop:02d}"
