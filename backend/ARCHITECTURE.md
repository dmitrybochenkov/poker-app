# Backend Architecture Contract

> **This document is normative for new code and migrated flows.**
> **Existing legacy code may violate these rules.**
> **Do not mass-refactor legacy code solely to comply with this document.**

Этот документ задаёт обязательные правила для нового backend-кода и для сценария после его миграции. Он не объявляет весь текущий код соответствующим этим правилам и не является основанием для массовой переделки legacy-кода. Миграция выполняется постепенно, вертикальными срезами по Strangler Pattern: рядом могут существовать legacy flows и уже мигрированные flows.

## 1. Назначение и границы

Telegram, VK и HTTP/WebApp — presentation/transport interfaces одного приложения. Они принимают разные внешние форматы, но не должны содержать разные копии одного бизнес-сценария.

```text
Telegram ─┐
VK ───────┼── Presentation → Application → Persistence / Domain
WebApp ───┘                         │
                                   └── External ports / adapters
```

Добавление транспорта не должно требовать копирования бизнес-правил. WebApp пока не мигрируется и может иметь собственные UI labels/messages.

### Правило зависимости

Зависимости направлены внутрь:

- presentation знает application;
- application координирует бизнес-операцию и persistence dependencies;
- repositories знают ORM и SQLAlchemy;
- adapters знают Telegram/VK/network API;
- application не знает aiogram, FastAPI request objects, VK events, keyboards или bot API.

Для нового и мигрированного кода запрещены зависимости `telegram → vk presentation` и `vk → telegram presentation`. Общие действия размещаются ниже transport layer или за application port.

## 2. Фактическая архитектура repository

### Что уже существует и пригодно для развития

| Область | Фактическое состояние | Решение |
| --- | --- | --- |
| Application | Именованные use cases находятся в `app/application/use_cases/`: регистрация, управление игроками, старт покера, ставки, статистика | Сохранять подход «одна осмысленная операция — один use case» |
| Application errors | `app/application/exceptions.py` содержит ошибки регистрации и пользователей | Расширять точечно, только под реальные business outcomes |
| Persistence | Конкретные repositories принимают `AsyncSession` и инкапсулируют запросы | Переиспользовать; не создавать параллельный набор interfaces |
| Session creation | `SessionFactory` и FastAPI dependency `get_db_session()` уже существуют | Использовать текущий SQLAlchemy composition; DI framework и Unit of Work сейчас не нужны |
| Identity storage | `User.row_id` — canonical internal ID; Telegram/VK IDs хранятся как внешние привязки | В application передавать `row_id`, внешнюю identity разрешать до business operation |
| Shared texts | `app/bot/shared/texts/{user,admin}/` уже организован по смысловым областям; фасад `Text` сохраняет совместимость | Развивать эту структуру; одинаковые TG/VK тексты хранить один раз |
| Platform adapters | `telegram/runtime.py`, `vk/api.py`, platform keyboards и notification helpers уже инкапсулируют часть API-вызовов | Использовать внутри transport adapters, не импортировать из application |
| Regression coverage | Есть точные Telegram handler-order tests, source-level VK dispatch-order tests и Start Betting regression tests | Сохранить при миграции; добавить независимые use-case tests |

### Конфликты с целевым контрактом

1. Bot handlers напрямую создают `SessionFactory`, собирают repositories, управляют бизнес-состоянием и выполняют cross-platform delivery.
2. Telegram handlers импортируют VK API/keyboards, а VK handlers импортируют Telegram runtime/keyboards.
3. Большинство repository mutation methods сами вызывают `commit()`. Поэтому одна бизнес-операция не всегда имеет единый transaction boundary.
4. Часть application use cases импортирует конкретные repositories и ORM models. Для текущего размера это допустимый pragmatic coupling, но application не должен импортировать transport types.
5. `BroadcastUseCases` в `application/use_cases/poker/broadcast.py` — незавершённая заглушка с `NotImplementedError`; это не рабочая abstraction и не основа для новой миграции.
6. `api/http/vk_webhook.py` содержит transport dispatch вместе с identity lookup, состоянием диалога и выбором клавиатур. WebApp и webhook cleanup не входят в первый срез.
7. Исторические poker records и расчёты местами используют `player_name`. Имя не является stable identity; это отдельный legacy debt, который этим контрактом не исправляется автоматически.
8. In-memory dictionaries для VK state и IDs закреплённых сообщений не устойчивы к рестарту или нескольким workers.

