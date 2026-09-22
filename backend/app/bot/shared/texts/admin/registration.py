"""Admin bot registration texts."""

NEW_REGISTRATION = "Новая заявка"

NEW_REGISTRATION_NEW = "Тип: новый пользоваель"

NEW_REGISTRATION_EXIST = "Тип: привязка платформы"

NEW_REGISTRATION_KIND_NEW = NEW_REGISTRATION_NEW

NEW_REGISTRATION_KIND_LINK = NEW_REGISTRATION_EXIST

LINK_PROMPT = "Отправь row_id существующего пользователя, к которому нужно привязать эту заявку."

LINK_CHOICES_TITLE = "Одобренные пользователи:"

LINK_SUCCESS = "Заявка привязана к существующему пользователю."

LINK_ACTION = "Привязка начата."

LINK_CONFLICT = "У существующего пользователя уже есть такой platform id."

LINK_COMMAND_USAGE = "Использование: link <pending_row_id> <existing_row_id>"

APPROVE_COMMAND_USAGE = "Использование: approve <row_id>"

CORRECT_COMMAND_USAGE = "Использование: correct <row_id> <исправленное имя>"

REJECT_COMMAND_USAGE = "Использование: reject <row_id>"

APPROVE_ACTION = "Заявка одобрена."

CORRECT_FLOW_STARTED = "Исправление имени начато."

CORRECT_PROMPT = "Отправь исправленное имя одним сообщением. После этого заявка будет одобрена."

CORRECT_ACTION = "Имя исправлено, заявка одобрена."

EMPTY_CORRECTED_NAME = "Исправленное имя не должно быть пустым."

REJECT_ACTION = "Заявка отклонена."

REQUEST_NOT_FOUND = "Заявка не найдена."

REQUEST_ALREADY_APPROVED = "Заявка уже одобрена."

PROFILE_LINK_LABEL = "Профиль"
