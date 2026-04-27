from enum import Enum


class UserText(Enum):
  BOT_INFO = (
    "Привет! Я бот покерного приложения.\n\n"
    "Я помогаю проводить покерные игры и принимать ставки.\n\n"
    "Чтобы начать пользоваться моими функциями, тебе нужно зарегистрироваться."
  )
  REGISTRATION_NEW_USER = (
    "Введи свои имя и фамилию русскими буквами через пробел. "
    "Пожалуйста, вводи настоящие!"
  )
  REGISTRATION_EXIST = "Ты уже зарегистрирован."
  REGISTRATION_WAIT = "Заявка отправлена, после ее рассмотрения тебе придет сообщение."
  REGISTRATION_APPROVED = "Ты успешно зарегистрирован!"
  REGISTRATION_NOT_APPROVED = "Ты не зарегистрирован! Спроси у админа почему."
  REGISTRATION_PENDING = "Твоя заявка уже ожидает подтверждения администратора."
  REGISTRATION_INVALID_NAME = "Нужно указать имя и фамилию одним сообщением."
  REGISTRATION_READ_ERROR = "Не удалось прочитать данные. Попробуй ещё раз."
  REGISTRATION_ID_ERROR = "Не удалось определить Telegram ID."
  ADMIN_NEW_REGISTRATION = "Новая заявка на регистрацию"
  ADMIN_NO_RIGHTS = "Недостаточно прав."
  ADMIN_USER_NOT_FOUND = "Пользователь не найден."
  ADMIN_MAKE_ADMIN_USAGE = "Использование: /make_admin <row_id>"
  ADMIN_MAKE_ADMIN_SUCCESS = "Права администратора выданы."


class Text:
  user = UserText
