from aiogram.types import (
  InlineKeyboardButton,
  InlineKeyboardMarkup,
  KeyboardButton,
  ReplyKeyboardMarkup,
)

main_keyboard = ReplyKeyboardMarkup(
  keyboard=[
    [KeyboardButton(text="Регистрация")],
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
