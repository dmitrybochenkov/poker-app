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
      _button_labels([Buttons.new_user.REGISTRATION]),
      adjust=1,
    )

  @classmethod
  def new_user_vk(cls) -> str:
    return cls.make_vk(
      _button_labels([Buttons.new_user.REGISTRATION]),
      adjust=1,
      one_time=False,
      color="primary",
    )

  @classmethod
  def played_before_vk(cls) -> str:
    return cls.make_vk(
      _button_labels(
        [
          Buttons.registration_flow.YES,
          Buttons.registration_flow.NO,
        ]
      ),
      adjust=1,
      one_time=False,
      inline=True,
      color="primary",
    )
