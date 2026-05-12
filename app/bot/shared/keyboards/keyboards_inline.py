from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.keyboards.keyboards_reply import ReplyKbs
from app.bot.shared.texts.texts import Text
from app.db.models.user import User


class InlineKbs:
  PAGE_SIZE = 5

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
  def betting_player_tg(*, action: str, players: list[str]) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    for player in players:
      keyboard.button(text=player, callback_data=f"bet_{action}:{player}")
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
    keyboard.adjust(1)
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
  def poker_buyin_candidates_tg(*, players: list) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    for player in players[:20]:
      keyboard.button(
        text=player.player_name,
        callback_data=f"pokerbuyin:{player.player_id}",
      )
    keyboard.adjust(1)
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
    keyboard.adjust(1)
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
    if page > 0:
      rows.append(
        [
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
        ]
      )
    if end < len(users):
      rows.append(
        [
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
        ]
      )
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
  def betting_player_vk(*, action: str, players: list[str]) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    for player in players:
      rows.append([{
        "action": {"type": "callback", "label": player[:40], "payload": {"action": f"bet_{action}", "player_name": player}},
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
    start = page * InlineKbs.PAGE_SIZE
    end = start + InlineKbs.PAGE_SIZE
    batch = indicators[start:end]
    for indicator in batch:
      mark = "✅ " if int(indicator.row_id) in selected else ""
      keyboard.button(text=f"{mark}{indicator.pic} {indicator.description}"[:64], callback_data=f"betstat_toggle:{indicator.row_id}:{page}")
    if page > 0:
      keyboard.button(text="⬅️", callback_data=f"betstat_page:{page - 1}")
    if end < len(indicators):
      keyboard.button(text="➡️", callback_data=f"betstat_page:{page + 1}")
    keyboard.button(text="✅ Готово", callback_data="betstat_done")
    keyboard.adjust(1)
    return keyboard.as_markup()

  @staticmethod
  def betting_stat_indicators_vk(*, indicators: list, page: int = 0, selected_ids: list[int] | None = None) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    selected = set(selected_ids or [])
    start = page * InlineKbs.PAGE_SIZE
    end = start + InlineKbs.PAGE_SIZE
    batch = indicators[start:end]
    for indicator in batch:
      mark = "✅ " if int(indicator.row_id) in selected else ""
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
    if page > 0:
      rows.append([{
        "action": {"type": "callback", "label": "⬅️", "payload": {"action": "betstat_page", "page": page - 1}},
        "color": "secondary",
      }])
    if end < len(indicators):
      rows.append([{
        "action": {"type": "callback", "label": "➡️", "payload": {"action": "betstat_page", "page": page + 1}},
        "color": "secondary",
      }])
    rows.append([{
      "action": {"type": "callback", "label": "✅ Готово", "payload": {"action": "betstat_done"}},
      "color": "positive",
    }])
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
    start = page * InlineKbs.PAGE_SIZE
    end = start + InlineKbs.PAGE_SIZE
    batch = indicators[start:end]
    for indicator in batch:
      mark = "✅ " if int(indicator.row_id) in selected else ""
      keyboard.button(text=f"{mark}{indicator.pic} {indicator.description}"[:64], callback_data=f"pokerstat_toggle:{indicator.row_id}:{page}")
    if page > 0:
      keyboard.button(text="⬅️", callback_data=f"pokerstat_page:{page - 1}")
    if end < len(indicators):
      keyboard.button(text="➡️", callback_data=f"pokerstat_page:{page + 1}")
    keyboard.button(text="✅ Готово", callback_data="pokerstat_done")
    keyboard.adjust(1)
    return keyboard.as_markup()

  @staticmethod
  def poker_stat_indicators_vk(*, indicators: list, page: int = 0, selected_ids: list[int] | None = None) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    selected = set(selected_ids or [])
    start = page * InlineKbs.PAGE_SIZE
    end = start + InlineKbs.PAGE_SIZE
    batch = indicators[start:end]
    for indicator in batch:
      mark = "✅ " if int(indicator.row_id) in selected else ""
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
    if page > 0:
      rows.append([{
        "action": {"type": "callback", "label": "⬅️", "payload": {"action": "pokerstat_page", "page": page - 1}},
        "color": "secondary",
      }])
    if end < len(indicators):
      rows.append([{
        "action": {"type": "callback", "label": "➡️", "payload": {"action": "pokerstat_page", "page": page + 1}},
        "color": "secondary",
      }])
    rows.append([{
      "action": {"type": "callback", "label": "✅ Готово", "payload": {"action": "pokerstat_done"}},
      "color": "positive",
    }])
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
    if page > 0:
      rows.append(
        [
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
        ]
      )
    if end < len(users):
      rows.append(
        [
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
        ]
      )
    return ReplyKbs.make_vk_callback(rows)
