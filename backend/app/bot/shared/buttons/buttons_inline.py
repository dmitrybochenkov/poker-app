from enum import Enum


class RegistrationInlineBtns(Enum):
  YES = "Да"
  NO = "Нет"
  NOT_IN_LIST = "Меня нет в списке"
  OPTIONAL_BANK = "🏦 Банк"
  OPTIONAL_PHONE = "☎️ Телефон"
  OPTIONAL_SKIP = "🥷 Не хочу указывать"
  PLATFORM_TG = "👦 Телеграм"
  PLATFORM_VK = "👴 ВК"


class AdminInlineBtns(Enum):
  APPROVE = "✅ Принять"
  CORRECT = "✏️ Изменить имя"
  REJECT = "❌ Отклонить"
  LINK = "🔗 Привязать"


class BettingInlineBtns(Enum):
  REGULAR_TOUR = "💰 Регулярный турнир"
  YEAR_TOUR = "🎄 Годовой турнир"
  CONFIRM_YES = "✅ Подтвердить"
  CONFIRM_NO = "❌ Отмена"