## 3. Presentation contract

Handler/controller после миграции может:

- принять platform-specific event/request;
- извлечь primitives;
- выполнить проверку структуры transport payload;
- разрешить external identity в canonical internal actor ID;
- собрать application input;
- вызвать use case;
- сопоставить typed outcome/error с текстом, keyboard и transport response.

Handler/controller после миграции не может:

- напрямую менять ORM business state;
- координировать несколько repositories;
- владеть business transaction;
- вычислять бизнес-правила;
- выполнять cross-platform delivery;
- считать скрытую кнопку достаточной авторизацией.

Platform-specific keyboards остаются в `bot/telegram/keyboards.py` и `bot/vk/keyboards.py`. Presentation formatter превращает application data в пользовательский текст. Бизнес-вычисления formatter не выполняет.

## 4. Application use cases

Предпочтительны явные операции: `StartBettingUseCase`, `PlaceBetUseCase`, `FinishPokerUseCase`, `ApproveRegistrationUseCase`, `CorrectBuyinUseCase`.

- Один use case представляет одну осмысленную бизнес-операцию.
- Getter без бизнес-правил не требует отдельного use case.
- `BaseUseCase`, manager/service wrapper вокруг одной функции и DTO для каждого вызова запрещены без конкретной потребности.
- Input/output используют primitives, internal IDs и небольшие dataclasses только когда они проясняют контракт.
- Application errors описывают бизнес-смысл, например `BettingAlreadyOpenError`, и не содержат Telegram/VK текста.
- Server/application side повторно проверяет authorization для чувствительной операции, даже если presentation уже сделал раннюю UX-проверку.

## 5. Identity and authorization

Canonical identity — `User.row_id`. `telegram_id`, `vk_id`, username и display name не используются как business identity.

Рекомендуемый путь запроса:

1. transport проверяет форму запроса;
2. identity resolver находит `User` по platform ID;
3. в use case передаётся `actor_user_id=User.row_id`;
4. use case проверяет approval/role, необходимые для операции.

На первом срезе identity resolver может быть тонкой presentation dependency поверх существующего `UserRepository`. Общий `IdentityResolver` port следует вводить только если повторение между транспортами станет самостоятельной проблемой.

WebApp authentication/authorization содержит legacy debt. Этот документ требует server-side authorization для будущих мигрированных операций, но не запускает переделку WebApp auth.

## 6. Repositories and transactions

Repository выполняет persistence operations: get/find/list, add, update/delete и `flush()` при необходимости. Бизнес-правила в repository не помещаются. Generic `BaseRepository` не нужен.

Целевой transaction boundary охватывает целый use case. Repository не должен `commit()` внутри новой или мигрированной операции. На текущем этапе use case может прямо использовать `AsyncSession`:

```python
async with session.begin():
    # validate, read and mutate through repositories
```

Это осознанный pragmatic выбор. `AbstractUnitOfWork`, `SqlAlchemyUnitOfWork`, Protocol для каждого repository и DI framework сейчас не вводятся. Существующие repository methods с `commit()` остаются legacy; их меняют точечно при миграции flow, сохраняя совместимость других callers.

Порядок side effects:

```text
validate → mutate DB → commit → external side effects
```

DB transaction нельзя держать открытой во время Telegram/VK/network delivery. Ошибка уведомления после commit не откатывает корректное business state. Для широковещательных сообщений текущая семантика — best effort: ошибка одного адресата логируется и не останавливает остальных. Transactional outbox возможен позже, если появится требование гарантированной доставки; сейчас он не вводится.

## 7. External notifications

Application выражает business intent (`betting started`, `registration approved`, `poker finished`), а adapter выбирает API, destination, keyboard и platform formatting.

Для первого мигрированного cross-platform flow нужен один узкий application port по событию, а не event bus и не универсальный notification framework. Port не должен принимать Telegram/VK keyboard или transport object. Его composite adapter может делегировать platform adapters и возвращать delivery report либо реализовывать best effort внутри.

Существующие `telegram/notifications.py` и `vk/notifications.py` полезны как примеры platform delivery, но сейчас ориентированы на регистрацию и зависят от platform types. Их не следует превращать в общий application service. `BroadcastUseCases` следует считать legacy-заглушкой и удалить, когда подтверждено отсутствие callers, вместо реализации второго конкурирующего механизма.

## 8. User-facing texts

Принцип: **shared by default, platform-specific by exception**.

