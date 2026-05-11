from enum import Enum


class RegistrationInlineBtns(Enum):
  NOT_IN_LIST = "Меня нет в списке"


class AdminInlineBtns(Enum):
  APPROVE = "✅ Принять"
  CORRECT = "✏️ Изменить"
  REJECT = "❌ Отклонить"
  LINK = "🔗 Привязать"
