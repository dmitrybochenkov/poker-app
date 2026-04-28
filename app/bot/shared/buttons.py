from enum import Enum


class NewUserButtons(Enum):
  REGISTRATION = "💾 Зарегистрироваться"
  ALREADY_REGISTERED_VK = "Я уже зарегистрирован в VK"
  ALREADY_REGISTERED_TG = "Я уже зарегистрирован в TG"


class Buttons:
  new_user = NewUserButtons