- Общие тексты организуются по business domains: `betting`, `poker`, `polls`, `registration`, `players`, `buyins`, `statistics`, `common`.
- Текущий `bot/shared/texts/user/betting.py` уже является правильным доменным местом для `START_BETTING`.
- Фасад `Text.user` / `Text.admin` допустим для совместимости.
- Новый текст получает semantic name. Имена `TEXT_02_PART_1` и подобные не продолжаются.
- Platform-specific text допустим, если различие вызвано UX/API. Keyboards всегда platform-specific.
- WebApp может иметь собственные labels и может переиспользовать shared text, когда смысл и presentation совпадают.

Массовая миграция существующего `inline/telegram` и `inline/vk` в этом этапе запрещена.

## 9. Testing contract

Для каждого нового или мигрированного business flow нужны:

- use-case tests без Telegram/VK runtime;
- success path;
- meaningful invalid state/error path;
- проверка отсутствия unintended mutation при отказе;
- side-effect behavior, если оно часть сценария;
- transport wiring/regression test там, где wiring существенно.

Существующие Telegram registration-order и VK dispatch-order tests сохраняются. End-to-end test на каждую мелкую функцию не требуется.

## 10. Incremental migration rules

1. Выбрать один flow и зафиксировать фактическое поведение тестами.
2. Вынести business operation в application, переиспользуя текущие repositories.
3. Сделать transaction boundary единым только для этого flow.
4. Добавить минимальный port/adapter только для необходимого external side effect.
5. Переключить TG/VK entry points на один use case.
6. Удалить дублированную orchestration из этих handlers.
7. Не затрагивать соседний legacy code без необходимости.

Целевое направление структуры, без создания пустых каталогов:

```text
application/
    use_cases/
    ports/                    # только реально используемые ports
bot/
    shared/texts/
    telegram/{handlers,formatters,keyboards}
    vk/{handlers,formatters,keyboards}
api/http/
db/{models,repositories}
infrastructure/              # adapters только при появлении реального port
```

---

# CHANGE SAFETY CONTRACT

Этот раздел нормативен для всех будущих задач Codex в repository. Его цель — выбирать проверки по реальному риску и сохранять либо улучшать защиту затронутого поведения. Количество строк, файлов и субъективная простота реализации не определяют риск.

## Task grades

| Grade | Риск и типичные изменения | Baseline verification |
| --- | --- | --- |
| **G0 — Documentation / non-runtime** | Markdown, comments, design notes и текст, не используемый runtime | Production tests обычно не нужны; проверить content, diff и status |
| **G1 — Local low-risk** | Shared user-facing text без control-flow change, formatter, изолированный pure helper, локальный presentation mapping, readability refactor хорошо покрытого компонента | Определить affected tests и запустить direct targeted tests; compile/static check — только когда полезен |
| **G2 — Functional/domain change** | Handler behavior, use case, repository query/mutation, notification behavior, validation, bugfix, миграция одного vertical flow, ограниченно используемый shared component | Test Impact Analysis, regression/specification или characterization coverage, direct и related-domain tests, нужные transport/repository и compile/import/static checks |
| **G3 — High-risk / architectural / shared-boundary** | Auth, identity, transactions, routing, schema, startup, concurrency, public API, shared TG/VK/WebApp infrastructure, крупная migration или dependency-boundary change | Все проверки G2, full pytest, compileall, application import smoke, relevant static, migration, security и structural checks |

G0 перестаёт быть G0, если documentation task меняет executable documentation, generated runtime artifact или configuration, которую читает приложение.

## Automatic grade escalation

Задача автоматически получает минимум **G3**, даже при diff в несколько строк, если затрагивает:

- authentication или authorization;
- canonical identity mapping;
- transaction ownership или commit semantics;
- database schema или Alembic migrations;
- routing либо handler registration/dispatch order;
- shared cross-platform infrastructure;
- application startup или runtime configuration;
- concurrency или locking;
- security boundary;
- public API compatibility.

При нескольких областях применяется самый высокий grade. Маленький diff не является основанием снизить grade.

## Declaration before implementation

До первого изменения production code рабочий план должен содержать:

```text
TASK GRADE: Gx

Reason:
...

Affected components:
...

Expected blast radius:
...

Required test scope:
...
```

Отдельное подтверждение пользователя не требуется, если сама задача уже одобрена. При обнаружении большего blast radius grade повышается вместе с test scope. Понижение во время реализации требует явного объяснения.

