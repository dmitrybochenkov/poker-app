# Аудит ботов — 22.09.2026

Нормативные правила для нового backend-кода и план первой вертикальной миграции Start Betting описаны в [`ARCHITECTURE.md`](ARCHITECTURE.md). Они применяются инкрементально и не требуют массового исправления перечисленного ниже legacy-кода.

## Vertical migration status

- **Start Betting migrated (23.09.2026).** Telegram и VK разрешают external identity в `User.row_id` и вызывают общий `StartBettingUseCase`.
- Use case повторно проверяет approved admin, валидирует poker state, выполняет атомарный conditional update и владеет commit. Legacy `PokerRepository.start_betting()` оставлен для немигрированных callers.
- Очистка room-status сообщений и TG/VK delivery выполняются отдельной post-commit orchestration. Она получает canonical user IDs, сохраняет `notification_platform`, общий `Text.user.START_BETTING`, platform keyboards и best-effort delivery.
- Из Start Betting handlers удалены business validation, mutation, commit, recipient queries, broadcast loops и cross-platform imports. Routing identifiers и порядок сохранены.
- Отложено: гарантированная доставка/outbox и persistence in-memory room-status IDs. Concurrent open защищён conditional update без новой locking/schema architecture.
- **Start Poker migrated (23.09.2026).** Telegram и VK разрешают external identity в `User.row_id`; `StartPokerUseCase` повторно проверяет approved admin, параметры и отсутствие активной игры.
- Создание Poker и PokerData инициатора теперь составляет одну транзакцию и один commit. Guarded insert предотвращает повторный и concurrent start в текущей SQLite persistence model.
- Use case возвращает canonical IDs всех approved пользователей. Отдельный post-commit adapter сохраняет legacy-семантику: пользователь с обеими привязками получает TG и VK сообщения независимо от `notification_platform`; одинаковый текст берётся из `Text.user.START_POKER`, клавиатуры остаются platform-specific.
- Start Poker handlers вынесены в отдельные transport modules и больше не содержат mutation, recipient query или cross-platform delivery. Ошибка delivery логируется best effort и не меняет успешный результат committed операции.
- Общий для двух реальных flows контракт уведомителя вынесен в `CanonicalRecipientNotifier`; `StartBettingFlow` сохраняет совместимый alias. Универсальный notification framework, event bus и общий base flow не вводились.
- Отложено: строгая межпроцессная гарантия единственной активной игры для будущей MVCC СУБД потребует schema constraint или locking strategy; transactional outbox и повторная доставка также не вводились.

## Срочно

| Приоритет | Наблюдение | Действие |
| --- | --- | --- |
| P0 | VK callback-сервер группы `236791730` (сервер `1`) указывает на `https://poker-u-molodogo.dedyn.io/webhooks/vk`. Этот домен не разрешается в DNS из среды проверки. Настроенный `PUBLIC_BASE_URL` ведёт на `https://poker-u-molodogo.dimension-x.dedyn.io`: `/api/health` отвечает `200`, POST подтверждения отвечает `200` и возвращает ожидаемый токен. Секрет callback-сервера совпадает с локальным, события `message_new` и `message_event` включены. | После согласования изменить URL существующего callback-сервера в VK на адрес приложения и проверить получение тестового события. Статус `ok` в настройках VK сам по себе не доказал доступность старого домена. |
| P0 | Telegram-старт ставок завершался `NameError`: после получения `approved_users` код обращался к несуществующим `tg_user_ids` и `vk_user_ids`. Изменение `is_bettable` уже было сохранено до ошибки, поэтому повторный старт отвечал «ставки уже открыты» без рассылки. | Исправлено получение адресатов по платформам; добавлен тест. Для уже открытых игр нужна отдельная операция повторной рассылки или журнал доставки. |
| P0 | Старт покера Telegram обращался к несуществующему `approved_users` после сохранения игры. | Исправлено; post-save TG/VK paths и canonical-recipient adapter покрыты regression tests. |
| P1 | Ошибка отправки одному получателю прерывала всю рассылку старта ставок после сохранения состояния игры. | Обе рассылки теперь продолжаются после ошибки конкретного адресата и пишут ошибку в лог. Для гарантированной доставки нужен outbox с повторными попытками. |
| P1 | У VK-администратора создание/отмена опроса вызывали несуществующую функцию удаления сообщения; статус комнаты использовал неимпортированную клавиатуру. | Исправлено. Отмена опроса покрыта тестом. |
| P1 | Проверка `vk_secret_key` пропускала запросы, в которых поле `secret` отсутствовало. | Исправлено; добавлен тест отказа с `403`. |

## Границы слоёв

