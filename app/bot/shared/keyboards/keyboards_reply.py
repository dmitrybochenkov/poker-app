import json
from collections.abc import Iterable

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from app.bot.shared.buttons.buttons import Buttons


def _button_labels(buttons: Iterable) -> list[str]:
  labels: list[str] = []
  for button in buttons:
    labels.append(button.value if hasattr(button, "value") else str(button))
  return labels


class ReplyKbs:
  @staticmethod
  def make_tg(labels: list[str], *, adjust: int = 1, resize: bool = True) -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardBuilder()
    for label in labels:
      keyboard.add(KeyboardButton(text=label))
    return keyboard.adjust(adjust).as_markup(resize_keyboard=resize)

  @staticmethod
  def make_vk(
    labels: list[str],
    *,
    adjust: int = 1,
    one_time: bool = False,
    inline: bool = False,
    color: str = "primary",
  ) -> str:
    rows: list[list[dict]] = []
    current_row: list[dict] = []

    for index, label in enumerate(labels, start=1):
      current_row.append(
        {
          "action": {
            "type": "text",
            "label": label,
          },
          "color": color,
        }
      )
      if index % adjust == 0:
        rows.append(current_row)
        current_row = []

    if current_row:
      rows.append(current_row)

    return json.dumps(
      {
        "one_time": one_time,
        "inline": inline,
        "buttons": rows,
      },
      ensure_ascii=False,
    )

  @staticmethod
  def make_vk_callback(
    rows: list[list[dict[str, str | dict[str, int | str]]]],
    *,
    one_time: bool = False,
    inline: bool = True,
  ) -> str:
    return json.dumps(
      {
        "one_time": one_time,
        "inline": inline,
        "buttons": rows,
      },
      ensure_ascii=False,
    )

  @classmethod
  def new_user_tg(cls) -> ReplyKeyboardMarkup:
    return cls.make_tg(
      _button_labels(
        [
          Buttons.new_user.ABOUT,
          Buttons.new_user.REGISTRATION,
        ]
      ),
      adjust=1,
    )

  @classmethod
  def new_user_vk(cls) -> str:
    return cls.make_vk(
      _button_labels(
        [
          Buttons.new_user.ABOUT,
          Buttons.new_user.REGISTRATION,
        ]
      ),
      adjust=1,
      one_time=False,
      color="primary",
    )

  @classmethod
  def main_tg(cls) -> ReplyKeyboardMarkup:
    return cls.make_tg(
      _button_labels(
        [
          Buttons.main.ROOM,
          Buttons.main.POKER,
          Buttons.main.BETTING,
          Buttons.main.ADMIN,
        ]
      ),
      adjust=1,
    )

  @classmethod
  def admin_main_entry_tg(cls) -> ReplyKeyboardMarkup:
    return cls.make_tg(
      _button_labels(
        [
          Buttons.main.ROOM,
          Buttons.main.POKER,
          Buttons.main.BETTING,
          Buttons.main.ADMIN,
        ]
      ),
      adjust=1,
    )

  @classmethod
  def main_vk(cls) -> str:
    return cls.make_vk(
      _button_labels(
        [
          Buttons.main.ROOM,
          Buttons.main.POKER,
          Buttons.main.BETTING,
          Buttons.main.ADMIN,
        ]
      ),
      adjust=1,
      one_time=False,
      color="primary",
    )

  @classmethod
  def admin_main_entry_vk(cls) -> str:
    return cls.make_vk(
      _button_labels(
        [
          Buttons.main.ROOM,
          Buttons.main.POKER,
          Buttons.main.BETTING,
          Buttons.main.ADMIN,
        ]
      ),
      adjust=1,
      one_time=False,
      color="primary",
    )

  @classmethod
  def admin_main_tg(cls) -> ReplyKeyboardMarkup:
    return cls.make_tg(
      _button_labels(
        [
          Buttons.admin_main.START_POKER,
          Buttons.admin_main.MAKE_ADMIN,
          Buttons.admin_main.TO_MAIN,
        ]
      ),
      adjust=1,
    )

  @classmethod
  def admin_main_vk(cls) -> str:
    return cls.make_vk(
      _button_labels(
        [
          Buttons.admin_main.START_POKER,
          Buttons.admin_main.MAKE_ADMIN,
          Buttons.admin_main.TO_MAIN,
        ]
      ),
      adjust=1,
      one_time=False,
      color="primary",
    )

  @classmethod
  def betting_tg(cls) -> ReplyKeyboardMarkup:
    return cls.make_tg(
      _button_labels(
        [
          Buttons.betting.MAKE_BET,
          Buttons.betting.CURRENT_TOURS,
          Buttons.betting.BETTING_STAT,
          Buttons.betting.BETTING_INFO,
          Buttons.betting.TO_MAIN,
        ]
      ),
      adjust=1,
    )

  @classmethod
  def betting_vk(cls) -> str:
    return cls.make_vk(
      _button_labels(
        [
          Buttons.betting.MAKE_BET,
          Buttons.betting.CURRENT_TOURS,
          Buttons.betting.BETTING_STAT,
          Buttons.betting.BETTING_INFO,
          Buttons.betting.TO_MAIN,
        ]
      ),
      adjust=1,
      one_time=False,
      color="primary",
    )

  @classmethod
  def betting_current_tg(cls) -> ReplyKeyboardMarkup:
    return cls.make_tg(
      _button_labels(
        [
          Buttons.betting_current.REG_TOURNAMENT,
          Buttons.betting_current.YEAR_TOURNAMENT,
          Buttons.betting_current.TO_MAIN,
        ]
      ),
      adjust=1,
    )

  @classmethod
  def betting_current_vk(cls) -> str:
    return cls.make_vk(
      _button_labels(
        [
          Buttons.betting_current.REG_TOURNAMENT,
          Buttons.betting_current.YEAR_TOURNAMENT,
          Buttons.betting_current.TO_MAIN,
        ]
      ),
      adjust=1,
      one_time=False,
      color="primary",
    )

  @classmethod
  def poker_tg(cls) -> ReplyKeyboardMarkup:
    return cls.make_tg(
      _button_labels(
        [
          Buttons.poker.POKER_STAT,
          Buttons.poker.POKER_INFO,
          Buttons.poker.POLL,
          Buttons.poker.TO_MAIN,
        ]
      ),
      adjust=1,
    )

  @classmethod
  def poker_vk(cls) -> str:
    return cls.make_vk(
      _button_labels(
        [
          Buttons.poker.POKER_STAT,
          Buttons.poker.POKER_INFO,
          Buttons.poker.POLL,
          Buttons.poker.TO_MAIN,
        ]
      ),
      adjust=1,
      one_time=False,
      color="primary",
    )

  @classmethod
  def betting_info_tg(cls) -> ReplyKeyboardMarkup:
    return cls.make_tg(
      _button_labels(
        [
          Buttons.bettingInfo.BETTING_RULES,
          Buttons.bettingInfo.BETTING_ACH_INFO,
          Buttons.bettingInfo.BETTING_STAT_INFO,
          Buttons.bettingInfo.TO_MAIN,
        ]
      ),
      adjust=1,
    )

  @classmethod
  def betting_info_vk(cls) -> str:
    return cls.make_vk(
      _button_labels(
        [
          Buttons.bettingInfo.BETTING_RULES,
          Buttons.bettingInfo.BETTING_ACH_INFO,
          Buttons.bettingInfo.BETTING_STAT_INFO,
          Buttons.bettingInfo.TO_MAIN,
        ]
      ),
      adjust=1,
      one_time=False,
      color="primary",
    )

  @classmethod
  def poker_info_tg(cls) -> ReplyKeyboardMarkup:
    return cls.make_tg(
      _button_labels(
        [
          Buttons.pokerInfo.POKER_ACH_INFO,
          Buttons.pokerInfo.POKER_STAT_INFO,
          Buttons.pokerInfo.TO_MAIN,
        ]
      ),
      adjust=1,
    )

  @classmethod
  def poker_info_vk(cls) -> str:
    return cls.make_vk(
      _button_labels(
        [
          Buttons.pokerInfo.POKER_ACH_INFO,
          Buttons.pokerInfo.POKER_STAT_INFO,
          Buttons.pokerInfo.TO_MAIN,
        ]
      ),
      adjust=1,
      one_time=False,
      color="primary",
    )

  @classmethod
  def room_tg(cls) -> ReplyKeyboardMarkup:
    return cls.make_tg(
      _button_labels(
        [
          Buttons.room.STATUS,
          Buttons.room.BUYIN,
          Buttons.room.POKER_ADMIN,
          Buttons.room.TO_MAIN,
        ]
      ),
      adjust=1,
    )

  @classmethod
  def room_admin_tg(cls) -> ReplyKeyboardMarkup:
    return cls.make_tg(
      _button_labels(
        [
          Buttons.room.STATUS,
          Buttons.room.BUYIN,
          Buttons.room.POKER_ADMIN,
          Buttons.room.TO_MAIN,
        ]
      ),
      adjust=1,
    )

  @classmethod
  def room_vk(cls) -> str:
    return cls.make_vk(
      _button_labels(
        [
          Buttons.room.STATUS,
          Buttons.room.BUYIN,
          Buttons.room.POKER_ADMIN,
          Buttons.room.TO_MAIN,
        ]
      ),
      adjust=1,
      one_time=False,
      color="primary",
    )

  @classmethod
  def room_admin_vk(cls) -> str:
    return cls.make_vk(
      _button_labels(
        [
          Buttons.room.STATUS,
          Buttons.room.BUYIN,
          Buttons.room.POKER_ADMIN,
          Buttons.room.TO_MAIN,
        ]
      ),
      adjust=1,
      one_time=False,
      color="primary",
    )

  @classmethod
  def admin_room_tg(cls) -> ReplyKeyboardMarkup:
    return cls.make_tg(
      _button_labels(
        [
          Buttons.admin_room.SET_CASHIER,
          Buttons.admin_room.START_BETTING,
          Buttons.admin_room.FINISH_POKER,
          Buttons.admin_room.CALCULATE_POKER,
          Buttons.admin_room.ADD_PLAYER,
          Buttons.admin_room.REMOVE_PLAYER,
          Buttons.admin_room.UNBAN_PLAYER,
          Buttons.admin_room.TO_ROOM,
        ]
      ),
      adjust=1,
    )

  @classmethod
  def admin_room_vk(cls) -> str:
    return cls.make_vk(
      _button_labels(
        [
          Buttons.admin_room.SET_CASHIER,
          Buttons.admin_room.START_BETTING,
          Buttons.admin_room.FINISH_POKER,
          Buttons.admin_room.CALCULATE_POKER,
          Buttons.admin_room.ADD_PLAYER,
          Buttons.admin_room.REMOVE_PLAYER,
          Buttons.admin_room.UNBAN_PLAYER,
          Buttons.admin_room.TO_ROOM,
        ]
      ),
      adjust=1,
      one_time=False,
      color="primary",
    )
