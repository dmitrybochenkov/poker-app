from enum import Enum


class UserText(Enum):
  BOT_INFO = (
    "Привет👋, я покер-бот🤖.\n\n"
    "Я помогаю проводить покерные игры: считаю закупы🏦 и переводы💲 победителям💍 от проигравших❌.\n\n"
    "Я веду статистику игр с 2023 года, а также умею принимать ставки на результаты покерных игр.\n\n"
    "Чтобы начать пользоваться моими функциями, тебе нужно зарегистрироваться."
  )

  REGISTRATION_PLAYED_BEFORE_Q = "Ты раньше играл с нами?"
  REGISTRATION_PLAYED_BEFORE_Y = "Найди себя в списке. Если тебя нет - жми Меня нет в списке."
  REGISTRATION_PLATFORM_CANDIDATES = "Вот игроки, у которых еще не привязана эта платформа:"
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
  REGISTRATION_IN_PROGRESS = "Мы уже начали регистрацию. Продолжай по предыдущему сообщению."
  REGISTRATION_EMPTY_NAME = "Имя не должно быть пустым."
  REGISTRATION_CHOOSE_FROM_LIST = "Не нашел такую запись в списке. Выбери игрока из списка."
  REGISTRATION_READ_ERROR = "Не удалось прочитать данные. Попробуй ещё раз."
  REGISTRATION_ID_ERROR = "Не удалось определить Telegram ID."
  REGISTRATION_OPTIONAL_DETAILS_PROMPT = (
    "Если хочешь, укажи свои банк и номер телефона. "
    "В случае твоей победы по этим данным тебе быстрее переведут деньги."
  )
  REGISTRATION_OPTIONAL_BANK = "🏦 Банк"
  REGISTRATION_OPTIONAL_PHONE = "☎️ Телефон"
  REGISTRATION_OPTIONAL_SKIP = "🥷 Не хочу указывать"
  REGISTRATION_PLATFORM_PROMPT = "Выбери платформу для уведомлений:"
  REGISTRATION_PLATFORM_TG = "👦 Телеграм"
  REGISTRATION_PLATFORM_VK = "👴 ВК"
  REGISTRATION_BANK_PROMPT = "Введи название банка."
  REGISTRATION_PHONE_PROMPT = "Введи номер телефона, начиная с 7."
  REGISTRATION_PHONE_INVALID = "Номер должен начинаться с 7 и содержать 11 цифр."
  START_POKER = "Начало покера. Желающим принять участие в игре пора заходить в покер рум!"
  STATUS_NEED_REGISTRATION = "Сначала зарегистрируйся."
  STATUS_PENDING = "Твоя заявка еще на рассмотрении у администратора."
  STATUS_ROOM_CLOSED = "Сейчас покер рум закрыт."
  STATUS_ROOM_NOT_ADDED = "Ты не добавлен в покер рум! Спроси у админа почему."
  STATUS_BUYINS = "🏦 Закупы: {buyins}"
  ROOM_JOINED = "Добро пожаловать в покер рум!"
  ROOM_ALREADY_JOINED = "Ты уже добавлен в покер рум."
