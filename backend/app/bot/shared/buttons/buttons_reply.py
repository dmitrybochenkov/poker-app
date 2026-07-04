from enum import Enum


class NewUserBtns(Enum):
  ABOUT = "ℹ️ О покер боте"
  REGISTRATION = "💾 Зарегистрироваться"

class MainBtns(Enum):
  NEXT_POKER_DATE = "📅 Следующий покер"
  ROOM = "♣️ Покер рум"
  POKER = "💍 Про покер"
  BETTING = "🍀 Про ставки"
  INFO = "ℹ️ Информация"
  ADMIN = "🔑 Админ панель"


class PollMenuBtns(Enum):
  VOTE = "✅ Проголосовать"
  RESULTS = "📊 Посмотреть результаты"
  TO_MAIN = "🏠 На главную"


class MainInfoBtns(Enum):
  POKER_INFO = "ℹ️💍 Про покер"
  BETTING_INFO = "ℹ️🍀 Про ставки"
  TO_MAIN = "🏠 На главную"

class AdminMainBtns(Enum):
  START_POKER = "🎲 Старт покера"
  CREATE_POLL = "🗓 Создать опрос"
  MAKE_ADMIN = "👨🏻‍💻 Добавить админа"
  TO_MAIN = "🏠 На главную"

class RoomBtns(Enum):
  STATUS = "ℹ️ Статус"
  BUYIN = "🏦 Закуп"
  TO_MAIN = "🏠 На главную"
  POKER_ADMIN = "🔑 Покер админ панель"

class AdminRoomBtns(Enum):
  SET_CASHIER = "🏦 Назначить кассира"
  START_BETTING = "🍀 Старт ставок"
  FINISH_POKER = "🏁 Финиш покера"
  CALCULATE_POKER = "🤖 Рассчитать покер" # 
  ADD_PLAYER = "👨 Добавить игрока"
  REMOVE_PLAYER = "❌ Удалить игрока"
  UNBAN_PLAYER = "✅ Разрешить обратно"
  CORRECT_POKER = "🔧 Корректировать покер"
  TO_ROOM = "♣️ В ПокерРум"


class AdminRoomCorrectBtns(Enum):
  SET_CASHIER = "🏦 Назначить кассира"
  ADD_PLAYER = "👨 Добавить игрока"
  REMOVE_PLAYER = "❌ Удалить игрока"
  BUYIN_CORRECT = "🏦 Корректировать закупы"
  TO_ADMIN_ROOM = "↩️ Назад"

class BettingBtns(Enum):
  MAKE_BET = "🐔 Сделать ставку"
  PAY_BET = "🤝 Оплатить ставку"
  CURRENT_TOURS = "🎰 Текущие турниры"
  BETTING_STAT = "🍀 Статистика ставок"
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
  HISTORY = "⌛ История"
  POLL = "🗓 Опрос"
  TO_MAIN = "🏠 На главную"

class PokerInfoBtns(Enum):
  POKER_ACH_INFO = "ℹ️🌟 Ачивки для покера"
  POKER_STAT_INFO = "ℹ️📊 Показатели для покера"
  HISTORY = "⌛ История"
  TO_MAIN = "🏠 На главную"