Каждая будущая code task начинается с последовательности:

1. прочитать `ARCHITECTURE.md`;
2. определить `TASK GRADE`;
3. выполнить Test Impact Analysis;
4. определить необходимый safety net;
5. только после этого менять production code.

## Test Impact Analysis

Перед production change определить и записать в рабочем плане:

- непосредственно изменяемый код;
- его callers и consumers;
- shared dependencies;
- затронутые business flows;
- transport и persistence boundaries;
- external side effects;
- существующие tests этих областей.

На этой карте строится минимально достаточный набор проверок. Цель — получить достаточную уверенность для фактического blast radius, а не запустить максимальное число тестов.

## Characterization before refactor

При refactor существующего поведения порядок обязателен:

```text
inspect current behavior
→ identify behavior contract
→ add characterization test where coverage is missing
→ confirm the test passes on the old implementation
→ refactor
→ confirm the same test still passes
```

Characterization test фиксирует непосредственно затронутое observable behavior. Его нельзя писать после refactor так, чтобы он лишь повторял новую внутреннюю реализацию. Покрывать весь legacy module не требуется.

## Bugfix contract

Для воспроизводимого дефекта:

```text
reproduce
→ write a failing regression test
→ confirm the expected failure reason
→ implement the minimal fix
→ confirm the regression test passes
→ run the impacted test set
```

Сначала исправить bug, а затем написать тест, который никогда не наблюдал failure, нельзя. Если автоматическое воспроизведение неразумно или невозможно, нужно объяснить причину и выбрать проверяемый альтернативный verification method.

## New behavior contract

Specification test нового business behavior описывает observable outcome:

```text
given state → when operation → then state / result / side effect
```

По возможности сначала пишется тест и подтверждается его осмысленный failure, затем реализация. Для тривиального wiring/config change не нужна искусственная red-test ceremony, если она не добавляет уверенности.

## What tests should observe

Предпочтение отдаётся business/public behavior, а не private implementation details. Без необходимости тест не должен фиксировать:

- порядок вызова private helpers;
- точное количество внутренних repository calls;
- структуру функции;
- детали реализации, не являющиеся контрактом.

Исключение — случаи, где порядок сам является публичным или safety contract, например Telegram handler registration и VK dispatch order.

Mocks ставятся преимущественно на external boundaries: Telegram API, VK API, Google/external API, filesystem/network, clock и randomness. Не следует автоматически mock every internal layer: тест должен проходить через реально изменяемый код.

## Existing tests are contract

Существующие passing tests считаются частью behavioral safety net. Если production change ломает тест, сначала классифицировать причину:

- **A. Production regression** — поведение нужно исправить, expectation сохраняется;
- **B. Intentional behavior change** — изменение прямо требуется задачей, старый contract осознанно заменяется.

Нельзя автоматически менять expected value, ослаблять assertion, удалять тест, добавлять `skip`/`xfail` или менять fixture только ради green suite. Для refactor expectations не меняются. При intentional behavior change в отчёте явно указываются старый и новый contracts.

## Tests must not be gamed

Запрещено получать green suite путём:

- удаления failing tests;
- `skip` или `xfail`;
- ослабления meaningful assertions;
- catch-all exception swallowing;
- чрезмерного mocking, обходящего изменённый path;
- изменения fixture так, чтобы problematic path больше не выполнялся.

Если существующий test ошибочен, это отдельно доказывается через фактический contract и описывается в отчёте.

## Equal or better safety

> Code touched by a task should leave the repository with equal or better behavioral regression protection than before.

Если задача меняет важное ранее непокрытое поведение, добавляется focused coverage именно для него. Это не требует повышать coverage всего файла, тестировать unrelated legacy или исправлять соседние flows.

## Test scope baseline

### G0

- runtime pytest по умолчанию не запускается;
- проверяются content/document validity, diff и status.

### G1

- direct targeted tests;
- relevant formatter/helper/text tests;
- optional compile/static check, когда он проверяет реальный риск.

### G2

- direct targeted tests;
- related-domain tests;
- regression/specification/characterization tests;
- relevant transport/repository tests;
- compile/import/static checks по результатам impact analysis.

Full pytest для G2 не обязателен, если impact area надёжно ограничена. В итоговом отчёте нужно объяснить, почему выбранного набора достаточно.

### G3

