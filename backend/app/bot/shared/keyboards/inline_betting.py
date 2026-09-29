from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.keyboards.keyboards_reply import ReplyKbs
from app.bot.shared.texts.inline.shared import keyboards_inline as InlineText

from .inline_base import InlineKeyboardBase


class BettingInlineKbs(InlineKeyboardBase):
  @staticmethod
  def tournament_close_tg(*, tournaments: list) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    for item in tournaments:
      keyboard.button(text=f"{item.tournament_type} {item.start_date:%m.%Y}–{item.end_date:%m.%Y}", callback_data=f"tourclose:preview:{item.row_id}")
    keyboard.button(text="Отмена", callback_data="tourclose:cancel")
    keyboard.adjust(1)
    return keyboard.as_markup()

  @staticmethod
  def tournament_confirm_tg(*, tournament_id: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Подтвердить", callback_data=f"tourclose:confirm:{tournament_id}")
    keyboard.button(text="Отмена", callback_data="tourclose:cancel")
    keyboard.adjust(2)
    return keyboard.as_markup()

  @staticmethod
  def tournament_close_vk(*, tournaments: list) -> str:
    rows = [[{"action": {"type": "callback", "label": f"{item.tournament_type} {item.start_date:%m.%Y}–{item.end_date:%m.%Y}"[:40], "payload": {"action": "tour_close_preview", "tournament_id": int(item.row_id)}}, "color": "primary"}] for item in tournaments]
    rows.append([{"action": {"type": "callback", "label": "Отмена", "payload": {"action": "tour_close_cancel"}}, "color": "negative"}])
    return ReplyKbs.make_vk_callback(rows)

  @staticmethod
  def tournament_confirm_vk(*, tournament_id: int) -> str:
    return ReplyKbs.make_vk_callback([[
      {"action": {"type": "callback", "label": "Подтвердить", "payload": {"action": "tour_close_confirm", "tournament_id": tournament_id}}, "color": "positive"},
      {"action": {"type": "callback", "label": "Отмена", "payload": {"action": "tour_close_cancel"}}, "color": "negative"},
    ]])
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
    players: list,
    player_marks: dict[str, str] | None = None,
  ) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    for player in players:
      player_id = int(player["player_id"] if isinstance(player, dict) else player.player_id)
      player_name = str(
        player["player_name"] if isinstance(player, dict) else player.player_name
      )
      mark = ""
      if player_marks:
        mark = player_marks.get(player_name, "")
      keyboard.button(
        text=f"{player_name}{mark}", callback_data=f"bet_{action}:{player_id}"
      )
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
    players: list,
    player_marks: dict[str, str] | None = None,
  ) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    for player in players:
      player_id = int(player["player_id"] if isinstance(player, dict) else player.player_id)
      player_name = str(
        player["player_name"] if isinstance(player, dict) else player.player_name
      )
      mark = ""
      if player_marks:
        mark = player_marks.get(player_name, "")
      label = f"{player_name}{mark}"[:40]
      rows.append([{
        "action": {"type": "callback", "label": label, "payload": {"action": f"bet_{action}", "player_id": player_id}},
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
  def bet_payment_choice_tg(*, total_rub: str) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text=f"💳 Оплатить всё — {total_rub} ₽", callback_data="betpay:all")
    keyboard.button(text="🎯 Выбрать ставки", callback_data="betpay:select")
    keyboard.button(text="Отмена", callback_data="betpay:cancel")
    keyboard.adjust(1)
    return keyboard.as_markup()

  @staticmethod
  def bet_payment_select_tg(*, bets: list, selected_ids: list[int]) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    selected = set(selected_ids)
    for bet in bets:
      mark = "✅ " if int(bet.row_id) in selected else ""
      day = bet.date.strftime("%d.%m.%Y") if bet.date else "—"
      amount = BettingInlineKbs._format_rub_from_kopecks(int(bet.amount_kopecks))
      keyboard.button(text=f"{mark}{day} — {amount} ₽", callback_data=f"betpay:toggle:{int(bet.row_id)}")
    keyboard.button(text="Готово", callback_data="betpay:done")
    keyboard.button(text="Отмена", callback_data="betpay:cancel")
    keyboard.adjust(1)
    return keyboard.as_markup()

  @staticmethod
  def bet_payment_choice_vk(*, total_rub: str) -> str:
    return ReplyKbs.make_vk_callback([
      [{"action": {"type": "callback", "label": f"💳 Оплатить всё — {total_rub} ₽", "payload": {"action": "bet_pay_all"}}, "color": "positive"}],
      [{"action": {"type": "callback", "label": "🎯 Выбрать ставки", "payload": {"action": "bet_pay_select"}}, "color": "primary"}],
      [{"action": {"type": "callback", "label": "Отмена", "payload": {"action": "bet_pay_cancel"}}, "color": "negative"}],
    ])

  @staticmethod
  def bet_payment_select_vk(*, bets: list, selected_ids: list[int]) -> str:
    selected = set(selected_ids)
    rows = []
    for bet in bets:
      mark = "✅ " if int(bet.row_id) in selected else ""
      day = bet.date.strftime("%d.%m.%Y") if bet.date else "—"
      amount = BettingInlineKbs._format_rub_from_kopecks(int(bet.amount_kopecks))
      rows.append([{"action": {"type": "callback", "label": f"{mark}{day} — {amount} ₽"[:40], "payload": {"action": "bet_pay_toggle", "bet_row_id": int(bet.row_id)}}, "color": "primary"}])
    rows.extend([
      [{"action": {"type": "callback", "label": "Готово", "payload": {"action": "bet_pay_done"}}, "color": "positive"}],
      [{"action": {"type": "callback", "label": "Отмена", "payload": {"action": "bet_pay_cancel"}}, "color": "negative"}],
    ])
    return ReplyKbs.make_vk_callback(rows)

  @staticmethod
  def bet_receipt_review_tg(*, receipt_row_id: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Подтвердить", callback_data=f"betreceipt:confirm:{receipt_row_id}")
    keyboard.button(text="Изменить", callback_data=f"betreceipt:change:{receipt_row_id}")
    keyboard.button(text="Отклонить", callback_data=f"betreceipt:reject:{receipt_row_id}")
    keyboard.adjust(2, 1)
    return keyboard.as_markup()

  @staticmethod
  def bet_receipt_review_vk(*, receipt_row_id: int) -> str:
    return ReplyKbs.make_vk_callback([[
      {"action": {"type": "callback", "label": "Подтвердить", "payload": {"action": "bet_receipt_confirm", "receipt_row_id": receipt_row_id}}, "color": "positive"},
      {"action": {"type": "callback", "label": "Изменить", "payload": {"action": "bet_receipt_change", "receipt_row_id": receipt_row_id}}, "color": "primary"},
    ], [{"action": {"type": "callback", "label": "Отклонить", "payload": {"action": "bet_receipt_reject", "receipt_row_id": receipt_row_id}}, "color": "negative"}]])

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