1. `application/use_cases` напрямую импортирует SQLAlchemy-модели и конкретные `db.repositories` как минимум в 13 файлах. Это привязывает сценарии к хранению данных. Сначала стоит выделить интерфейсы для ключевых сценариев покера, ставок и регистрации; массовую замену в одном проходе делать не следует.
2. Многие обработчики ботов напрямую импортируют `db` и совмещают распознавание события, бизнес-решение, транзакцию, построение текста и сетевую отправку. Start Betting и Start Poker уже мигрированы; среди ближайших рискованных legacy-сценариев остаются завершение покера и платежи.
3. `api/http/vk_webhook.py` содержит логику `/start`, управление состоянием пользователя, доступ к репозиторию и выбор клавиатуры. HTTP-слой должен передавать событие в VK-адаптер, а ответ формироваться там.
4. В немигрированных handlers ещё есть Telegram → VK и VK → Telegram presentation imports. Start Betting и Start Poker устранили их внутри своих transport modules через post-commit adapters.
5. Legacy repository methods продолжают вызывать `commit()` внутри методов; ещё часть транзакций завершается в обработчиках. Для Start Betting и Start Poker добавлены точечные non-committing mutations, а use cases владеют commit. Остальные границы переносятся только вместе с соответствующим vertical flow.
6. Словари состояния VK и ID сообщений находятся в памяти процесса. Перезапуск или несколько воркеров теряют/разделяют состояние непредсказуемо. Для регистрации, черновиков ставок и уведомлений нужен общий persistent storage.

## Нейминг и сопровождение

- Все 138 числовых имен VK `_event_0_XX` / `_text_1_XX` заменены именами по `action`, кнопке или ожидаемому состоянию. Неопределенных назначений и оставленных числовых имен нет. Тела функций и порядок вызовов не менялись.
- Из `telegram/handlers/user/common.py` и `vk/handlers/user/common.py` вынесены тематические группы опросов (`poll_helpers.py`) и платежных подтверждений (`receipts_helpers.py`). Существующие импорты обработчиков сохранены через реэкспорт. Остальные общие функции, в том числе сценарии с БД и межплатформенной рассылкой, пока остаются: их безопасное разделение требует более широких тестов и изменения архитектурных границ.
- `Buttons.bettingInfo` и `Buttons.pokerInfo` нарушают единый стиль имён `snake_case`; изменение публичных атрибутов требует совместимых алиасов.
- Динамические тексты, ранее встроенные в обработчики, вынесены в тематические файлы `app/bot/shared/texts/inline/`. Имена фрагментов `_PART_N` следует постепенно заменить смысловыми шаблонами при работе над конкретным сценарием.

## Что проверено

- Приложение импортируется, `compileall` проходит.
- Прежний `test_telegram_handler_order` сравнивал отсортированные списки и **не проверял порядок**. Теперь он сверяет точную последовательность отдельно для `admin_router.message`, `admin_router.callback_query`, `user_router.message` и `user_router.callback_query`; перестановка двух обработчиков меняет результат теста.
- `test_vk_dispatch_order` фиксирует порядок вызовов в четырех VK маршрутах: admin `message_event`, admin text, user `message_event`, user `message_new`. Он проверяет AST исходного routing и обнаруживает перестановку вызовов без тяжелых mocks каждого обработчика.
- Локальные тесты также проверяют публичные импорты VK, обе рассылки старта ставок, старт покера, отмену VK-опроса и проверку VK-секрета.
- Start Poker regression suite проверяет authorization, invalid params без mutation, один commit для игры и инициатора, canonical approved recipients, повторный и concurrent start, post-commit ordering, best-effort dual-platform delivery, сохранение committed state при сбое notifier и отсутствие cross-presentation imports. Отдельный VK regression test защищает прежний post-save `approved_users` failure path.
- Во время review найден `NameError` в `services/buyins_chart.py`: генератор графика истории обращался к отсутствующему `chart_type` при непустых данных. Сначала добавлен падающий регрессионный тест, затем исправление отдельным коммитом.
- Финальный прогон после миграции Start Poker: 44 теста проходят, `compileall` проходит, `from app.main import app` отвечает `OK`, полный `ruff F821` проходит. Полный Ruff всё ещё сообщает 486 оставшихся замечаний: 425 `E501`, 54 `I001`, 5 `F841`, 2 `F401`. Их массовое исправление в эту задачу не входило.
- Токен VK отвечает на read-only запрос API. Адреса callback-сервера, секрет и статус событий проверены без вывода секретов. Текущий адрес приложения принял POST подтверждения. Отправка пользователям и изменение настройки VK в ходе аудита не выполнялись.
- Полной проверки реальной доставки не было: она требует исправления внешнего callback URL и тестового события из VK.