- все применимые G2 checks;
- full pytest;
- `compileall`;
- application import/startup smoke;
- relevant static checks;
- migration checks при schema changes;
- security и structural/routing checks, когда затронуты соответствующие boundaries.

Это baseline, а не rigid command table. Test Impact Analysis может добавить проверки.

## Fast feedback

Во время реализации проверки расширяются постепенно:

```text
single regression/specification test
→ affected test module
→ related domain tests
→ broader checks required by grade
```

Full pytest не запускается после каждой небольшой правки. Для G3 он обязателен один раз на финальном проверяемом состоянии, а также повторно только после последующих изменений, способных повлиять на результат.

## Test organization and naming

- Новые tests размещаются в существующей test organization проекта.
- Параллельная test architecture без необходимости не создаётся.
- Имя описывает behavior: `test_start_betting_rejects_non_admin`, а не `test_case_7` или `test_execute_works`.
- Fixtures и helpers вводятся только при реальном повторении и не должны скрывать сценарий.

## Refactor, behavior change and bugfix

- **REFACTOR:** observable behavior сохраняется.
- **BEHAVIOR CHANGE:** observable contract намеренно меняется.
- **BUGFIX:** неправильное поведение заменяется ожидаемым и закрепляется regression test.

Behavior change нельзя называть refactor. Когда возможно, structural refactor и behavior change оформляются отдельными commits.

## Commit contract

Для нетривиальной работы предпочтительны логические commits:

```text
characterization/regression tests
→ implementation/refactor
→ wiring
→ docs
```

Для bugfix предпочтительны отдельный failing regression-test commit и следующий fix commit. Unrelated cleanup в эти commits не включается.

## Final report contract

Для каждой G1–G3 code task итоговый отчёт содержит:

```text
TASK GRADE:
Gx

CHANGED:
...

TEST IMPACT:
...

TESTS ADDED/CHANGED:
...

TESTS RUN:
exact scopes/commands and results

NOT RUN:
broader tests and why they were not required

BEHAVIOR:
preserved and intentionally changed behavior

DEFERRED:
relevant debt deliberately outside scope
```

Для G3 дополнительно указываются full-suite, compile/static/import results и применимые migration/security/routing checks.

## No unrequested cleanup

Unrelated failing test, lint debt, uncovered legacy code или архитектурное нарушение не дают автоматического разрешения исправлять их в текущей задаче. Если такой долг блокирует verification, он описывается отдельно; выполняется только минимально необходимое изменение после явного обоснования.

---

# First Vertical Migration: Start Betting

Раздел был создан как проверяемый design и реализован 23.09.2026. Он сохраняет исходную карту и принятые решения как reference implementation первой vertical migration.

## 11. Текущая карта Start Betting

### Entry points

**Telegram**

- Reply button `Buttons.admin_room.START_BETTING` регистрирует `start_betting()`.
- Callback `pokerstartbetting:inline` регистрирует `start_betting_inline()`.
- Оба выполняют Telegram admin guard и вызывают `_start_betting_flow(admin_tg_id=...)` из `telegram/handlers/admin/common.py`.
- Аргумент `admin_tg_id` внутри `_start_betting_flow` фактически не используется; authorization остаётся во внешних handlers.

**VK**

- Text dispatch вызывает `handle_admin_room_start_betting_text()` в `vk/handlers/admin/bets.py`.
- Inline action `poker_start_betting_inline` в `vk/handlers/admin/poker.py` повторно вызывает тот же text handler с текстом кнопки.
- Text handler сам выполняет `is_vk_admin()`.

### Reads, mutations and commit

Обе реализации выполняют одинаковую последовательность:

1. Создают `SessionFactory()`.
2. Создают `PokerRepository` и `UserRepository`.
3. Читают `PokerRepository.get_started()` — активный `Poker` вместе с `PokerParam`.
4. Проверяют `is_ready_for_chips_entering` и `is_bettable`.
5. Вызывают `PokerRepository.start_betting(poker)`.
6. Repository устанавливает `poker.is_bettable = True`, делает `session.commit()` и `refresh()`.
7. Читают `UserRepository.list_approved_tg_ids()` и `list_approved_vk_ids()`.
8. Закрывают session до любых network calls.

Единственная DB mutation — `Poker.is_bettable: False → True`. Commit скрыт внутри repository.

### Current validation and business rules

