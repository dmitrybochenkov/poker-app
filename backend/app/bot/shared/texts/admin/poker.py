"""Admin bot poker texts."""

POKER_STARTED = "Покер уже идет - нельзя начать новый."

POKER_PARAMS_EMPTY = "Нет параметров покера. Сначала добавь параметры."

POKER_PARAMS_CHOOSE = "Выбери параметры для старта покера:"

POKER_START_SUCCESS = "Покер успешно запущен."

POKER_FINISH_SUCCESS = "Покер завершен."

POKER_ACTIVE_NOT_FOUND = "Активный покер не найден."

POKER_PLAYERS_EMPTY = "В активном покере пока нет игроков."

POKER_CASHIER_CHOOSE = "Выбери кассира:"

POKER_CASHIER_SET = "Кассир назначен."

POKER_ADD_PLAYER_CHOOSE = "Выбери игрока для добавления в активный покер:"

POKER_ADD_PLAYER_EMPTY = "Нет доступных игроков для добавления."

POKER_ADD_PLAYER_SUCCESS = "Игрок добавлен в активный покер."

POKER_REMOVE_PLAYER_CHOOSE = "Выбери игрока для удаления из активного покера:"

POKER_REMOVE_PLAYER_SUCCESS = "Игрок удален из активного покера."

POKER_UNBAN_PLAYER_CHOOSE = "Выбери игрока для разрешения повторного входа в активный покер:"

POKER_UNBAN_PLAYER_EMPTY = "Нет игроков с запретом повторного входа."

POKER_UNBAN_PLAYER_SUCCESS = "Игроку снова разрешен вход в активный покер."

POKER_BUYIN_CHOOSE = "Выбери игрока для закупа:"

POKER_BUYIN_CORRECT_CHOOSE = (
    "🔧 Выбери игрока для корректировки закупов.\n❗ Для удаления нужно пользоваться другой кнопкой"
)

POKER_BUYIN_EMPTY = "Некого закупать: в активном покере нет игроков."

POKER_BUYIN_CASHIER_REQUIRED = "Закупы закрыты, пока не назначен кассир."

POKER_BUYIN_PROMPT = "Выбери количество закупов:"

POKER_BUYIN_SAVED = "Закуп сохранен."

POKER_BUYIN_INVALID = "Нужно ввести целое число больше 0."

POKER_CASHOUT_CHOOSE = "Выбери игрока для ввода фишек:"

POKER_CASHOUT_EMPTY = "Нет завершенного покера, готового к вводу фишек, или в нем нет игроков."

POKER_CASHOUT_PROMPT = "Введи количество фишек (целое число >= 0)."

POKER_CASHOUT_SAVED = "Фишки сохранены."

POKER_CASHOUT_INVALID = "Нужно ввести целое число 0 или больше."

POKER_CHIPS_WAITING = "Ожидаем ввод фишек от игроков:\n{players}"

POKER_CHIPS_ALL_ENTERED = "Все игроки ввели фишки."

POKER_CHIPS_FOR_WHO = "Кому вводим {chips} фишек?"

POKER_CALC_BALANCE_MISMATCH = (
    "Проверка фишек не сошлась.\nВ игре: {in_game}\nВведено: {entered}\nРазница: {diff}"
)

POKER_CALC_SUCCESS = "Покер рассчитан."
