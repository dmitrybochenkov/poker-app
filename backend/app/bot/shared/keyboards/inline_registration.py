from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.keyboards.keyboards_reply import ReplyKbs
from app.bot.shared.texts.inline.shared import keyboards_inline as InlineText
from app.db.models.user import User

from .inline_base import InlineKeyboardBase

class RegistrationInlineKbs(InlineKeyboardBase):
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
    return RegistrationInlineKbs.link_candidates_tg_page(pending_row_id=pending_row_id, users=users, page=0)

  @staticmethod
  def link_candidates_tg_page(*, pending_row_id: int, users: list[User], page: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    start = page * RegistrationInlineKbs.PAGE_SIZE
    end = start + RegistrationInlineKbs.PAGE_SIZE
    page_users = users[start:end]
    for user in page_users:
      keyboard.button(
        text=f'{user.row_id}{InlineText.BUTTON_LABEL_LINE_368}{user.name}',
        callback_data=f"linkto:{pending_row_id}:{user.row_id}",
      )
    if page > 0:
      keyboard.button(
        text=InlineText.PAGE_PREVIOUS,
        callback_data=f"linkto_page:{pending_row_id}:{page - 1}",
      )
    if end < len(users):
      keyboard.button(
        text=InlineText.PAGE_NEXT,
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
  def registration_candidates_tg(*, users: list[User]) -> InlineKeyboardMarkup:
    return RegistrationInlineKbs.registration_candidates_tg_page(users=users, page=0)

  @staticmethod
  def registration_candidates_tg_page(*, users: list[User], page: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardBuilder()
    start = page * RegistrationInlineKbs.PAGE_SIZE
    end = start + RegistrationInlineKbs.PAGE_SIZE
    page_users = users[start:end]
    for user in page_users:
      keyboard.button(
        text=user.name[:64],
        callback_data=f"registration_existing:{user.row_id}",
      )
    if page > 0:
      keyboard.button(
        text=InlineText.PAGE_PREVIOUS,
        callback_data=f"registration_existing_page:{page - 1}",
      )
    if end < len(users):
      keyboard.button(
        text=InlineText.PAGE_NEXT,
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
    return RegistrationInlineKbs.registration_candidates_vk_page(users=users, page=0)

  @staticmethod
  def registration_candidates_vk_page(*, users: list[User], page: int) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    start = page * RegistrationInlineKbs.PAGE_SIZE
    end = start + RegistrationInlineKbs.PAGE_SIZE
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
            "label": InlineText.PAGE_PREVIOUS,
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
            "label": InlineText.PAGE_NEXT,
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
  def link_candidates_vk(*, pending_row_id: int, users: list[User]) -> str:
    return RegistrationInlineKbs.link_candidates_vk_page(pending_row_id=pending_row_id, users=users, page=0)

  @staticmethod
  def link_candidates_vk_page(*, pending_row_id: int, users: list[User], page: int) -> str:
    rows: list[list[dict[str, str | dict[str, int | str]]]] = []
    start = page * RegistrationInlineKbs.PAGE_SIZE
    end = start + RegistrationInlineKbs.PAGE_SIZE
    page_users = users[start:end]
    for user in page_users:
      rows.append(
        [
          {
            "action": {
              "type": "callback",
              "label": f'{user.row_id}{InlineText.BUTTON_LABEL_LINE_368}{user.name[:32]}',
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
            "label": InlineText.PAGE_PREVIOUS,
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
            "label": InlineText.PAGE_NEXT,
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
