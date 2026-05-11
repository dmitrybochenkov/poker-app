from enum import Enum


class RegistrationInlineBtns(Enum):
  NOT_IN_LIST = "Меня нет в списке"
  OPTIONAL_BANK = "🏦 Банк"
  OPTIONAL_PHONE = "☎️ Телефон"
  OPTIONAL_SKIP = "🥷 Не хочу указывать"
  PLATFORM_TG = "👦 Телеграм"
  PLATFORM_VK = "👴 ВК"


class AdminInlineBtns(Enum):
  APPROVE = "✅ Принять"
  CORRECT = "✏️ Изменить"
  REJECT = "❌ Отклонить"
  LINK = "🔗 Привязать"
