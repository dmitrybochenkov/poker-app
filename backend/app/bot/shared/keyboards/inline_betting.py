from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.keyboards.keyboards_reply import ReplyKbs
from app.bot.shared.texts.inline.shared import keyboards_inline as InlineText

from .inline_base import InlineKeyboardBase

class BettingInlineKbs(InlineKeyboardBase):
  @staticmethod
  def betting_tournament_tg() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    keyboard.button(
      text=Buttons.betting_inline.REGULAR_TOUR.value,
      callback_data="bet_tournament:regular",
    )
    keyboard.button(
      text=Buttons.betting_inline.YEAR_TOUR.value,
      callback_data="bet_tournament:year",
    )
    keyboard.adjust(1)
    return keyboard.as_markup()

  @staticmethod
  def betting_size_tg(*, small_size_kopecks: int, big_size_kopecks: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    keyboard.button(
      text=f'{InlineText.BUTTON_LABEL_LINE_173}{small_size_kopecks // 100}{InlineText.BUTTON_LABEL_LINE_173_2}',
      callback_data=f"bet_size:{small_size_kopecks}",
    )
    keyboard.button(
      text=f'{InlineText.BUTTON_LABEL_LINE_177}{big_size_kopecks // 100}{InlineText.BUTTON_LABEL_LINE_177_4}',
      callback_data=f"bet_size:{big_size_kopecks}",
    )
    keyboard.adjust(1)
    return keyboard.as_markup()

  @staticmethod
  def betting_player_tg(
    *,
    action: str,
    players: list[str],
    player_marks: dict[str, str] | None = None,
  ) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    for player in players:
      mark = ""
      if player_marks:
        mark = player_marks.get(player, "")
      keyboard.button(text=f"{player}{mark}", callback_data=f"bet_{action}:{player}")
    keyboard.adjust(1)
    return keyboard.as_markup()

  @staticmethod
  def betting_confirm_tg() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text=Buttons.betting_inline.CONFIRM_YES.value, callback_data="bet_confirm:yes")
    keyboard.button(text=Buttons.betting_inline.CONFIRM_NO.value, callback_data="bet_confirm:no")
    keyboard.adjust(1)
    return keyboard.as_markup()

  @staticmethod
  def betting_tournament_vk() -> str:
    return ReplyKbs.make_vk_callback(
      [
        [
          {
            "action": {
              "type": "callback",
              "label": Buttons.betting_inline.REGULAR_TOUR.value,
              "payload": {"action": "bet_tournament_regular"},
            },
            "color": "primary",
          }
        ],
        [
          {
            "action": {
              "type": "callback",
              "label": Buttons.betting_inline.YEAR_TOUR.value,
              "payload": {"action": "bet_tournament_year"},
            },
            "color": "primary",
          }
        ],
      ]
    )

  @staticmethod
  def betting_size_vk(*, small_size_kopecks: int, big_size_kopecks: int) -> str:
    return ReplyKbs.make_vk_callback(
      [
        [{
          "action": {"type": "callback", "label": f'{InlineText.BUTTON_LABEL_LINE_173}{small_size_kopecks // 100}{InlineText.BUTTON_LABEL_LINE_177_4}', "payload": {"action": "bet_size", "amount_kopecks": small_size_kopecks}},
          "color": "primary",
        }],
        [{
          "action": {"type": "callback", "label": f'{InlineText.BUTTON_LABEL_LINE_177}{big_size_kopecks // 100}{InlineText.BUTTON_LABEL_LINE_177_4}', "payload": {"action": "bet_size", "amount_kopecks": big_size_kopecks}},
          "color": "primary",
        }],
      ]
    )

  @staticmethod
  def betting_player_vk(
    *,
    action: str,
    players: list[str],
    player_marks: dict[str, str] | None = None,
  ) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    for player in players:
      mark = ""
      if player_marks:
        mark = player_marks.get(player, "")
      label = f"{player}{mark}"[:40]
      rows.append([{
        "action": {"type": "callback", "label": label, "payload": {"action": f"bet_{action}", "player_name": player}},
        "color": "primary",
      }])
    return ReplyKbs.make_vk_callback(rows)

  @staticmethod
  def betting_confirm_vk() -> str:
    return ReplyKbs.make_vk_callback(
      [
        [{
          "action": {"type": "callback", "label": Buttons.betting_inline.CONFIRM_YES.value, "payload": {"action": "bet_confirm_yes"}},
          "color": "positive",
        }],
        [{
          "action": {"type": "callback", "label": Buttons.betting_inline.CONFIRM_NO.value, "payload": {"action": "bet_confirm_no"}},
          "color": "negative",
        }],
      ]
    )

  @staticmethod
  def bet_receipt_manual_tg(
    *,
    receipt_row_id: int,
    bets: list | None = None,
    selected_ids: list[int] | None = None,
    page: int = 0,
  ) -> InlineKeyboardMarkup:
    return BettingInlineKbs.bet_receipt_manual_select_tg(
      receipt_row_id=receipt_row_id,
      bets=bets or [],
      selected_ids=selected_ids or [],
      page=page,
    )

  @staticmethod
  def bet_receipt_manual_select_tg(
    *,
    receipt_row_id: int,
    bets: list,
    selected_ids: list[int] | None = None,
    page: int = 0,
  ) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    selected = set(selected_ids or [])
    start = page * BettingInlineKbs.STAT_PAGE_SIZE
    end = start + BettingInlineKbs.STAT_PAGE_SIZE
    batch = bets[start:end]
    for bet in batch:
      mark = InlineText.BET_RECEIPT_MANUAL_SELECT_TG_MARKER_11 if int(bet.row_id) in selected else ""
      d = bet.date.strftime("%d.%m.%Y") if bet.date else InlineText.BET_RECEIPT_MANUAL_SELECT_TG_MARKER_12
      amount_rub = BettingInlineKbs._format_rub_from_kopecks(int(bet.amount_kopecks))
      keyboard.button(
        text=f'{mark}{d}{InlineText.BET_RECEIPT_MANUAL_SELECT_TG_MARKER_13_PART_3}{amount_rub}{InlineText.BUTTON_LABEL_LINE_177_4}'[:64],
        callback_data=f"betreceipt:toggle:{int(receipt_row_id)}:{int(bet.row_id)}:{page}",
      )
    if page > 0:
      keyboard.button(text=InlineText.PAGE_PREVIOUS, callback_data=f"betreceipt:page:{int(receipt_row_id)}:{page - 1}")
    if end < len(bets):
      keyboard.button(text=InlineText.PAGE_NEXT, callback_data=f"betreceipt:page:{int(receipt_row_id)}:{page + 1}")
    keyboard.button(text=InlineText.INLINEKBS_BET_RECEIPT_MANUAL_SELECT_TG_TEXT_01, callback_data=f"betreceipt:done:{int(receipt_row_id)}")
    keyboard.button(text=InlineText.INLINEKBS_BET_RECEIPT_MANUAL_SELECT_TG_TEXT_02, callback_data=f"betreceipt:cancel:{int(receipt_row_id)}")
    sizes = [2, 2][: (len(batch) + 1) // 2]
    nav_count = int(page > 0) + int(end < len(bets))
    if nav_count:
      sizes.append(nav_count)
    sizes.append(2)
    keyboard.adjust(*sizes)
    return keyboard.as_markup()

  @staticmethod
  def bet_receipt_manual_vk(
    *,
    receipt_row_id: int,
    bets: list | None = None,
    selected_ids: list[int] | None = None,
    page: int = 0,
  ) -> str:
    return BettingInlineKbs.bet_receipt_manual_select_vk(
      receipt_row_id=receipt_row_id,
      bets=bets or [],
      selected_ids=selected_ids or [],
      page=page,
    )

  @staticmethod
  def bet_receipt_manual_select_vk(
    *,
    receipt_row_id: int,
    bets: list,
    selected_ids: list[int] | None = None,
    page: int = 0,
  ) -> str:
    selected = set(selected_ids or [])
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    start = page * BettingInlineKbs.STAT_PAGE_SIZE
    end = start + BettingInlineKbs.STAT_PAGE_SIZE
    batch = bets[start:end]
    pair_row: list[dict[str, str | dict[str, int | str]]] = []
    for bet in batch:
      mark = InlineText.BET_RECEIPT_MANUAL_SELECT_TG_MARKER_11 if int(bet.row_id) in selected else ""
      d = bet.date.strftime("%d.%m.%Y") if bet.date else InlineText.BET_RECEIPT_MANUAL_SELECT_TG_MARKER_12
      amount_rub = BettingInlineKbs._format_rub_from_kopecks(int(bet.amount_kopecks))
      pair_row.append(
        {
          "action": {
            "type": "callback",
            "label": f'{mark}{d}{InlineText.BET_RECEIPT_MANUAL_SELECT_TG_MARKER_13_PART_3}{amount_rub}{InlineText.BUTTON_LABEL_LINE_177_4}'[:40],
            "payload": {
              "action": "bet_receipt_toggle",
              "receipt_row_id": int(receipt_row_id),
              "bet_row_id": int(bet.row_id),
              "page": int(page),
            },
          },
          "color": "primary",
        }
      )
      if len(pair_row) == 2:
        rows.append(pair_row)
        pair_row = []
    if pair_row:
      rows.append(pair_row)
    nav_row: list[dict[str, str | dict[str, int | str]]] = []
    if page > 0:
      nav_row.append(
        {
          "action": {
            "type": "callback",
            "label": InlineText.PAGE_PREVIOUS,
            "payload": {"action": "bet_receipt_page", "receipt_row_id": int(receipt_row_id), "page": int(page - 1)},
          },
          "color": "secondary",
        }
      )
    if end < len(bets):
      nav_row.append(
        {
          "action": {
            "type": "callback",
            "label": InlineText.PAGE_NEXT,
            "payload": {"action": "bet_receipt_page", "receipt_row_id": int(receipt_row_id), "page": int(page + 1)},
          },
          "color": "secondary",
        }
      )
    if nav_row:
      rows.append(nav_row)
    rows.append(
      [
        {
          "action": {
            "type": "callback",
            "label": InlineText.INLINEKBS_BET_RECEIPT_MANUAL_SELECT_VK_TEXT_01,
            "payload": {"action": "bet_receipt_done", "receipt_row_id": int(receipt_row_id)},
          },
          "color": "positive",
        },
        {
          "action": {
            "type": "callback",
            "label": InlineText.INLINEKBS_BET_RECEIPT_MANUAL_SELECT_VK_TEXT_02,
            "payload": {"action": "bet_receipt_cancel", "receipt_row_id": int(receipt_row_id)},
          },
          "color": "negative",
        },
      ]
    )
    return ReplyKbs.make_vk_callback(
      rows
    )