- Actor должен быть admin: Telegram guard выполняется перед helper; VK guard — внутри handler.
- Должен существовать started poker (`is_going=True`).
- Poker не должен находиться на стадии ввода фишек (`is_ready_for_chips_entering=False`).
- Ставки не должны быть уже открыты (`is_bettable=False`).

Текущий порядок ошибок: active poker missing → chips-entry state → already open. Операция идемпотентна только через отказ `already open`; повторная доставка отсутствует.

### Recipients

`UserRepository.list_approved_tg_ids()` и `list_approved_vk_ids()` выбирают только approved users с соответствующим `notification_platform` и непустым external ID, по `User.row_id`. Пользователь с обеими привязками получает сообщение только в выбранной notification platform. Legacy rows с `notification_platform=NULL` не получают это broadcast.

### External side effects

После commit обе реализации:

1. best effort unpin/delete всех сохранённых Telegram admin-room status messages;
2. best effort unpin/delete всех сохранённых VK admin-room status messages;
3. очищают `TG_ADMIN_ROOM_STATUS_MSG_IDS` и `VK_ADMIN_ROOM_STATUS_MSG_IDS`;
4. отправляют всем TG recipients общий `Text.user.START_BETTING` с Telegram `betting_keyboard`;
5. отправляют всем VK recipients тот же текст с VK `betting_keyboard`;
6. возвращают инициатору `Text.admin.BETTING_START_SUCCESS`.

Ошибка одного broadcast recipient логируется и не прерывает остальных. Ошибки удаления/pin state подавляются. Отдельная финальная отправка VK инициатору не обёрнута в best effort и может завершить webhook ошибкой уже после успешного commit. Telegram ответ инициатору также происходит после helper и может упасть после commit.

### Shared and platform-specific presentation

- `Text.user.START_BETTING` уже общий и определён семантически в `bot/shared/texts/user/betting.py`.
- Admin outcomes уже общие: `BETTING_START_SUCCESS`, `BETTING_ALREADY_OPEN`, `POKER_ACTIVE_NOT_FOUND`; chips-entry отказ сейчас использует `Text.user.FINISH_CHIPS_NOT_READY`.
- Telegram/VK betting keyboards различаются и должны остаться platform adapters.
- In-memory status message IDs — transport state; они не должны входить в business use case.

### Existing tests

- `test_telegram_start_betting_sends_both_platform_notifications` проверяет mutation call, TG/VK recipients и продолжение Telegram рассылки после ошибки одного адресата.
- `test_vk_start_betting_continues_after_one_failed_delivery` проверяет mutation call, VK best effort и ответ инициатору.
- Handler-order/dispatch-order tests фиксируют подключение Telegram и VK routes.

Эти тесты полезны как characterization tests, но подменяют repositories внутри handlers и не проверяют use case независимо от bot runtime, authorization, отсутствие mutation при каждом отказе или явную transaction boundary.

### Existing components to reuse

- `PokerRepository.get_started()` — текущий read активной игры.
- `UserRepository.get_by_telegram_id()`, `get_by_vk_id()`, `get_by_row_id()` — identity resolution и authorization data.
- Логика recipient preference в `notification_platform` и текущие list methods — семантика, которую надо сохранить.
- `SessionFactory` / `AsyncSession` — transaction composition.
- `Text.user.START_BETTING` и admin outcome texts — shared semantic texts.
- Telegram/VK `betting_keyboard` и API send functions — platform adapter details.
- Handler and dispatch regression tests — wiring protection.

Не переиспользовать как abstraction: `BroadcastUseCases` (пустая заглушка), cross-imports из TG/VK handlers и дублированные Start Betting helpers.

## 12. Target design

### Application contract

Предлагаемый use case:

```python
@dataclass(frozen=True)
class StartBettingResult:
    poker_id: int
    recipient_user_ids: tuple[int, ...]

class StartBettingUseCase:
    async def execute(self, *, actor_user_id: int) -> StartBettingResult: ...
```

Отдельный command object для одного `actor_user_id` не нужен. Результат содержит canonical IDs, а не Telegram/VK IDs, text или keyboards.

### Dependencies

Минимальный набор:

- `AsyncSession` для явной transaction boundary;
- существующий `PokerRepository`;
- существующий `UserRepository`;
- после commit — узкий `BettingStartedNotifier` port либо application orchestrator, вызывающий этот port.

