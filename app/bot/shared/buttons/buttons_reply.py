from enum import Enum


class NewUserBtns(Enum):
  ABOUT = "ℹ️ О покер боте"
  REGISTRATION = "💾 Зарегистрироваться"


class RegistrationFlowBtns(Enum):
  YES = "Да"
  NO = "Нет"


class MainBtns(Enum):
  ROOM = "♣️ Покер рум"
  POKER = "💍 Про покер"
  BETTING = "🍀 Про ставки"
  ADMIN = "🔑 Админ панель"


class AdminMainBtns(Enum):
  START_POKER = "🎲 Старт покера"
  TO_MAIN = "🏠 На главную"


class RoomBtns(Enum):
  STATUS = "ℹ️ Статус"
  BUYIN = "🏦 Закуп"
  TO_MAIN = "🏠 На главную"
  POKER_ADMIN = "🎲 Покер админ панель"


class AdminRoomBtns(Enum):
  SET_CASHIER = "🏦 Назначить кассира"
  CASHOUT = "💸 Кешаут"
  START_BETTING = "🍀 Старт ставок"
  FINISH_POKER = "🏁 Финиш покера"
  CALCULATE_POKER = "🤖 Рассчитать покер"
  ADD_PLAYER = "👨 Добавить игрока"
  REMOVE_PLAYER = "❌ Удалить игрока"
  CORRECT_POKER = "🔧 Исправить данные"
  TO_ROOM = "♣️ В ПокерРум"


class BettingBtns(Enum):
  MAKE_BET = "🐔 Сделать ставку"
  CURRENT_TOURS = "🎰 Текущие турниры"
  BETTING_STAT = "🍀 Статистика ставок"
  BETTING_INFO = "ℹ️ Информация про ставки"
  TO_MAIN = "🏠 На главную"


class BettingInfoBtns(Enum):
  BETTING_RULES = "📖 Правила"
  BETTING_ACH_INFO = "ℹ️🌟 Ачивки для ставок"
  BETTING_STAT_INFO = "ℹ️📊 Показатели для ставок"
  TO_MAIN = "🏠 На главную"


class BettingCurrentBtns(Enum):
  REG_TOURNAMENT = "💰 Регулярный турнир"
  YEAR_TOURNAMENT = "🎄💰 Годовой турнир"
  TO_MAIN = "🏠 На главную"


class PokerBtns(Enum):
  POKER_STAT = "🦑 Статистика покера"
  POKER_INFO = "ℹ️ Информация про покер"
  TO_MAIN = "🏠 На главную"


class PokerInfoBtns(Enum):
  POKER_ACH_INFO = "ℹ️🌟 Ачивки для покера"
  POKER_STAT_INFO = "ℹ️📊 Показатели для покера"
  TO_MAIN = "🏠 На главную"
