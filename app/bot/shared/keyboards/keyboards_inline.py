from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.keyboards.keyboards_reply import ReplyKbs
from app.bot.shared.texts.texts import Text
from app.db.models.user import User


class InlineKbs:
  @staticmethod
  def played_before_tg() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    keyboard.button(
      text=Buttons.registration_flow.YES.value,
      callback_data="registration_played_before:yes",
    )
    keyboard.button(
      text=Buttons.registration_flow.NO.value,
      callback_data="registration_played_before:no",
    )
    keyboard.adjust(2)
    return keyboard.as_markup()

  @staticmethod
  def registration_optional_details_tg() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    keyboard.button(
      text=Text.user.REGISTRATION_OPTIONAL_BANK.value,
      callback_data="registration_optional:bank",
    )
    keyboard.button(
      text=Text.user.REGISTRATION_OPTIONAL_PHONE.value,
      callback_data="registration_optional:phone",
    )
    keyboard.button(
      text=Text.user.REGISTRATION_OPTIONAL_SKIP.value,
      callback_data="registration_optional:skip",
    )
    keyboard.adjust(2, 1)
    return keyboard.as_markup()

  @staticmethod
  def registration_platform_tg() -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    keyboard.button(
      text=Text.user.REGISTRATION_PLATFORM_TG.value,
      callback_data="registration_platform:tg",
    )
    keyboard.button(
      text=Text.user.REGISTRATION_PLATFORM_VK.value,
      callback_data="registration_platform:vk",
    )
    keyboard.adjust(2)
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
    keyboard.adjust(3, 1)
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
    keyboard.adjust(2, 1)
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
          },
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
              "label": Buttons.admin_inline.CORRECT.value,
              "payload": {
                "action": "correct",
                "row_id": row_id,
              },
            },
            "color": "secondary",
          },
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
          },
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
    keyboard = InlineKeyboardBuilder()
    for user in users[:20]:
      keyboard.button(
        text=f"{user.row_id} — {user.name}",
        callback_data=f"linkto:{pending_row_id}:{user.row_id}",
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
        text=f"ID {p.row_id}: {p.buyin_size_chips}/{p.buyin_size_rub}, BB {p.bb_size_chips}",
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
  def registration_candidates_tg(*, users: list[User]) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    for user in users[:20]:
      keyboard.button(
        text=user.name,
        callback_data=f"registration_existing:{user.row_id}",
      )
    keyboard.button(
      text=Buttons.registration_inline.NOT_IN_LIST.value,
      callback_data="registration_existing:new",
    )
    keyboard.adjust(1)
    return keyboard.as_markup()

  @staticmethod
  def registration_candidates_vk(*, users: list[User]) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    for user in users[:10]:
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
              "label": Text.user.REGISTRATION_OPTIONAL_BANK.value,
              "payload": {"action": "registration_optional_bank"},
            },
            "color": "primary",
          },
          {
            "action": {
              "type": "callback",
              "label": Text.user.REGISTRATION_OPTIONAL_PHONE.value,
              "payload": {"action": "registration_optional_phone"},
            },
            "color": "primary",
          },
        ],
        [
          {
            "action": {
              "type": "callback",
              "label": Text.user.REGISTRATION_OPTIONAL_SKIP.value,
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
              "label": f"ID {p.row_id}: {p.buyin_size_chips}/{p.buyin_size_rub}, BB {p.bb_size_chips}"[:40],
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
  def registration_platform_vk() -> str:
    return ReplyKbs.make_vk_callback(
      [
        [
          {
            "action": {
              "type": "callback",
              "label": Text.user.REGISTRATION_PLATFORM_TG.value,
              "payload": {"action": "registration_platform_tg"},
            },
            "color": "primary",
          },
          {
            "action": {
              "type": "callback",
              "label": Text.user.REGISTRATION_PLATFORM_VK.value,
              "payload": {"action": "registration_platform_vk"},
            },
            "color": "primary",
          },
        ]
      ]
    )

  @staticmethod
  def link_candidates_vk(*, pending_row_id: int, users: list[User]) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    for user in users[:10]:
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
    return ReplyKbs.make_vk_callback(rows)
