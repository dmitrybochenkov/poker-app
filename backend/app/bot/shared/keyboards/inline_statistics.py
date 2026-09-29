from datetime import date

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.shared.keyboards.keyboards_reply import ReplyKbs
from app.bot.shared.texts.inline.shared import keyboards_inline as InlineText

from .inline_base import InlineKeyboardBase


class StatisticsInlineKbs(InlineKeyboardBase):
  BETTING_TOURNAMENT_PAGE_SIZE = 5

  @staticmethod
  def betting_tournament_periods_tg(
    *, periods: list, selected_period_ids: set[str] | list[str], page: int = 0, today: date | None = None
  ) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    selected = set(selected_period_ids)
    start = page * StatisticsInlineKbs.BETTING_TOURNAMENT_PAGE_SIZE
    end = start + StatisticsInlineKbs.BETTING_TOURNAMENT_PAGE_SIZE
    batch = periods[start:end]
    for period in batch:
      mark = InlineText.BETTING_TOURNAMENT_SELECTED if period.selection_id in selected else ""
      keyboard.button(
        text=f"{mark}{period.display_label(today=today)}"[:64],
        callback_data=f"betstattour_toggle:{period.selection_id}:{page}",
      )
    if page > 0:
      keyboard.button(text=InlineText.PAGE_PREVIOUS, callback_data=f"betstattour_page:{page - 1}")
    if end < len(periods):
      keyboard.button(text=InlineText.PAGE_NEXT, callback_data=f"betstattour_page:{page + 1}")
    keyboard.button(text=InlineText.BETTING_TOURNAMENT_BACK, callback_data="betstattour_back")
    keyboard.button(text=InlineText.INLINEKBS_STAT_YEAR_TG_TEXT_01, callback_data="betstattour_done")
    keyboard.button(text=InlineText.INLINEKBS_STAT_YEAR_TG_TEXT_02, callback_data="betstattour_cancel")
    sizes = [1] * len(batch)
    nav_count = int(page > 0) + int(end < len(periods))
    if nav_count:
      sizes.append(nav_count)
    sizes.append(3)
    keyboard.adjust(*sizes)
    return keyboard.as_markup()

  @staticmethod
  def betting_tournament_periods_vk(
    *, periods: list, selected_period_ids: set[str] | list[str], page: int = 0, today: date | None = None
  ) -> str:
    selected = set(selected_period_ids)
    rows: list[list[dict]] = []
    start = page * StatisticsInlineKbs.BETTING_TOURNAMENT_PAGE_SIZE
    end = start + StatisticsInlineKbs.BETTING_TOURNAMENT_PAGE_SIZE
    batch = periods[start:end]
    for period in batch:
      mark = InlineText.BETTING_TOURNAMENT_SELECTED if period.selection_id in selected else ""
      rows.append([{
        "action": {
          "type": "callback",
          "label": f"{mark}{period.display_label(today=today)}"[:40],
          "payload": {"action": "betstattour_toggle", "period_id": period.selection_id, "page": page},
        },
        "color": "primary",
      }])
    nav_row = []
    if page > 0:
      nav_row.append({"action": {"type": "callback", "label": InlineText.PAGE_PREVIOUS, "payload": {"action": "betstattour_page", "page": page - 1}}, "color": "secondary"})
    if end < len(periods):
      nav_row.append({"action": {"type": "callback", "label": InlineText.PAGE_NEXT, "payload": {"action": "betstattour_page", "page": page + 1}}, "color": "secondary"})
    if nav_row:
      rows.append(nav_row)
    rows.append([
      {"action": {"type": "callback", "label": InlineText.BETTING_TOURNAMENT_BACK, "payload": {"action": "betstattour_back"}}, "color": "secondary"},
      {"action": {"type": "callback", "label": InlineText.INLINEKBS_STAT_YEAR_VK_TEXT_01, "payload": {"action": "betstattour_done"}}, "color": "positive"},
      {"action": {"type": "callback", "label": InlineText.INLINEKBS_STAT_YEAR_VK_TEXT_02, "payload": {"action": "betstattour_cancel"}}, "color": "negative"},
    ])
    return ReplyKbs.make_vk_callback(rows)

  @staticmethod
  def betting_stat_indicators_tg(*, indicators: list, page: int = 0, selected_ids: list[int] | None = None) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    selected = set(selected_ids or [])
    start = page * StatisticsInlineKbs.STAT_PAGE_SIZE
    end = start + StatisticsInlineKbs.STAT_PAGE_SIZE
    batch = indicators[start:end]
    for indicator in batch:
      mark = InlineText.BET_RECEIPT_MANUAL_SELECT_TG_MARKER_11 if int(indicator.row_id) in selected else ""
      keyboard.button(text=f"{mark}{indicator.pic} {indicator.description}"[:64], callback_data=f"betstat_toggle:{indicator.row_id}:{page}")
    if page > 0:
      keyboard.button(text=InlineText.PAGE_PREVIOUS, callback_data=f"betstat_page:{page - 1}")
    if end < len(indicators):
      keyboard.button(text=InlineText.PAGE_NEXT, callback_data=f"betstat_page:{page + 1}")
    keyboard.button(text=InlineText.BETTING_TOURNAMENT_BACK, callback_data="betstat_back")
    keyboard.button(text=InlineText.INLINEKBS_BETTING_STAT_INDICATORS_TG_TEXT_01, callback_data="betstat_done")
    keyboard.button(text=InlineText.INLINEKBS_BETTING_STAT_INDICATORS_TG_TEXT_02, callback_data="betstat_cancel")
    sizes = [1] * len(batch)
    nav_count = int(page > 0) + int(end < len(indicators))
    if nav_count:
      sizes.append(nav_count)
    sizes.append(3)
    keyboard.adjust(*sizes)
    return keyboard.as_markup()

  @staticmethod
  def betting_stat_indicators_vk(*, indicators: list, page: int = 0, selected_ids: list[int] | None = None) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    selected = set(selected_ids or [])
    start = page * StatisticsInlineKbs.STAT_PAGE_SIZE
    end = start + StatisticsInlineKbs.STAT_PAGE_SIZE
    batch = indicators[start:end]
    for indicator in batch:
      mark = InlineText.BET_RECEIPT_MANUAL_SELECT_TG_MARKER_11 if int(indicator.row_id) in selected else ""
      rows.append([
        {
          "action": {
            "type": "callback",
            "label": f"{mark}{indicator.pic} {indicator.description}"[:40],
            "payload": {"action": "betstat_toggle", "indicator_id": int(indicator.row_id), "page": page},
          },
          "color": "primary",
        }
      ])
    nav_row: list[dict[str, str | dict[str, int | str]]] = []
    if page > 0:
      nav_row.append({
        "action": {"type": "callback", "label": InlineText.PAGE_PREVIOUS, "payload": {"action": "betstat_page", "page": page - 1}},
        "color": "secondary",
      })
    if end < len(indicators):
      nav_row.append({
        "action": {"type": "callback", "label": InlineText.PAGE_NEXT, "payload": {"action": "betstat_page", "page": page + 1}},
        "color": "secondary",
      })
    if nav_row:
      rows.append(nav_row)
    rows.append([
      {
        "action": {"type": "callback", "label": InlineText.BETTING_TOURNAMENT_BACK, "payload": {"action": "betstat_back"}},
        "color": "secondary",
      },
      {
        "action": {"type": "callback", "label": InlineText.INLINEKBS_BETTING_STAT_INDICATORS_VK_TEXT_01, "payload": {"action": "betstat_done"}},
        "color": "positive",
      },
      {
        "action": {"type": "callback", "label": InlineText.INLINEKBS_BETTING_STAT_INDICATORS_VK_TEXT_02, "payload": {"action": "betstat_cancel"}},
        "color": "negative",
      },
    ])
    return ReplyKbs.make_vk_callback(rows)

  @staticmethod
  def poker_stat_indicators_tg(*, indicators: list, page: int = 0, selected_ids: list[int] | None = None) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    selected = set(selected_ids or [])
    start = page * StatisticsInlineKbs.STAT_PAGE_SIZE
    end = start + StatisticsInlineKbs.STAT_PAGE_SIZE
    batch = indicators[start:end]
    for indicator in batch:
      mark = InlineText.BET_RECEIPT_MANUAL_SELECT_TG_MARKER_11 if int(indicator.row_id) in selected else ""
      keyboard.button(text=f"{mark}{indicator.pic} {indicator.description}"[:64], callback_data=f"pokerstat_toggle:{indicator.row_id}:{page}")
    if page > 0:
      keyboard.button(text=InlineText.PAGE_PREVIOUS, callback_data=f"pokerstat_page:{page - 1}")
    if end < len(indicators):
      keyboard.button(text=InlineText.PAGE_NEXT, callback_data=f"pokerstat_page:{page + 1}")
    keyboard.button(text=InlineText.INLINEKBS_POKER_STAT_INDICATORS_TG_TEXT_01, callback_data="pokerstat_done")
    keyboard.button(text=InlineText.INLINEKBS_POKER_STAT_INDICATORS_TG_TEXT_02, callback_data="pokerstat_cancel")
    sizes = [1] * len(batch)
    nav_count = int(page > 0) + int(end < len(indicators))
    if nav_count:
      sizes.append(nav_count)
    sizes.append(2)
    keyboard.adjust(*sizes)
    return keyboard.as_markup()

  @staticmethod
  def poker_stat_indicators_vk(*, indicators: list, page: int = 0, selected_ids: list[int] | None = None) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    selected = set(selected_ids or [])
    start = page * StatisticsInlineKbs.STAT_PAGE_SIZE
    end = start + StatisticsInlineKbs.STAT_PAGE_SIZE
    batch = indicators[start:end]
    for indicator in batch:
      mark = InlineText.BET_RECEIPT_MANUAL_SELECT_TG_MARKER_11 if int(indicator.row_id) in selected else ""
      rows.append([
        {
          "action": {
            "type": "callback",
            "label": f"{mark}{indicator.pic} {indicator.description}"[:40],
            "payload": {"action": "pokerstat_toggle", "indicator_id": int(indicator.row_id), "page": page},
          },
          "color": "primary",
        }
      ])
    nav_row: list[dict[str, str | dict[str, int | str]]] = []
    if page > 0:
      nav_row.append({
        "action": {"type": "callback", "label": InlineText.PAGE_PREVIOUS, "payload": {"action": "pokerstat_page", "page": page - 1}},
        "color": "secondary",
      })
    if end < len(indicators):
      nav_row.append({
        "action": {"type": "callback", "label": InlineText.PAGE_NEXT, "payload": {"action": "pokerstat_page", "page": page + 1}},
        "color": "secondary",
      })
    if nav_row:
      rows.append(nav_row)
    rows.append([
      {
        "action": {"type": "callback", "label": InlineText.INLINEKBS_POKER_STAT_INDICATORS_VK_TEXT_01, "payload": {"action": "pokerstat_done"}},
        "color": "positive",
      },
      {
        "action": {"type": "callback", "label": InlineText.INLINEKBS_POKER_STAT_INDICATORS_VK_TEXT_02, "payload": {"action": "pokerstat_cancel"}},
        "color": "negative",
      },
    ])
    return ReplyKbs.make_vk_callback(rows)

  @staticmethod
  def stat_year_tg(
    *,
    prefix: str,
    years: list[int],
    selected_years: list[int] | None = None,
    page: int = 0,
  ) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    selected = {int(item) for item in (selected_years or [])}
    start = page * StatisticsInlineKbs.STAT_PAGE_SIZE
    end = start + StatisticsInlineKbs.STAT_PAGE_SIZE
    batch = years[start:end]
    for year in batch:
      mark = InlineText.BET_RECEIPT_MANUAL_SELECT_TG_MARKER_11 if int(year) in selected else ""
      keyboard.button(text=f"{mark}{year}", callback_data=f"{prefix}_toggle:{year}:{page}")
    if page > 0:
      keyboard.button(text=InlineText.PAGE_PREVIOUS, callback_data=f"{prefix}_page:{page - 1}")
    if end < len(years):
      keyboard.button(text=InlineText.PAGE_NEXT, callback_data=f"{prefix}_page:{page + 1}")
    keyboard.button(text=InlineText.INLINEKBS_STAT_YEAR_TG_TEXT_01, callback_data=f"{prefix}_done")
    keyboard.button(text=InlineText.INLINEKBS_STAT_YEAR_TG_TEXT_02, callback_data=f"{prefix}_cancel")
    sizes = [1] * len(batch)
    nav_count = int(page > 0) + int(end < len(years))
    if nav_count:
      sizes.append(nav_count)
    sizes.append(2)
    keyboard.adjust(*sizes)
    return keyboard.as_markup()

  @staticmethod
  def stat_year_vk(
    *,
    action: str,
    years: list[int],
    selected_years: list[int] | None = None,
    page: int = 0,
  ) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    selected = {int(item) for item in (selected_years or [])}
    start = page * StatisticsInlineKbs.STAT_PAGE_SIZE
    end = start + StatisticsInlineKbs.STAT_PAGE_SIZE
    batch = years[start:end]
    for year in batch:
      mark = InlineText.BET_RECEIPT_MANUAL_SELECT_TG_MARKER_11 if int(year) in selected else ""
      rows.append([
        {
          "action": {"type": "callback", "label": f"{mark}{year}", "payload": {"action": f"{action}_toggle", "year": int(year), "page": page}},
          "color": "primary",
        }
      ])
    nav_row: list[dict[str, str | dict[str, int | str]]] = []
    if page > 0:
      nav_row.append({"action": {"type": "callback", "label": InlineText.PAGE_PREVIOUS, "payload": {"action": f"{action}_page", "page": page - 1}}, "color": "secondary"})
    if end < len(years):
      nav_row.append({"action": {"type": "callback", "label": InlineText.PAGE_NEXT, "payload": {"action": f"{action}_page", "page": page + 1}}, "color": "secondary"})
    if nav_row:
      rows.append(nav_row)
    rows.append([
      {"action": {"type": "callback", "label": InlineText.INLINEKBS_STAT_YEAR_VK_TEXT_01, "payload": {"action": f"{action}_done"}}, "color": "positive"},
      {"action": {"type": "callback", "label": InlineText.INLINEKBS_STAT_YEAR_VK_TEXT_02, "payload": {"action": f"{action}_cancel"}}, "color": "negative"},
    ])
    return ReplyKbs.make_vk_callback(rows)

  @staticmethod
  def stat_sort_tg(
    *,
    prefix: str,
    indicators: list,
    selected_ids: list[int],
    selected_sort_id: int | None = None,
    page: int = 0,
  ) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    selected = {int(x) for x in selected_ids}
    filtered = [indicator for indicator in indicators if int(indicator.row_id) in selected]
    start = page * StatisticsInlineKbs.STAT_PAGE_SIZE
    end = start + StatisticsInlineKbs.STAT_PAGE_SIZE
    batch = filtered[start:end]
    for indicator in batch:
      mark = InlineText.BET_RECEIPT_MANUAL_SELECT_TG_MARKER_11 if selected_sort_id is not None and int(indicator.row_id) == int(selected_sort_id) else ""
      keyboard.button(
        text=f"{mark}{indicator.pic} {indicator.description}"[:64],
        callback_data=f"{prefix}_toggle:{int(indicator.row_id)}:{page}",
      )
    if page > 0:
      keyboard.button(text=InlineText.PAGE_PREVIOUS, callback_data=f"{prefix}_page:{page - 1}")
    if end < len(filtered):
      keyboard.button(text=InlineText.PAGE_NEXT, callback_data=f"{prefix}_page:{page + 1}")
    if prefix == "betstatsort":
      keyboard.button(text=InlineText.BETTING_TOURNAMENT_BACK, callback_data="betstatsort_back")
    keyboard.button(text=InlineText.INLINEKBS_STAT_SORT_TG_TEXT_01, callback_data=f"{prefix}_done")
    keyboard.button(text=InlineText.INLINEKBS_STAT_SORT_TG_TEXT_02, callback_data=f"{prefix}_cancel")
    sizes = [1] * len(batch)
    nav_count = int(page > 0) + int(end < len(filtered))
    if nav_count:
      sizes.append(nav_count)
    sizes.append(3 if prefix == "betstatsort" else 2)
    keyboard.adjust(*sizes)
    return keyboard.as_markup()

  @staticmethod
  def stat_sort_vk(
    *,
    action: str,
    indicators: list,
    selected_ids: list[int],
    selected_sort_id: int | None = None,
    page: int = 0,
  ) -> str:
    selected = {int(x) for x in selected_ids}
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    filtered = [indicator for indicator in indicators if int(indicator.row_id) in selected]
    start = page * StatisticsInlineKbs.STAT_PAGE_SIZE
    end = start + StatisticsInlineKbs.STAT_PAGE_SIZE
    batch = filtered[start:end]
    for indicator in batch:
      mark = InlineText.BET_RECEIPT_MANUAL_SELECT_TG_MARKER_11 if selected_sort_id is not None and int(indicator.row_id) == int(selected_sort_id) else ""
      rows.append([
        {
          "action": {
            "type": "callback",
            "label": f"{mark}{indicator.pic} {indicator.description}"[:40],
            "payload": {"action": action, "indicator_id": int(indicator.row_id), "page": page},
          },
          "color": "primary",
        }
      ])
    nav_row: list[dict[str, str | dict[str, int | str]]] = []
    if page > 0:
      nav_row.append({
        "action": {"type": "callback", "label": InlineText.PAGE_PREVIOUS, "payload": {"action": f"{action}_page", "page": page - 1}},
        "color": "secondary",
      })
    if end < len(filtered):
      nav_row.append({
        "action": {"type": "callback", "label": InlineText.PAGE_NEXT, "payload": {"action": f"{action}_page", "page": page + 1}},
        "color": "secondary",
      })
    if nav_row:
      rows.append(nav_row)
    actions_row = []
    if action == "betstat_sort":
      actions_row.append({
        "action": {"type": "callback", "label": InlineText.BETTING_TOURNAMENT_BACK, "payload": {"action": "betstatsort_back"}},
        "color": "secondary",
      })
    actions_row.extend([
      {
        "action": {"type": "callback", "label": InlineText.INLINEKBS_STAT_SORT_VK_TEXT_01, "payload": {"action": f"{action}_done"}},
        "color": "positive",
      },
      {
        "action": {"type": "callback", "label": InlineText.INLINEKBS_STAT_SORT_VK_TEXT_02, "payload": {"action": f"{action}_cancel"}},
        "color": "negative",
      },
    ])
    rows.append(actions_row)
    return ReplyKbs.make_vk_callback(rows)

  @staticmethod
  def poker_history_year_tg(*, years: list[int]) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    for year in years:
      keyboard.button(text=str(int(year)), callback_data=f"pokerhistyear:{int(year)}")
    keyboard.button(text=InlineText.INLINEKBS_POKER_HISTORY_YEAR_TG_TEXT_01, callback_data="pokerhist_cancel")
    keyboard.adjust(1, *(1 for _ in years[1:]), 1)
    return keyboard.as_markup()

  @staticmethod
  def poker_history_year_vk(*, years: list[int]) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    for year in years:
      rows.append([
        {
          "action": {"type": "callback", "label": str(int(year)), "payload": {"action": "pokerhistyear", "year": int(year)}},
          "color": "primary",
        }
      ])
    rows.append([
      {
        "action": {"type": "callback", "label": InlineText.INLINEKBS_POKER_HISTORY_YEAR_VK_TEXT_01, "payload": {"action": "pokerhist_cancel"}},
        "color": "negative",
      }
    ])
    return ReplyKbs.make_vk_callback(rows)

  @staticmethod
  def poker_history_dates_tg(*, year: int, dates: list[date], page: int = 0) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    page_size = 6
    start = page * page_size
    end = start + page_size
    batch = dates[start:end]
    for item in batch:
      keyboard.button(text=item.strftime("%d.%m"), callback_data=f"pokerhistdate:{int(year)}:{int(page)}:{item.isoformat()}")
    if page > 0:
      keyboard.button(text=InlineText.PAGE_PREVIOUS, callback_data=f"pokerhistpage:{int(year)}:{int(page - 1)}")
    if end < len(dates):
      keyboard.button(text=InlineText.PAGE_NEXT, callback_data=f"pokerhistpage:{int(year)}:{int(page + 1)}")
    sizes = [3, 3]
    nav_count = int(page > 0) + int(end < len(dates))
    if nav_count:
      sizes.append(nav_count)
    keyboard.adjust(*sizes)
    return keyboard.as_markup()

  @staticmethod
  def poker_history_dates_vk(*, year: int, dates: list[date], page: int = 0) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    page_size = 6
    start = page * page_size
    end = start + page_size
    batch = dates[start:end]
    for index in range(0, len(batch), 3):
      row_items = batch[index:index + 3]
      row: list[dict[str, str | dict[str, int | str]]] = []
      for item in row_items:
        row.append(
          {
            "action": {
              "type": "callback",
              "label": item.strftime("%d.%m"),
              "payload": {"action": "pokerhistdate", "year": int(year), "page": int(page), "date": item.isoformat()},
            },
            "color": "primary",
          }
        )
      rows.append(row)
    nav_row: list[dict[str, str | dict[str, int | str]]] = []
    if page > 0:
      nav_row.append(
        {"action": {"type": "callback", "label": InlineText.PAGE_PREVIOUS, "payload": {"action": "pokerhistpage", "year": int(year), "page": int(page - 1)}}, "color": "secondary"}
      )
    if end < len(dates):
      nav_row.append(
        {"action": {"type": "callback", "label": InlineText.PAGE_NEXT, "payload": {"action": "pokerhistpage", "year": int(year), "page": int(page + 1)}}, "color": "secondary"}
      )
    if nav_row:
      rows.append(nav_row)
    return ReplyKbs.make_vk_callback(rows)
