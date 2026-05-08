from enum import Enum


class UserText(Enum):
  BOT_INFO = (
    "Привет! Я бот покерного приложения.\n\n"
    "Я помогаю проводить покерные игры и принимать ставки.\n\n"
    "Чтобы начать пользоваться моими функциями, тебе нужно зарегистрироваться."
  )
  REGISTRATION_PLAYED_BEFORE = "Ты раньше играл с нами?"
  REGISTRATION_EXISTING_ROW_ID_PROMPT = (
    "Найди себя в списке. "
    "Я создам pending-заявку с этим же именем и сразу сообщу админу, к какой записи ее нужно привязать."
  )
  REGISTRATION_PLATFORM_CANDIDATES = "Вот игроки, у которых еще не привязана эта платформа:"
  REGISTRATION_PLATFORM_CANDIDATES_EMPTY = (
    "Сейчас не вижу approved-игроков без привязки этой платформы."
  )
  REGISTRATION_NEW_NAME_PROMPT = (
    "Введи свое имя в любом виде. "
    "Если понадобится, администратор потом поправит его перед подтверждением."
  )
  REGISTRATION_EXIST = "Ты уже зарегистрирован."
  REGISTRATION_WAIT = "Заявка отправлена. После её рассмотрения тебе придёт сообщение."
  REGISTRATION_LINK_WAIT = (
    "Я отправил заявку админу. Если найдется твоя старая запись, он привяжет этот аккаунт."
  )
  REGISTRATION_APPROVED = "Ты успешно зарегистрирован!"
  REGISTRATION_NOT_APPROVED = "Ты не зарегистрирован! Спроси у админа почему."
  REGISTRATION_PENDING = "Твоя заявка уже ожидает подтверждения администратора."
  REGISTRATION_EMPTY_NAME = "Имя не должно быть пустым."
  REGISTRATION_INVALID_ROW_ID = "Нужно выбрать игрока из списка."
  REGISTRATION_CHOOSE_FROM_LIST = "Не нашел такую запись в списке. Выбери игрока из списка."
  REGISTRATION_READ_ERROR = "Не удалось прочитать данные. Попробуй ещё раз."
  REGISTRATION_ID_ERROR = "Не удалось определить Telegram ID."
  REGISTRATION_SIMILAR_USERS_FOUND = "Похоже, в базе есть похожие игроки:"
  REGISTRATION_SIMILAR_USERS_NOT_FOUND = (
    "Похожих игроков в базе не нашел, но заявку админу все равно отправил."
  )
  REGISTRATION_OPTIONAL_DETAILS_PROMPT = (
    "Если хочешь, укажи свои банк и номер телефона. "
    "В случае твоей победы по этим данным тебе быстрее переведут деньги."
  )
  REGISTRATION_OPTIONAL_BANK = "🏦 Банк"
  REGISTRATION_OPTIONAL_PHONE = "☎️ Телефон"
  REGISTRATION_OPTIONAL_SKIP = "🥷 Не хочу указывать"
  REGISTRATION_BANK_PROMPT = "Введи название банка."
  REGISTRATION_PHONE_PROMPT = "Введи номер телефона, начиная с 7."
  REGISTRATION_BANK_SAVED = "Банк сохранен. Можешь добавить телефон или завершить."
  REGISTRATION_PHONE_SAVED = "Телефон сохранен. Можешь добавить банк или завершить."
  REGISTRATION_PHONE_INVALID = "Номер должен начинаться с 7 и содержать 11 цифр."
