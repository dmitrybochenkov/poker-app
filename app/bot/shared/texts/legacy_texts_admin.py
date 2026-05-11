from enum import Enum


class LegacyAdminText(Enum):
  CANCEL = "Отмена."
  REGISTRATION_NEW_USER = "Новый пользователь!"
  REGISTRATION_NOT_APPROVED_BEFORE = " был удален из базы другим админом!"
  REGISTRATION_APPROVED_BEFORE = " был сохранен в базе другим админом!"
  REGISTRATION_APPROVED = " сохранен в базе!"
  REGISTRATION_NOT_APPROVED = " удален из базы!"
  REGISTRATION_CORRECT_NAME = "Введи новое имя для пользователя: "

  HI_ADMIN = "Добро пожаловать в админ панель!"
  HI_POKER_ADMIN = "Добро пожаловать в покер админ панель!"
  ROOM_NEW_PLAYER = "В покер рум хочет зайти "
  ROOM_PLAYER_NOT_APPROVED_BEFORE = " был удален из рума другим админом!"
  ROOM_PLAYER_APPROVED_BEFORE = " был добавлен в рум другим админом!"
  ROOM_PLAYER_APPROVED = " добавлен в рум!"
  ROOM_PLAYER_NOT_APPROVED = " удален из рума!"

  POKER_START = "Не забудь назначить кассира и запустить ставки!"
  POKER_STARTED = "Покер уже идет - нельзя начать новый!"
  POKER_PARAMS_LIST = "Варианты параметров для сегодняшнего покера: "
  POKER_PARAMS_CHOOSE = "Нужно выбрать вариант или добавить новый: "
  POKER_PARAMS_ADDING_BUYIN_SIZE_CHIPS = "Добавляем новые параметры покера. \nВведи количество фишек за 1 закуп (например, 200): "
  POKER_PARAMS_ADDING_BUYIN_SIZE_RUB = "Теперь введи количество денег за 1 закуп (например, 100): "
  POKER_PARAMS_ADDING_MAX_BUYINS = "Теперь введи количество максимальных закупов за один раз (например, 2): "
  POKER_PARAMS_ADDING_BB_SIZE = "Теперь введи размер ББ (например, 20): "
  POKER_PARAMS_ADDING_APPROVE = "Подтверди новые параметры для покера: "
  POKER_PARAMS_SAVE = "Сохранено."

  SET_CASHIER = "Кто будет выдавать фишки: "
  SET_CASHIER_WAIT = "Подожди, кассир еще не зашел в покер рум!"
  SET_CASHIER_ADDED = " выбран кассиром!"
  BETTING_START = "Пора ставить ставки! Не забывайте, как Илларионов Саня поднял 8к в 25 году)"
