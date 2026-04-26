from aiogram.types import (
  InlineKeyboardButton,
  InlineKeyboardMarkup,
  KeyboardButton,
  ReplyKeyboardMarkup,
)

from app.bot.shared.buttons import Buttons

main_keyboard = ReplyKeyboardMarkup(
  keyboard=[
    [KeyboardButton(text=Buttons.new_user.REGISTRATION.value)],
  ],
  resize_keyboard=True,
)


def registration_review_keyboard(*, row_id: int) -> InlineKeyboardMarkup:
  return InlineKeyboardMarkup(
    inline_keyboard=[
      [
        InlineKeyboardButton(text="Approve", callback_data=f"approve:{row_id}"),
        InlineKeyboardButton(text="Reject", callback_data=f"reject:{row_id}"),
      ]
    ]
  )
