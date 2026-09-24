from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.keyboards.keyboards_reply import ReplyKbs
from app.bot.shared.texts.inline.shared import keyboards_inline as InlineText
from app.db.models.user import User

from .inline_base import InlineKeyboardBase

class PokerInlineKbs(InlineKeyboardBase):
  def poker_params_tg(*, params: list) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    for p in params[:20]:
      keyboard.button(
        text=f'{InlineText.BUTTON_LABEL_LINE_404}{p.row_id}',
        callback_data=f"pokerstart:{p.row_id}",
      )
    keyboard.adjust(1)
    return keyboard.as_markup()

  def poker_add_player_candidates_tg(*, users: list[User]) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    for user in users[:20]:
      keyboard.button(
        text=user.name,
        callback_data=f"pokeradd:{user.row_id}",
      )
    keyboard.button(
      text=InlineText.INLINEKBS_POKER_ADD_PLAYER_CANDIDATES_TG_TEXT_01,
      callback_data="pokeraddnew:0",
    )
    keyboard.button(
      text=Buttons.betting_inline.CONFIRM_NO.value,
      callback_data="pokeraddcancel:0",
    )
    keyboard.adjust(1)
    return keyboard.as_markup()

  def poker_cashier_candidates_tg(*, players: list) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    for player in players[:20]:
      keyboard.button(
        text=player.player_name,
        callback_data=f"pokercashier:{player.player_id}",
      )
    keyboard.adjust(1)
    return keyboard.as_markup()

  def poker_room_admin_status_tg(*, players: list, can_start_betting: bool = False) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    for player in players[:20]:
      keyboard.button(
        text=player.player_name[:40],
        callback_data=f"pokerroommanage:{int(player.player_id)}",
      )
    if can_start_betting:
      keyboard.button(
        text=Buttons.admin_room.START_BETTING.value,
        callback_data="pokerstartbetting:inline",
      )
    keyboard.adjust(1)
    return keyboard.as_markup()

  def poker_room_manage_player_tg(*, player_id: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    keyboard.button(
      text=InlineText.INLINEKBS_POKER_ROOM_MANAGE_PLAYER_TG_TEXT_01,
      callback_data=f"pokerremove:{int(player_id)}",
    )
    keyboard.button(
      text=InlineText.INLINEKBS_POKER_ROOM_MANAGE_PLAYER_TG_TEXT_02,
      callback_data=f"pokerroomcashier:{int(player_id)}",
    )
    keyboard.adjust(1)
    return keyboard.as_markup()

  def poker_room_approve_tg(*, player_id: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    keyboard.button(
      text=InlineText.INLINEKBS_POKER_ROOM_APPROVE_TG_TEXT_01,
      callback_data=f"pokerroomapprove:{int(player_id)}",
    )
    keyboard.button(
      text=InlineText.INLINEKBS_POKER_ROOM_APPROVE_TG_TEXT_02,
      callback_data=f"pokerroomreject:{int(player_id)}",
    )
    keyboard.adjust(1)
    return keyboard.as_markup()

  def poker_remove_player_candidates_tg(*, players: list) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    for player in players[:20]:
      keyboard.button(
        text=f'{player.player_name}{InlineText.BUTTON_LABEL_LINE_489}{int(player.buyins)}',
        callback_data=f"pokerremove:{player.player_id}",
      )
    keyboard.adjust(1)
    return keyboard.as_markup()

  def poker_unban_player_candidates_tg(*, players: list) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    for player in players[:20]:
      keyboard.button(
        text=player["name"][:64],
        callback_data=f"pokerunban:{player['player_id']}",
      )
    keyboard.adjust(1)
    return keyboard.as_markup()

  def poker_buyin_candidates_tg(
    *,
    players: list,
    show_buyins: bool = False,
    callback_prefix: str = "pokerbuyin",
  ) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    for player in players[:20]:
      label = f"{player.player_name}: {int(player.buyins)}" if show_buyins else f"{player.player_name}"
      keyboard.button(
        text=label,
        callback_data=f"{callback_prefix}:{player.player_id}",
      )
    keyboard.button(
      text=Buttons.betting_inline.CONFIRM_NO.value,
      callback_data="pokerbuyincancel:0",
    )
    keyboard.adjust(1)
    return keyboard.as_markup()

  def poker_buyin_count_tg(
    *,
    player_id: int,
    max_buyins: int,
    big_buyin: int | None,
    king_buyin: int | None,
    super_buyin: int | None,
    big_buyin_pic: str | None,
    king_buyin_pic: str | None,
    super_buyin_pic: str | None,
    include_king_buyin: bool,
    current_big_buyin_count: int = 0,
    current_super_buyin_count: int = 0,
  ) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    safe_max = max(1, int(max_buyins))
    for count in range(1, safe_max + 1):
      keyboard.button(
        text=f"{count}",
        callback_data=f"pokerbuyincount:{player_id}:{count}",
      )
    if safe_max == 2:
      special_values: list[tuple[int, str]] = []
      allow_big = int(current_big_buyin_count) < 2 and int(current_super_buyin_count) == 0
      allow_super = int(current_big_buyin_count) == 0 and int(current_super_buyin_count) == 0
      allow_king = include_king_buyin and int(current_big_buyin_count) == 0 and int(current_super_buyin_count) == 0
      if allow_big and big_buyin is not None and int(big_buyin) > safe_max:
        special_values.append((int(big_buyin), str(big_buyin_pic or InlineText.POKER_BUYIN_COUNT_TG_MARKER_01)))
      if allow_super and super_buyin is not None and int(super_buyin) > safe_max:
        special_values.append((int(super_buyin), str(super_buyin_pic or InlineText.POKER_BUYIN_COUNT_TG_MARKER_02)))
      if allow_king and king_buyin is not None and int(king_buyin) > safe_max:
        special_values.append((int(king_buyin), str(king_buyin_pic or InlineText.POKER_BUYIN_COUNT_TG_MARKER_03)))
      # Keep distinct values and stable visual order by amount.
      unique_special_values: list[tuple[int, str]] = []
      seen: set[int] = set()
      for amount, icon in sorted(special_values, key=lambda x: x[0]):
        if amount in seen:
          continue
        seen.add(amount)
        unique_special_values.append((amount, icon))
      for amount, icon in unique_special_values:
        keyboard.button(
          text=f"{icon} {amount}",
          callback_data=f"pokerbuyincount:{player_id}:{amount}",
        )
    keyboard.button(
      text=Buttons.betting_inline.CONFIRM_NO.value,
      callback_data=f"pokerbuyincancel:{player_id}",
    )
    keyboard.adjust(*([1] * (safe_max + (len(unique_special_values) if safe_max == 2 else 0) + 1)))
    return keyboard.as_markup()

  def poker_buyin_correct_confirm_tg(*, player_id: int, new_buyins: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    keyboard.button(
      text=Buttons.betting_inline.CONFIRM_YES.value,
      callback_data=f"pokerbuyincorrectconfirm:yes:{int(player_id)}:{int(new_buyins)}",
    )
    keyboard.button(
      text=Buttons.betting_inline.CONFIRM_NO.value,
      callback_data=f"pokerbuyincorrectconfirm:no:{int(player_id)}:{int(new_buyins)}",
    )
    keyboard.adjust(2)
    return keyboard.as_markup()

  def poker_cashout_candidates_tg(*, players: list) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    for player in players[:20]:
      keyboard.button(
        text=player.player_name,
        callback_data=f"pokercashout:{player.player_id}",
      )
    keyboard.adjust(1)
    return keyboard.as_markup()

  def poker_params_vk(*, params: list) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    for p in params[:10]:
      rows.append(
        [
          {
            "action": {
              "type": "callback",
              "label": f"ID {p.row_id}"[:40],
              "payload": {
                "action": "poker_start_param",
                "params_id": p.row_id,
              },
            },
            "color": "primary",
          }
        ]
      )
    return ReplyKbs.make_vk_callback(rows)

  def poker_add_player_candidates_vk(*, users: list[User]) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    for user in users[:10]:
      rows.append(
        [
          {
            "action": {
              "type": "callback",
              "label": user.name[:40],
              "payload": {
                "action": "poker_add_player_select",
                "row_id": user.row_id,
              },
            },
            "color": "primary",
          }
        ]
      )
    rows.append(
      [
        {
          "action": {
            "type": "callback",
            "label": InlineText.INLINEKBS_POKER_ADD_PLAYER_CANDIDATES_VK_TEXT_01,
            "payload": {
              "action": "poker_add_player_new",
            },
          },
          "color": "primary",
        }
      ]
    )
    rows.append(
      [
        {
          "action": {
            "type": "callback",
            "label": Buttons.betting_inline.CONFIRM_NO.value[:40],
            "payload": {
              "action": "poker_add_player_cancel",
            },
          },
          "color": "negative",
        }
      ]
    )
    return ReplyKbs.make_vk_callback(rows)

  def poker_cashier_candidates_vk(*, players: list) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    for player in players[:10]:
      rows.append(
        [
          {
            "action": {
              "type": "callback",
              "label": player.player_name[:40],
              "payload": {
                "action": "poker_set_cashier_select",
                "player_id": int(player.player_id),
              },
            },
            "color": "primary",
          }
        ]
      )
    return ReplyKbs.make_vk_callback(rows)

  def poker_room_admin_status_vk(*, players: list, can_start_betting: bool = False) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    for player in players[:10]:
      rows.append(
        [
          {
            "action": {
              "type": "callback",
              "label": player.player_name[:40],
              "payload": {
                "action": "poker_room_manage_select",
                "player_id": int(player.player_id),
              },
            },
            "color": "primary",
          }
        ]
      )
    if can_start_betting:
      rows.append(
        [
          {
            "action": {
              "type": "callback",
              "label": Buttons.admin_room.START_BETTING.value[:40],
              "payload": {
                "action": "poker_start_betting_inline",
              },
            },
            "color": "positive",
          }
        ]
      )
    return ReplyKbs.make_vk_callback(rows)

  def poker_room_manage_player_vk(*, player_id: int) -> str:
    rows = [
      [
        {
          "action": {
            "type": "callback",
            "label": InlineText.INLINEKBS_POKER_ROOM_MANAGE_PLAYER_VK_TEXT_01,
            "payload": {"action": "poker_remove_player_select", "player_id": int(player_id)},
          },
          "color": "negative",
        }
      ],
      [
        {
          "action": {
            "type": "callback",
            "label": InlineText.INLINEKBS_POKER_ROOM_MANAGE_PLAYER_VK_TEXT_02,
            "payload": {"action": "poker_room_set_cashier_select", "player_id": int(player_id)},
          },
          "color": "primary",
        }
      ],
    ]
    return ReplyKbs.make_vk_callback(rows)

  def poker_room_approve_vk(*, player_id: int) -> str:
    rows = [
      [
        {
          "action": {
            "type": "callback",
            "label": InlineText.INLINEKBS_POKER_ROOM_APPROVE_VK_TEXT_01,
            "payload": {"action": "poker_room_approve_select", "player_id": int(player_id)},
          },
          "color": "positive",
        },
        {
          "action": {
            "type": "callback",
            "label": InlineText.INLINEKBS_POKER_ROOM_APPROVE_VK_TEXT_02,
            "payload": {"action": "poker_room_reject_select", "player_id": int(player_id)},
          },
          "color": "negative",
        },
      ]
    ]
    return ReplyKbs.make_vk_callback(rows)

  def poker_remove_player_candidates_vk(*, players: list) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    for player in players[:10]:
      rows.append(
        [
          {
            "action": {
              "type": "callback",
              "label": f"{player.player_name}: {int(player.buyins)}"[:40],
              "payload": {
                "action": "poker_remove_player_select",
                "player_id": int(player.player_id),
              },
            },
            "color": "negative",
          }
        ]
      )
    return ReplyKbs.make_vk_callback(rows)

  def poker_unban_player_candidates_vk(*, players: list) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    for player in players[:10]:
      rows.append(
        [
          {
            "action": {
              "type": "callback",
              "label": str(player["name"])[:40],
              "payload": {
                "action": "poker_unban_player_select",
                "player_id": int(player["player_id"]),
              },
            },
            "color": "positive",
          }
        ]
      )
    return ReplyKbs.make_vk_callback(rows)

  def poker_buyin_candidates_vk(
    *,
    players: list,
    show_buyins: bool = False,
    action: str = "poker_buyin_select",
  ) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    for player in players[:10]:
      label = f"{player.player_name}: {int(player.buyins)}" if show_buyins else f"{player.player_name}"
      rows.append(
        [
          {
            "action": {
              "type": "callback",
              "label": label[:40],
              "payload": {
                "action": action,
                "player_id": int(player.player_id),
              },
            },
            "color": "primary",
          }
        ]
      )
    rows.append(
      [
        {
          "action": {
            "type": "callback",
            "label": Buttons.betting_inline.CONFIRM_NO.value[:40],
            "payload": {
              "action": "poker_buyin_cancel",
              "player_id": 0,
            },
          },
          "color": "negative",
        }
      ]
    )
    return ReplyKbs.make_vk_callback(rows)

  def poker_buyin_correct_confirm_vk(*, player_id: int, new_buyins: int) -> str:
    rows = [
      [
        {
          "action": {
            "type": "callback",
            "label": Buttons.betting_inline.CONFIRM_YES.value[:40],
            "payload": {
              "action": "poker_buyin_correct_confirm_yes",
              "player_id": int(player_id),
              "new_buyins": int(new_buyins),
            },
          },
          "color": "positive",
        },
        {
          "action": {
            "type": "callback",
            "label": Buttons.betting_inline.CONFIRM_NO.value[:40],
            "payload": {
              "action": "poker_buyin_correct_confirm_no",
              "player_id": int(player_id),
              "new_buyins": int(new_buyins),
            },
          },
          "color": "negative",
        },
      ]
    ]
    return ReplyKbs.make_vk_callback(rows)

  def poker_buyin_count_vk(
    *,
    player_id: int,
    max_buyins: int,
    big_buyin: int | None,
    king_buyin: int | None,
    super_buyin: int | None,
    big_buyin_pic: str | None,
    king_buyin_pic: str | None,
    super_buyin_pic: str | None,
    include_king_buyin: bool,
    current_big_buyin_count: int = 0,
    current_super_buyin_count: int = 0,
  ) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    safe_max = max(1, int(max_buyins))
    for count in range(1, safe_max + 1):
      rows.append(
        [
          {
            "action": {
              "type": "callback",
              "label": str(count),
              "payload": {
                "action": "poker_buyin_count_select",
                "player_id": int(player_id),
                "count": count,
              },
            },
            "color": "primary",
          }
        ]
      )
    if safe_max == 2:
      special_values: list[tuple[int, str]] = []
      allow_big = int(current_big_buyin_count) < 2 and int(current_super_buyin_count) == 0
      allow_super = int(current_big_buyin_count) == 0 and int(current_super_buyin_count) == 0
      allow_king = include_king_buyin and int(current_big_buyin_count) == 0 and int(current_super_buyin_count) == 0
      if allow_big and big_buyin is not None and int(big_buyin) > safe_max:
        special_values.append((int(big_buyin), str(big_buyin_pic or InlineText.POKER_BUYIN_COUNT_TG_MARKER_01)))
      if allow_super and super_buyin is not None and int(super_buyin) > safe_max:
        special_values.append((int(super_buyin), str(super_buyin_pic or InlineText.POKER_BUYIN_COUNT_TG_MARKER_02)))
      if allow_king and king_buyin is not None and int(king_buyin) > safe_max:
        special_values.append((int(king_buyin), str(king_buyin_pic or InlineText.POKER_BUYIN_COUNT_TG_MARKER_03)))
      unique_special_values: list[tuple[int, str]] = []
      seen: set[int] = set()
      for amount, icon in sorted(special_values, key=lambda x: x[0]):
        if amount in seen:
          continue
        seen.add(amount)
        unique_special_values.append((amount, icon))
      for amount, icon in unique_special_values:
        rows.append(
          [
            {
              "action": {
                "type": "callback",
                "label": f"{icon} {amount}"[:40],
                "payload": {
                  "action": "poker_buyin_count_select",
                  "player_id": int(player_id),
                  "count": amount,
                },
              },
              "color": "primary",
            }
          ]
        )
    rows.append(
      [
        {
          "action": {
            "type": "callback",
            "label": Buttons.betting_inline.CONFIRM_NO.value[:40],
            "payload": {
              "action": "poker_buyin_cancel",
              "player_id": int(player_id),
            },
          },
          "color": "negative",
        }
      ]
    )
    return ReplyKbs.make_vk_callback(rows)

  def poker_cashout_candidates_vk(*, players: list) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    for player in players[:10]:
      rows.append(
        [
          {
            "action": {
              "type": "callback",
              "label": player.player_name[:40],
              "payload": {
                "action": "poker_cashout_select",
                "player_id": int(player.player_id),
              },
            },
            "color": "primary",
          }
        ]
      )
    return ReplyKbs.make_vk_callback(rows)

  def poker_calc_tg() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    keyboard.button(
      text=Buttons.admin_room.CALCULATE_POKER.value,
      callback_data="pokercalc:run",
    )
    keyboard.adjust(1)
    return keyboard.as_markup()

  def poker_calc_vk() -> str:
    return ReplyKbs.make_vk_callback(
      [
        [
          {
            "action": {
              "type": "callback",
              "label": Buttons.admin_room.CALCULATE_POKER.value,
              "payload": {"action": "poker_calc_run"},
            },
            "color": "positive",
          }
        ]
      ]
    )
