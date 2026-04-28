from enum import Enum


class AdminText(Enum):
  NEW_REGISTRATION = "Новая заявка на регистрацию"
  NO_RIGHTS = "Недостаточно прав."
  USER_NOT_FOUND = "Пользователь не найден."
  MAKE_ADMIN_USAGE = "Использование: /make_admin <row_id>"
  MAKE_ADMIN_SUCCESS = "Права администратора выданы."
  APPROVE_ACTION = "Заявка одобрена."
  REJECT_ACTION = "Заявка отклонена."
  IDENTIFY_USER_ERROR = "Не удалось определить пользователя."
  REQUEST_NOT_FOUND = "Заявка не найдена."
  REQUEST_ALREADY_APPROVED = "Одобренную заявку нельзя отклонить."
