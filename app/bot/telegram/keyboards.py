from aiogram.types import (
  KeyboardButton,
  ReplyKeyboardMarkup,
)

main_keyboard = ReplyKeyboardMarkup(
  keyboard=[
    [KeyboardButton(text="Регистрация")],
  ],
  resize_keyboard=True,
)