Новые repository interfaces и Unit of Work не нужны. Для миграции потребуется точечный non-committing repository method, например `mark_betting_started(poker)` с `flush()`, при сохранении legacy `start_betting()` до миграции его остальных callers. Получение canonical IDs адресатов потребует либо нового узкого query method в `UserRepository`, либо `list_approved()` с фильтрацией по существующей notification preference. Предпочтителен repository query, возвращающий `User.row_id` и сохраняющий текущую семантику.

### Authorization and errors

Use case повторно загружает actor по `actor_user_id` и проверяет `is_approved`/`is_admin` внутри transaction. Предлагаемые точечные errors:

- `ActorNotAuthorizedError`;
- `ActivePokerNotFoundError`;
- `PokerAwaitingChipsError`;
- `BettingAlreadyOpenError`.

Не нужна большая hierarchy. TG/VK adapters сопоставляют эти ошибки с уже существующими shared texts.

### Transaction and notification boundary

```text
TG/VK handler
  → resolve platform ID to actor_user_id
  → StartBettingUseCase.execute(actor_user_id)
      → transaction: authorize, validate, set is_bettable, obtain recipient user IDs
      → commit
  → BettingStartedNotifier.notify(result)
      → clear stale platform room-status messages
      → resolve delivery route for each canonical recipient
      → send shared intent using platform text/keyboard adapters
  → map outcome to initiator response
```

Notifier вызывается только после успешного commit. Его broadcast semantics — best effort per recipient, с логированием и необязательным `DeliveryReport`. Ошибка delivery не превращает committed operation в business failure. Outbox/event bus не вводится.

Практический composition вариант: application service `StartBettingUseCase` выполняет transaction, затем вызывает injected narrow notifier после выхода из `session.begin()`. Альтернатива — handler вызывает use case, затем notifier; она проще, но оставляет cross-platform orchestration в presentation. Рекомендация: notifier dependency внутри application orchestration, с жёстко зафиксированным вызовом после commit.

### Notification port and adapters

Минимальный port выражает intent, например:

```python
class BettingStartedNotifier(Protocol):
    async def notify(self, *, recipient_user_ids: tuple[int, ...]) -> DeliveryReport: ...
```

Composite infrastructure adapter:

- получает актуальные delivery destinations по canonical user IDs;
- вызывает Telegram adapter с `Text.user.START_BETTING` и Telegram keyboard;
- вызывает VK adapter с тем же shared text и VK keyboard;
- очищает соответствующий transport room-status state;
- изолирует ошибку одного получателя.

Это один port под реальную cross-platform проблему. Универсальный event bus и port для каждого API call не нужны.

### Telegram adapter changes after implementation

После будущей миграции `start_betting()` и `start_betting_inline()` сохранят только:

- parsing/identity precheck;
- resolution `telegram_id → User.row_id`;
- вызов одного composition entry point;
- mapping ошибок/успеха в `message.answer` или `callback.answer`;
- callback-specific cleanup.

Из `_start_betting_flow` будут удалены DB reads/mutation, recipient queries, cross-platform imports, room-status cleanup и broadcast loops. Сам helper после переключения обоих entry points удаляется.

### VK adapter changes after implementation

`handle_admin_room_start_betting_text()` сохранит распознавание кнопки, identity resolution, вызов того же application entry point и VK response mapping. Inline action продолжит делегировать в единый VK adapter либо будет вызывать тот же application entry point напрямую без имитации текста.

Из VK handler будут удалены `SessionFactory` orchestration для business operation, repositories, Telegram runtime/keyboard imports, обе broadcast loops и общий status cleanup.

### Planned tests

Use-case tests:

1. authorized admin opens betting: `is_bettable=True`, один commit, canonical recipients returned, notifier invoked after commit;
2. no active poker → `ActivePokerNotFoundError`, no mutation/commit/notification;
3. chips-entry state → `PokerAwaitingChipsError`, no mutation/notification;
4. already open → `BettingAlreadyOpenError`, no mutation/notification;
5. non-admin/unapproved actor → `ActorNotAuthorizedError`, no poker read/mutation beyond required authorization read;
6. notifier failure after commit does not roll back state;
7. best effort adapter continues after one TG/VK delivery failure and reports/logs failure.

Transport tests:

- Telegram reply and callback resolve identity and map each error/outcome;
- VK text and inline action resolve identity and map each error/outcome;
- existing exact handler/dispatch order tests remain unchanged;
- characterization tests are replaced or narrowed once they no longer target legacy internals.

## 13. What will be added and removed during migration

### Add

