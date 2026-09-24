from datetime import date

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.shared.keyboards.keyboards_reply import ReplyKbs
from app.bot.shared.texts.inline.shared import keyboards_inline as InlineText

from .inline_base import InlineKeyboardBase

class PollInlineKbs(InlineKeyboardBase):
  @staticmethod
  def poll_month_tg(
    *,
    month: date,
    page: int = 0,
    selected_dates: list[date] | None = None,
    extra_dates: list[date] | None = None,
  ) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    selected = {item.isoformat() for item in (selected_dates or [])}
    all_dates = PollInlineKbs._poll_days_for_month(month, extra_dates=extra_dates)
    start = page * PollInlineKbs.POLL_PAGE_SIZE
    end = start + PollInlineKbs.POLL_PAGE_SIZE
    batch = all_dates[start:end]
    date_buttons: list[tuple[str, str]] = []
    for item in batch:
      mark = InlineText.BET_RECEIPT_MANUAL_SELECT_TG_MARKER_11 if item.isoformat() in selected else ""
      date_buttons.append((f"{mark}{item.day}, {PollInlineKbs._weekday_ru(item)}", f"poll_day:{item.isoformat()}:{page}"))

    if len(date_buttons) <= 2:
      if date_buttons:
        keyboard.row(
          *[InlineKeyboardButton(text=text, callback_data=data) for text, data in date_buttons],
          width=max(1, len(date_buttons)),
        )
    else:
      keyboard.row(
        *[InlineKeyboardButton(text=text, callback_data=data) for text, data in date_buttons[:2]],
        width=2,
      )
      keyboard.row(
        *[InlineKeyboardButton(text=text, callback_data=data) for text, data in date_buttons[2:]],
        width=max(1, len(date_buttons[2:])),
      )

    left_data = f"poll_page:{month.year}-{month.month:02d}:{page - 1}" if start > 0 else "poll_noop"
    right_data = f"poll_page:{month.year}-{month.month:02d}:{page + 1}" if end < len(all_dates) else "poll_noop"
    keyboard.row(
      InlineKeyboardButton(text=InlineText.PAGE_PREVIOUS, callback_data=left_data),
      InlineKeyboardButton(text=InlineText.PAGE_NEXT, callback_data=right_data),
      width=2,
    )
    keyboard.row(
      InlineKeyboardButton(
        text=InlineText.INLINEKBS_POLL_MONTH_TG_TEXT_01,
        callback_data=f"poll_suggest:{month.year}-{month.month:02d}",
      ),
      width=1,
    )
    keyboard.row(
      InlineKeyboardButton(text=InlineText.INLINEKBS_POLL_MONTH_TG_TEXT_02, callback_data="poll_done"),
      InlineKeyboardButton(text=InlineText.INLINEKBS_POLL_MONTH_TG_TEXT_03, callback_data="poll_cancel"),
      width=2,
    )
    return keyboard.as_markup()

  @staticmethod
  def poll_month_vk(
    *,
    month: date,
    page: int = 0,
    selected_dates: list[date] | None = None,
    extra_dates: list[date] | None = None,
  ) -> str:
    selected = {item.isoformat() for item in (selected_dates or [])}
    all_dates = PollInlineKbs._poll_days_for_month(month, extra_dates=extra_dates)
    start = page * PollInlineKbs.POLL_PAGE_SIZE_VK
    end = start + PollInlineKbs.POLL_PAGE_SIZE_VK
    batch = all_dates[start:end]
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    labels: list[dict[str, str | dict[str, int | str]]] = []
    for item in batch:
      mark = InlineText.BET_RECEIPT_MANUAL_SELECT_TG_MARKER_11 if item.isoformat() in selected else ""
      labels.append(
        {
          "action": {
            "type": "callback",
            "label": f"{mark}{item.day}, {PollInlineKbs._weekday_ru(item)}"[:40],
            "payload": {"action": "poll_day", "date": item.isoformat(), "page": page},
          },
          "color": "primary",
        }
      )
    if len(labels) <= 2:
      if labels:
        rows.append(labels)
    else:
      rows.append(labels[:2])
      rows.append(labels[2:])

    rows.append(
      [
        {
          "action": {
            "type": "callback",
            "label": InlineText.PAGE_PREVIOUS,
            "payload": (
              {"action": "poll_page", "month": f"{month.year}-{month.month:02d}", "page": page - 1}
              if start > 0
              else {"action": "poll_noop"}
            ),
          },
          "color": "secondary",
        },
        {
          "action": {
            "type": "callback",
            "label": InlineText.PAGE_NEXT,
            "payload": (
              {"action": "poll_page", "month": f"{month.year}-{month.month:02d}", "page": page + 1}
              if end < len(all_dates)
              else {"action": "poll_noop"}
            ),
          },
          "color": "secondary",
        },
      ]
    )
    rows.append(
      [
        {
          "action": {
            "type": "callback",
            "label": InlineText.INLINEKBS_POLL_MONTH_VK_TEXT_01,
            "payload": {"action": "poll_suggest", "month": f"{month.year}-{month.month:02d}"},
          },
          "color": "secondary",
        },
      ]
    )
    rows.append(
      [
        {
          "action": {"type": "callback", "label": InlineText.INLINEKBS_POLL_MONTH_VK_TEXT_02, "payload": {"action": "poll_done"}},
          "color": "positive",
        },
        {
          "action": {"type": "callback", "label": InlineText.INLINEKBS_POLL_MONTH_VK_TEXT_03, "payload": {"action": "poll_cancel"}},
          "color": "negative",
        },
      ]
    )
    return ReplyKbs.make_vk_callback(rows)

  @staticmethod
  def poll_admin_choose_tg(*, current_month: date, next_month: date) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    keyboard.button(
      text=PollInlineKbs._month_label_ru(current_month),
      callback_data=f"polladmin_month:{current_month.year}-{current_month.month:02d}",
    )
    keyboard.button(
      text=PollInlineKbs._month_label_ru(next_month),
      callback_data=f"polladmin_month:{next_month.year}-{next_month.month:02d}",
    )
    keyboard.button(text=InlineText.INLINEKBS_POLL_ADMIN_CHOOSE_TG_TEXT_01, callback_data="polladmin_cancel")
    keyboard.adjust(1, 1, 1)
    return keyboard.as_markup()

  @staticmethod
  def poll_admin_other_tg(*, months: list[date]) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    for item in months:
      keyboard.button(
        text=PollInlineKbs._month_label_ru(item),
        callback_data=f"polladmin_month:{item.year}-{item.month:02d}",
      )
    keyboard.adjust(1)
    return keyboard.as_markup()

  @staticmethod
  def poll_admin_choose_vk(*, current_month: date, next_month: date) -> str:
    return ReplyKbs.make_vk_callback(
      [
        [
          {
            "action": {
              "type": "callback",
              "label": PollInlineKbs._month_label_ru(current_month),
              "payload": {"action": "polladmin_month", "month": f"{current_month.year}-{current_month.month:02d}"},
            },
            "color": "primary",
          },
        ],
        [
          {
            "action": {
              "type": "callback",
              "label": PollInlineKbs._month_label_ru(next_month),
              "payload": {"action": "polladmin_month", "month": f"{next_month.year}-{next_month.month:02d}"},
            },
            "color": "primary",
          },
        ],
        [
          {
            "action": {"type": "callback", "label": InlineText.INLINEKBS_POLL_ADMIN_CHOOSE_VK_TEXT_01, "payload": {"action": "polladmin_cancel"}},
            "color": "negative",
          },
        ],
      ]
    )

  @staticmethod
  def poll_admin_other_vk(*, months: list[date]) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    for item in months:
      rows.append(
        [
          {
            "action": {
              "type": "callback",
              "label": PollInlineKbs._month_label_ru(item),
              "payload": {"action": "polladmin_month", "month": f"{item.year}-{item.month:02d}"},
            },
            "color": "primary",
          }
        ]
      )
    return ReplyKbs.make_vk_callback(rows)
