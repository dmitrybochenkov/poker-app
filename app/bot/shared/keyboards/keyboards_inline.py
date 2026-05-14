import calendar
from datetime import date

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.keyboards.keyboards_reply import ReplyKbs
from app.bot.shared.texts.texts import Text
from app.db.models.user import User


class InlineKbs:
  PAGE_SIZE = 5
  STAT_PAGE_SIZE = 4
  POLL_PAGE_SIZE = 6
  POLL_PAGE_SIZE_VK = 6

  @staticmethod
  def _weekday_ru(value: date) -> str:
    names = [
      "понедельник",
      "вторник",
      "среда",
      "четверг",
      "пятница",
      "суббота",
      "воскресенье",
    ]
    return names[value.weekday()]

  @staticmethod
  def _format_rub_from_kopecks(value_kopecks: int) -> str:
    rub = int(value_kopecks) // 100
    kop = int(value_kopecks) % 100
    if kop == 0:
      return str(rub)
    return f"{rub}.{kop:02d}"

  @staticmethod
  def played_before_tg() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    keyboard.button(
      text=Buttons.registration_inline.YES.value,
      callback_data="registration_played_before:yes",
    )
    keyboard.button(
      text=Buttons.registration_inline.NO.value,
      callback_data="registration_played_before:no",
    )
    keyboard.adjust(1)
    return keyboard.as_markup()

  @staticmethod
  def played_before_vk() -> str:
    return ReplyKbs.make_vk_callback(
      [
        [
          {
            "action": {
              "type": "callback",
              "label": Buttons.registration_inline.YES.value,
              "payload": {"action": "registration_played_before_yes"},
            },
            "color": "primary",
          }
        ],
        [
          {
            "action": {
              "type": "callback",
              "label": Buttons.registration_inline.NO.value,
              "payload": {"action": "registration_played_before_no"},
            },
            "color": "primary",
          }
        ],
      ]
    )

  @staticmethod
  def registration_optional_details_tg() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    keyboard.button(
      text=Buttons.registration_inline.OPTIONAL_BANK.value,
      callback_data="registration_optional:bank",
    )
    keyboard.button(
      text=Buttons.registration_inline.OPTIONAL_PHONE.value,
      callback_data="registration_optional:phone",
    )
    keyboard.button(
      text=Buttons.registration_inline.OPTIONAL_SKIP.value,
      callback_data="registration_optional:skip",
    )
    keyboard.adjust(1)
    return keyboard.as_markup()

  @staticmethod
  def registration_platform_tg() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    keyboard.button(
      text=Buttons.registration_inline.PLATFORM_TG.value,
      callback_data="registration_platform:tg",
    )
    keyboard.button(
      text=Buttons.registration_inline.PLATFORM_VK.value,
      callback_data="registration_platform:vk",
    )
    keyboard.adjust(1)
    return keyboard.as_markup()

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
      text=f"🐤 {small_size_kopecks // 100} ₽",
      callback_data=f"bet_size:{small_size_kopecks}",
    )
    keyboard.button(
      text=f"🐔 {big_size_kopecks // 100} ₽",
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
  def registration_review_tg(*, row_id: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    keyboard.add(
      InlineKeyboardButton(
        text=Buttons.admin_inline.APPROVE.value,
        callback_data=f"approve:{row_id}",
      ),
      InlineKeyboardButton(
        text=Buttons.admin_inline.CORRECT.value,
        callback_data=f"correct:{row_id}",
      ),
      InlineKeyboardButton(
        text=Buttons.admin_inline.REJECT.value,
        callback_data=f"reject:{row_id}",
      ),
      InlineKeyboardButton(
        text=Buttons.admin_inline.LINK.value,
        callback_data=f"link:{row_id}",
      ),
    )
    keyboard.adjust(1)
    return keyboard.as_markup()

  @staticmethod
  def registration_link_review_tg(*, row_id: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    keyboard.add(
      InlineKeyboardButton(
        text=Buttons.admin_inline.APPROVE.value,
        callback_data=f"approve:{row_id}",
      ),
      InlineKeyboardButton(
        text=Buttons.admin_inline.REJECT.value,
        callback_data=f"reject:{row_id}",
      ),
      InlineKeyboardButton(
        text=Buttons.admin_inline.LINK.value,
        callback_data=f"link:{row_id}",
      ),
    )
    keyboard.adjust(1)
    return keyboard.as_markup()

  @staticmethod
  def registration_review_vk(*, row_id: int) -> str:
    return ReplyKbs.make_vk_callback(
      [
        [
          {
            "action": {
              "type": "callback",
              "label": Buttons.admin_inline.APPROVE.value,
              "payload": {
                "action": "approve",
                "row_id": row_id,
              },
            },
            "color": "positive",
          }
        ],
        [
          {
            "action": {
              "type": "callback",
              "label": Buttons.admin_inline.REJECT.value,
              "payload": {
                "action": "reject",
                "row_id": row_id,
              },
            },
            "color": "negative",
          }
        ],
        [
          {
            "action": {
              "type": "callback",
              "label": Buttons.admin_inline.CORRECT.value,
              "payload": {
                "action": "correct",
                "row_id": row_id,
              },
            },
            "color": "secondary",
          }
        ],
        [
          {
            "action": {
              "type": "callback",
              "label": Buttons.admin_inline.LINK.value,
              "payload": {
                "action": "link",
                "row_id": row_id,
              },
            },
            "color": "primary",
          },
        ],
      ]
    )

  @staticmethod
  def registration_link_review_vk(*, row_id: int) -> str:
    return ReplyKbs.make_vk_callback(
      [
        [
          {
            "action": {
              "type": "callback",
              "label": Buttons.admin_inline.APPROVE.value,
              "payload": {
                "action": "approve",
                "row_id": row_id,
              },
            },
            "color": "positive",
          }
        ],
        [
          {
            "action": {
              "type": "callback",
              "label": Buttons.admin_inline.REJECT.value,
              "payload": {
                "action": "reject",
                "row_id": row_id,
              },
            },
            "color": "negative",
          },
        ],
        [
          {
            "action": {
              "type": "callback",
              "label": Buttons.admin_inline.LINK.value,
              "payload": {
                "action": "link",
                "row_id": row_id,
              },
            },
            "color": "primary",
          }
        ],
      ]
    )

  @staticmethod
  def link_candidates_tg(*, pending_row_id: int, users: list[User]) -> InlineKeyboardMarkup:
    return InlineKbs.link_candidates_tg_page(pending_row_id=pending_row_id, users=users, page=0)

  @staticmethod
  def link_candidates_tg_page(*, pending_row_id: int, users: list[User], page: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    start = page * InlineKbs.PAGE_SIZE
    end = start + InlineKbs.PAGE_SIZE
    page_users = users[start:end]
    for user in page_users:
      keyboard.button(
        text=f"{user.row_id} — {user.name}",
        callback_data=f"linkto:{pending_row_id}:{user.row_id}",
      )
    if page > 0:
      keyboard.button(
        text="⬅️",
        callback_data=f"linkto_page:{pending_row_id}:{page - 1}",
      )
    if end < len(users):
      keyboard.button(
        text="➡️",
        callback_data=f"linkto_page:{pending_row_id}:{page + 1}",
      )
    sizes = [1] * len(page_users)
    nav_count = int(page > 0) + int(end < len(users))
    if nav_count:
      sizes.append(nav_count)
    keyboard.adjust(*sizes)
    return keyboard.as_markup()

  @staticmethod
  def make_admin_candidates_tg(*, users: list[User]) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    for user in users[:20]:
      keyboard.button(
        text=user.name,
        callback_data=f"makeadmin:{user.row_id}",
      )
    keyboard.adjust(1)
    return keyboard.as_markup()

  @staticmethod
  def poker_params_tg(*, params: list) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    for p in params[:20]:
      keyboard.button(
        text=(
          f"ID {p.row_id}: {p.buyin_size_chips}/"
          f"{InlineKbs._format_rub_from_kopecks(p.buyin_size_kopecks)}, BB {p.bb_size_chips}"
        ),
        callback_data=f"pokerstart:{p.row_id}",
      )
    keyboard.adjust(1)
    return keyboard.as_markup()

  @staticmethod
  def poker_add_player_candidates_tg(*, users: list[User]) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    for user in users[:20]:
      keyboard.button(
        text=user.name,
        callback_data=f"pokeradd:{user.row_id}",
      )
    keyboard.adjust(1)
    return keyboard.as_markup()

  @staticmethod
  def poker_cashier_candidates_tg(*, players: list) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    for player in players[:20]:
      keyboard.button(
        text=player.player_name,
        callback_data=f"pokercashier:{player.player_id}",
      )
    keyboard.adjust(1)
    return keyboard.as_markup()

  @staticmethod
  def poker_remove_player_candidates_tg(*, players: list) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    for player in players[:20]:
      keyboard.button(
        text=player.player_name,
        callback_data=f"pokerremove:{player.player_id}",
      )
    keyboard.adjust(1)
    return keyboard.as_markup()

  @staticmethod
  def poker_unban_player_candidates_tg(*, players: list) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    for player in players[:20]:
      keyboard.button(
        text=player["name"][:64],
        callback_data=f"pokerunban:{player['player_id']}",
      )
    keyboard.adjust(1)
    return keyboard.as_markup()

  @staticmethod
  def poker_buyin_candidates_tg(*, players: list) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    for player in players[:20]:
      keyboard.button(
        text=player.player_name,
        callback_data=f"pokerbuyin:{player.player_id}",
      )
    keyboard.button(
      text=Buttons.betting_inline.CONFIRM_NO.value,
      callback_data="pokerbuyincancel:0",
    )
    keyboard.adjust(1)
    return keyboard.as_markup()

  @staticmethod
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
        special_values.append((int(big_buyin), str(big_buyin_pic or "🟠")))
      if allow_super and super_buyin is not None and int(super_buyin) > safe_max:
        special_values.append((int(super_buyin), str(super_buyin_pic or "⭐")))
      if allow_king and king_buyin is not None and int(king_buyin) > safe_max:
        special_values.append((int(king_buyin), str(king_buyin_pic or "👑")))
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

  @staticmethod
  def poker_cashout_candidates_tg(*, players: list) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    for player in players[:20]:
      keyboard.button(
        text=player.player_name,
        callback_data=f"pokercashout:{player.player_id}",
      )
    keyboard.adjust(1)
    return keyboard.as_markup()

  @staticmethod
  def registration_candidates_tg(*, users: list[User]) -> InlineKeyboardMarkup:
    return InlineKbs.registration_candidates_tg_page(users=users, page=0)

  @staticmethod
  def registration_candidates_tg_page(*, users: list[User], page: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    start = page * InlineKbs.PAGE_SIZE
    end = start + InlineKbs.PAGE_SIZE
    page_users = users[start:end]
    for user in page_users:
      keyboard.button(
        text=user.name[:64],
        callback_data=f"registration_existing:{user.row_id}",
      )
    if page > 0:
      keyboard.button(
        text="⬅️",
        callback_data=f"registration_existing_page:{page - 1}",
      )
    if end < len(users):
      keyboard.button(
        text="➡️",
        callback_data=f"registration_existing_page:{page + 1}",
      )
    keyboard.button(
      text=Buttons.registration_inline.NOT_IN_LIST.value,
      callback_data="registration_existing:new",
    )
    sizes = [1] * len(page_users)
    nav_count = int(page > 0) + int(end < len(users))
    if nav_count:
      sizes.append(nav_count)
    sizes.append(1)
    keyboard.adjust(*sizes)
    return keyboard.as_markup()

  @staticmethod
  def registration_candidates_vk(*, users: list[User]) -> str:
    return InlineKbs.registration_candidates_vk_page(users=users, page=0)

  @staticmethod
  def registration_candidates_vk_page(*, users: list[User], page: int) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    start = page * InlineKbs.PAGE_SIZE
    end = start + InlineKbs.PAGE_SIZE
    page_users = users[start:end]
    for user in page_users:
      rows.append(
        [
          {
            "action": {
              "type": "callback",
              "label": user.name[:40],
              "payload": {
                "action": "registration_existing",
                "row_id": user.row_id,
              },
            },
            "color": "primary",
          }
        ]
      )
    nav_row: list[dict[str, str | dict[str, int | str]]] = []
    if page > 0:
      nav_row.append(
        {
          "action": {
            "type": "callback",
            "label": "⬅️",
            "payload": {
              "action": "registration_existing_page",
              "page": page - 1,
            },
          },
          "color": "secondary",
        }
      )
    if end < len(users):
      nav_row.append(
        {
          "action": {
            "type": "callback",
            "label": "➡️",
            "payload": {
              "action": "registration_existing_page",
              "page": page + 1,
            },
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
            "label": Buttons.registration_inline.NOT_IN_LIST.value,
            "payload": {
              "action": "registration_new_name",
            },
          },
          "color": "secondary",
        }
      ]
    )
    return ReplyKbs.make_vk_callback(rows)

  @staticmethod
  def registration_optional_details_vk() -> str:
    return ReplyKbs.make_vk_callback(
      [
        [
          {
            "action": {
              "type": "callback",
              "label": Buttons.registration_inline.OPTIONAL_BANK.value,
              "payload": {"action": "registration_optional_bank"},
            },
            "color": "primary",
          }
        ],
        [
          {
            "action": {
              "type": "callback",
              "label": Buttons.registration_inline.OPTIONAL_PHONE.value,
              "payload": {"action": "registration_optional_phone"},
            },
            "color": "primary",
          },
        ],
        [
          {
            "action": {
              "type": "callback",
              "label": Buttons.registration_inline.OPTIONAL_SKIP.value,
              "payload": {"action": "registration_optional_skip"},
            },
            "color": "secondary",
          }
        ],
      ]
    )

  @staticmethod
  def make_admin_candidates_vk(*, users: list[User]) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    for user in users[:10]:
      rows.append(
        [
          {
            "action": {
              "type": "callback",
              "label": user.name[:40],
              "payload": {
                "action": "make_admin_select",
                "row_id": user.row_id,
              },
            },
            "color": "primary",
          }
        ]
      )
    return ReplyKbs.make_vk_callback(rows)

  @staticmethod
  def poker_params_vk(*, params: list) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    for p in params[:10]:
      rows.append(
        [
          {
            "action": {
              "type": "callback",
              "label": (
                f"ID {p.row_id}: {p.buyin_size_chips}/"
                f"{InlineKbs._format_rub_from_kopecks(p.buyin_size_kopecks)}, BB {p.bb_size_chips}"
              )[:40],
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

  @staticmethod
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
    return ReplyKbs.make_vk_callback(rows)

  @staticmethod
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

  @staticmethod
  def poker_remove_player_candidates_vk(*, players: list) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    for player in players[:10]:
      rows.append(
        [
          {
            "action": {
              "type": "callback",
              "label": player.player_name[:40],
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

  @staticmethod
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

  @staticmethod
  def poker_buyin_candidates_vk(*, players: list) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    for player in players[:10]:
      rows.append(
        [
          {
            "action": {
              "type": "callback",
              "label": player.player_name[:40],
              "payload": {
                "action": "poker_buyin_select",
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

  @staticmethod
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
        special_values.append((int(big_buyin), str(big_buyin_pic or "🟠")))
      if allow_super and super_buyin is not None and int(super_buyin) > safe_max:
        special_values.append((int(super_buyin), str(super_buyin_pic or "⭐")))
      if allow_king and king_buyin is not None and int(king_buyin) > safe_max:
        special_values.append((int(king_buyin), str(king_buyin_pic or "👑")))
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

  @staticmethod
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

  @staticmethod
  def registration_platform_vk() -> str:
    return ReplyKbs.make_vk_callback(
      [
        [
          {
            "action": {
              "type": "callback",
              "label": Buttons.registration_inline.PLATFORM_TG.value,
              "payload": {"action": "registration_platform_tg"},
            },
            "color": "primary",
          }
        ],
        [
          {
            "action": {
              "type": "callback",
              "label": Buttons.registration_inline.PLATFORM_VK.value,
              "payload": {"action": "registration_platform_vk"},
            },
            "color": "primary",
          },
        ]
      ]
    )

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
          "action": {"type": "callback", "label": f"🐤 {small_size_kopecks // 100} ₽", "payload": {"action": "bet_size", "amount_kopecks": small_size_kopecks}},
          "color": "primary",
        }],
        [{
          "action": {"type": "callback", "label": f"🐔 {big_size_kopecks // 100} ₽", "payload": {"action": "bet_size", "amount_kopecks": big_size_kopecks}},
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
  def betting_stat_indicators_tg(*, indicators: list, page: int = 0, selected_ids: list[int] | None = None) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    selected = set(selected_ids or [])
    start = page * InlineKbs.STAT_PAGE_SIZE
    end = start + InlineKbs.STAT_PAGE_SIZE
    batch = indicators[start:end]
    for indicator in batch:
      mark = "✔ " if int(indicator.row_id) in selected else ""
      keyboard.button(text=f"{mark}{indicator.pic} {indicator.description}"[:64], callback_data=f"betstat_toggle:{indicator.row_id}:{page}")
    if page > 0:
      keyboard.button(text="⬅️", callback_data=f"betstat_page:{page - 1}")
    if end < len(indicators):
      keyboard.button(text="➡️", callback_data=f"betstat_page:{page + 1}")
    keyboard.button(text="🚀 Готово", callback_data="betstat_done")
    keyboard.button(text="❌ Отмена", callback_data="betstat_cancel")
    sizes = [1] * len(batch)
    nav_count = int(page > 0) + int(end < len(indicators))
    if nav_count:
      sizes.append(nav_count)
    sizes.append(2)
    keyboard.adjust(*sizes)
    return keyboard.as_markup()

  @staticmethod
  def betting_stat_indicators_vk(*, indicators: list, page: int = 0, selected_ids: list[int] | None = None) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    selected = set(selected_ids or [])
    start = page * InlineKbs.STAT_PAGE_SIZE
    end = start + InlineKbs.STAT_PAGE_SIZE
    batch = indicators[start:end]
    for indicator in batch:
      mark = "✔ " if int(indicator.row_id) in selected else ""
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
        "action": {"type": "callback", "label": "⬅️", "payload": {"action": "betstat_page", "page": page - 1}},
        "color": "secondary",
      })
    if end < len(indicators):
      nav_row.append({
        "action": {"type": "callback", "label": "➡️", "payload": {"action": "betstat_page", "page": page + 1}},
        "color": "secondary",
      })
    if nav_row:
      rows.append(nav_row)
    rows.append([
      {
        "action": {"type": "callback", "label": "🚀 Готово", "payload": {"action": "betstat_done"}},
        "color": "positive",
      },
      {
        "action": {"type": "callback", "label": "❌ Отмена", "payload": {"action": "betstat_cancel"}},
        "color": "negative",
      },
    ])
    return ReplyKbs.make_vk_callback(rows)

  @staticmethod
  def betting_stat_mode_tg() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="📚 Все ставки", callback_data="betstatmode:all")
    keyboard.button(text="💰 Текущий regular", callback_data="betstatmode:regular")
    keyboard.button(text="🎄 Текущий year", callback_data="betstatmode:year")
    keyboard.adjust(1)
    return keyboard.as_markup()

  @staticmethod
  def betting_stat_mode_vk() -> str:
    return ReplyKbs.make_vk_callback(
      [
        [{
          "action": {"type": "callback", "label": "📚 Все ставки", "payload": {"action": "betstat_mode", "mode": "all"}},
          "color": "primary",
        }],
        [{
          "action": {"type": "callback", "label": "💰 Текущий regular", "payload": {"action": "betstat_mode", "mode": "regular"}},
          "color": "primary",
        }],
        [{
          "action": {"type": "callback", "label": "🎄 Текущий year", "payload": {"action": "betstat_mode", "mode": "year"}},
          "color": "primary",
        }],
      ]
    )

  @staticmethod
  def poker_stat_indicators_tg(*, indicators: list, page: int = 0, selected_ids: list[int] | None = None) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    selected = set(selected_ids or [])
    start = page * InlineKbs.STAT_PAGE_SIZE
    end = start + InlineKbs.STAT_PAGE_SIZE
    batch = indicators[start:end]
    for indicator in batch:
      mark = "✔ " if int(indicator.row_id) in selected else ""
      keyboard.button(text=f"{mark}{indicator.pic} {indicator.description}"[:64], callback_data=f"pokerstat_toggle:{indicator.row_id}:{page}")
    if page > 0:
      keyboard.button(text="⬅️", callback_data=f"pokerstat_page:{page - 1}")
    if end < len(indicators):
      keyboard.button(text="➡️", callback_data=f"pokerstat_page:{page + 1}")
    keyboard.button(text="🚀 Готово", callback_data="pokerstat_done")
    keyboard.button(text="❌ Отмена", callback_data="pokerstat_cancel")
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
    start = page * InlineKbs.STAT_PAGE_SIZE
    end = start + InlineKbs.STAT_PAGE_SIZE
    batch = indicators[start:end]
    for indicator in batch:
      mark = "✔ " if int(indicator.row_id) in selected else ""
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
        "action": {"type": "callback", "label": "⬅️", "payload": {"action": "pokerstat_page", "page": page - 1}},
        "color": "secondary",
      })
    if end < len(indicators):
      nav_row.append({
        "action": {"type": "callback", "label": "➡️", "payload": {"action": "pokerstat_page", "page": page + 1}},
        "color": "secondary",
      })
    if nav_row:
      rows.append(nav_row)
    rows.append([
      {
        "action": {"type": "callback", "label": "🚀 Готово", "payload": {"action": "pokerstat_done"}},
        "color": "positive",
      },
      {
        "action": {"type": "callback", "label": "❌ Отмена", "payload": {"action": "pokerstat_cancel"}},
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
    start = page * InlineKbs.STAT_PAGE_SIZE
    end = start + InlineKbs.STAT_PAGE_SIZE
    batch = years[start:end]
    for year in batch:
      mark = "✔ " if int(year) in selected else ""
      keyboard.button(text=f"{mark}{year}", callback_data=f"{prefix}_toggle:{year}:{page}")
    if page > 0:
      keyboard.button(text="⬅️", callback_data=f"{prefix}_page:{page - 1}")
    if end < len(years):
      keyboard.button(text="➡️", callback_data=f"{prefix}_page:{page + 1}")
    keyboard.button(text="🚀 Готово", callback_data=f"{prefix}_done")
    keyboard.button(text="❌ Отмена", callback_data=f"{prefix}_cancel")
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
    start = page * InlineKbs.STAT_PAGE_SIZE
    end = start + InlineKbs.STAT_PAGE_SIZE
    batch = years[start:end]
    for year in batch:
      mark = "✔ " if int(year) in selected else ""
      rows.append([
        {
          "action": {"type": "callback", "label": f"{mark}{year}", "payload": {"action": f"{action}_toggle", "year": int(year), "page": page}},
          "color": "primary",
        }
      ])
    nav_row: list[dict[str, str | dict[str, int | str]]] = []
    if page > 0:
      nav_row.append({"action": {"type": "callback", "label": "⬅️", "payload": {"action": f"{action}_page", "page": page - 1}}, "color": "secondary"})
    if end < len(years):
      nav_row.append({"action": {"type": "callback", "label": "➡️", "payload": {"action": f"{action}_page", "page": page + 1}}, "color": "secondary"})
    if nav_row:
      rows.append(nav_row)
    rows.append([
      {"action": {"type": "callback", "label": "🚀 Готово", "payload": {"action": f"{action}_done"}}, "color": "positive"},
      {"action": {"type": "callback", "label": "❌ Отмена", "payload": {"action": f"{action}_cancel"}}, "color": "negative"},
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
    start = page * InlineKbs.STAT_PAGE_SIZE
    end = start + InlineKbs.STAT_PAGE_SIZE
    batch = filtered[start:end]
    for indicator in batch:
      mark = "✔ " if selected_sort_id is not None and int(indicator.row_id) == int(selected_sort_id) else ""
      keyboard.button(
        text=f"{mark}{indicator.pic} {indicator.description}"[:64],
        callback_data=f"{prefix}_toggle:{int(indicator.row_id)}:{page}",
      )
    if page > 0:
      keyboard.button(text="⬅️", callback_data=f"{prefix}_page:{page - 1}")
    if end < len(filtered):
      keyboard.button(text="➡️", callback_data=f"{prefix}_page:{page + 1}")
    keyboard.button(text="🚀 Готово", callback_data=f"{prefix}_done")
    keyboard.button(text="❌ Отмена", callback_data=f"{prefix}_cancel")
    sizes = [1] * len(batch)
    nav_count = int(page > 0) + int(end < len(filtered))
    if nav_count:
      sizes.append(nav_count)
    sizes.append(2)
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
    start = page * InlineKbs.STAT_PAGE_SIZE
    end = start + InlineKbs.STAT_PAGE_SIZE
    batch = filtered[start:end]
    for indicator in batch:
      mark = "✔ " if selected_sort_id is not None and int(indicator.row_id) == int(selected_sort_id) else ""
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
        "action": {"type": "callback", "label": "⬅️", "payload": {"action": f"{action}_page", "page": page - 1}},
        "color": "secondary",
      })
    if end < len(filtered):
      nav_row.append({
        "action": {"type": "callback", "label": "➡️", "payload": {"action": f"{action}_page", "page": page + 1}},
        "color": "secondary",
      })
    if nav_row:
      rows.append(nav_row)
    rows.append([
      {
        "action": {"type": "callback", "label": "🚀 Готово", "payload": {"action": f"{action}_done"}},
        "color": "positive",
      },
      {
        "action": {"type": "callback", "label": "❌ Отмена", "payload": {"action": f"{action}_cancel"}},
        "color": "negative",
      },
    ])
    return ReplyKbs.make_vk_callback(rows)

  @staticmethod
  def poll_month_tg(
    *,
    month: date,
    page: int = 0,
    selected_dates: list[date] | None = None,
  ) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    selected = {item.isoformat() for item in (selected_dates or [])}
    days_in_month = calendar.monthrange(month.year, month.month)[1]
    all_dates = [date(month.year, month.month, day) for day in range(1, days_in_month + 1)]
    start = page * InlineKbs.POLL_PAGE_SIZE
    end = start + InlineKbs.POLL_PAGE_SIZE
    batch = all_dates[start:end]
    for item in batch:
      mark = "✔ " if item.isoformat() in selected else ""
      keyboard.button(
        text=f"{mark}{item.day}, {InlineKbs._weekday_ru(item)}",
        callback_data=f"poll_day:{item.isoformat()}:{page}",
      )
    keyboard.button(text="⬅️", callback_data=f"poll_page:{month.year}-{month.month:02d}:{page - 1}")
    keyboard.button(text="🚀 Готово", callback_data="poll_done")
    keyboard.button(text="❌ Отмена", callback_data="poll_cancel")
    keyboard.button(text="➡️", callback_data=f"poll_page:{month.year}-{month.month:02d}:{page + 1}")
    keyboard.adjust(2, 2, 2, 4)
    return keyboard.as_markup()

  @staticmethod
  def poll_month_vk(
    *,
    month: date,
    page: int = 0,
    selected_dates: list[date] | None = None,
  ) -> str:
    selected = {item.isoformat() for item in (selected_dates or [])}
    days_in_month = calendar.monthrange(month.year, month.month)[1]
    all_dates = [date(month.year, month.month, day) for day in range(1, days_in_month + 1)]
    start = page * InlineKbs.POLL_PAGE_SIZE_VK
    end = start + InlineKbs.POLL_PAGE_SIZE_VK
    batch = all_dates[start:end]
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    for index in range(0, len(batch), 2):
      row: list[dict[str, str | dict[str, int | str]]] = []
      for item in batch[index:index + 2]:
        mark = "✔ " if item.isoformat() in selected else ""
        row.append(
          {
            "action": {
              "type": "callback",
              "label": f"{mark}{item.day}, {InlineKbs._weekday_ru(item)}"[:40],
              "payload": {"action": "poll_day", "date": item.isoformat(), "page": page},
            },
            "color": "primary",
          }
        )
      rows.append(row)

    rows.append(
      [
        {
          "action": {
            "type": "callback",
            "label": "⬅️",
            "payload": {"action": "poll_page", "month": f"{month.year}-{month.month:02d}", "page": page - 1},
          },
          "color": "secondary",
        },
        {
          "action": {"type": "callback", "label": "🚀 Готово", "payload": {"action": "poll_done"}},
          "color": "positive",
        },
        {
          "action": {"type": "callback", "label": "❌ Отмена", "payload": {"action": "poll_cancel"}},
          "color": "negative",
        },
        {
          "action": {
            "type": "callback",
            "label": "➡️",
            "payload": {"action": "poll_page", "month": f"{month.year}-{month.month:02d}", "page": page + 1},
          },
          "color": "secondary",
        },
      ]
    )
    return ReplyKbs.make_vk_callback(rows)

  @staticmethod
  def link_candidates_vk(*, pending_row_id: int, users: list[User]) -> str:
    return InlineKbs.link_candidates_vk_page(pending_row_id=pending_row_id, users=users, page=0)

  @staticmethod
  def link_candidates_vk_page(*, pending_row_id: int, users: list[User], page: int) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    start = page * InlineKbs.PAGE_SIZE
    end = start + InlineKbs.PAGE_SIZE
    page_users = users[start:end]
    for user in page_users:
      rows.append(
        [
          {
            "action": {
              "type": "callback",
              "label": f"{user.row_id} — {user.name[:32]}",
              "payload": {
                "action": "link_to",
                "pending_row_id": pending_row_id,
                "existing_row_id": user.row_id,
              },
            },
            "color": "primary",
          }
        ]
      )
    nav_row: list[dict[str, str | dict[str, int | str]]] = []
    if page > 0:
      nav_row.append(
        {
          "action": {
            "type": "callback",
            "label": "⬅️",
            "payload": {
              "action": "link_page",
              "pending_row_id": pending_row_id,
              "page": page - 1,
            },
          },
          "color": "secondary",
        }
      )
    if end < len(users):
      nav_row.append(
        {
          "action": {
            "type": "callback",
            "label": "➡️",
            "payload": {
              "action": "link_page",
              "pending_row_id": pending_row_id,
              "page": page + 1,
            },
          },
          "color": "secondary",
        }
      )
    if nav_row:
      rows.append(nav_row)
    return ReplyKbs.make_vk_callback(rows)