- `StartBettingUseCase` and its focused errors/result;
- one non-committing persistence operation/query needed by the flow;
- one narrow betting-start notification port;
- composite TG/VK adapter using existing API functions, keyboards and shared text;
- use-case and adapter tests.

### Remove from TG/VK handlers

- direct `PokerRepository`/`UserRepository` orchestration for Start Betting;
- direct mutation/commit ownership;
- duplicated validation rules;
- TG↔VK imports for Start Betting;
- recipient selection and cross-platform broadcast loops;
- room-status cleanup orchestration.

No other handlers, repositories or WebApp flows are included.

## 14. OPEN QUESTIONS / TRADE-OFFS

| Rule | Existing code / conflict | Options | Recommendation | Impact |
| --- | --- | --- | --- | --- |
| Use case owns transaction | `PokerRepository.start_betting()` commits internally | A: keep repository commit; B: add non-committing method and `session.begin()`; C: introduce UoW | **B**. It fixes only this vertical slice without a framework | PokerRepository gains one focused method; legacy callers remain stable until migrated |
| Notification after commit | Both handlers currently own broadcast after repository commit | A: handler calls notifier; B: application orchestration calls narrow port after transaction; C: event bus/outbox | **B** for consistent behavior; outbox only if guaranteed delivery becomes required | One port and one composite adapter; no bus |
| Recipient identity | Current queries return external IDs and encode `notification_platform` | A: return external IDs from use case; B: return canonical IDs and resolve in adapter | **B**, preserving internal identity rule | Add focused repository query/resolution in adapter; preserve current preference semantics |
| External identity resolution | Guards currently query by platform independently and Start Betting receives external ID | A: common global resolver now; B: thin platform resolvers using `UserRepository` | **B** for first slice | Small duplicate composition remains, business operation stays shared |
| Authorization | Telegram checks outside helper; VK checks inside handler | A: trust transport; B: enforce in use case with optional early UX check | **B** | Use case loads canonical actor; buttons remain UX only |
| Existing repositories | Concrete repositories commit and return ORM models | A: define interfaces for all; B: reuse concrete classes and change only required methods | **B** | Keeps migration small; application remains pragmatically coupled to SQLAlchemy |
| Existing use-case/service abstractions | `StartPokerUseCase` establishes naming; `BroadcastUseCases` is empty | A: implement BroadcastUseCases; B: add focused notifier port and later delete shell | **B** | Avoids duplicate generic broadcast abstraction |
| Shared texts | `Text.user.START_BETTING` is already shared; inline trees contain platform copies elsewhere | A: new texts tree; B: reuse current domain text | **B** | No text migration required for Start Betting |
| Status-message cleanup | IDs live in process-global TG/VK maps | A: include in business use case; B: adapter-owned cleanup; C: persist immediately | **B** now; persistence is separate reliability work | Business layer stays transport-neutral; restart limitation remains |
| Notification failure result | Current operation reports success despite per-recipient failures | A: fail command; B: best effort and log/report; C: outbox retries | **B**, matching current behavior | State remains committed; optional delivery report improves observability |
| Duplicate concurrent starts | Read-then-update can race; SQLite/process behavior does not guarantee a single winner across workers | A: accept current risk; B: conditional atomic update; C: locking/UoW | Prefer **B** during implementation if supported cleanly, with a concurrency test | May require a focused repository method; no schema migration necessarily required |
| WebApp reuse | WebApp has separate presentation and auth debt | A: migrate together; B: expose same use case later | **B** | First slice remains TG/VK only; future HTTP endpoint reuses operation |
| Historical name identity | Some poker history depends on player names | A: fix during Start Betting; B: defer | **B** | No unrelated data/schema migration |

## 15. Implementation status

Реализован только Start Betting vertical slice:

- `StartBettingUseCase` принимает canonical `User.row_id`, повторно проверяет authorization и владеет commit;
- conditional repository update предотвращает успешное повторное открытие при гонке без schema/locking framework;
- use case возвращает platform-neutral canonical recipient IDs;
- `StartBettingFlow` завершает DB session до вызова notifier;
- composite notification adapter вне TG/VK presentation очищает room status и выполняет best-effort delivery;
- Telegram и VK используют отдельные thin handlers без cross-platform presentation imports;
- общий `Text.user.START_BETTING`, platform keyboards и существующий routing order сохранены.

Outbox, persistence room-status IDs и миграция других poker/betting flows сознательно отложены. Завершение этого среза не разрешает автоматически начинать следующую migration.
