# Poker u Molodogo

Рабочая копия репозитория предполагается в каталоге:

`/opt/apps/poker-u-molodogo/backend`

Целевая серверная структура на Dimension-X:

```text
/opt/apps/poker-u-molodogo/
├── backend/   # этот git-репозиторий
├── webapp/    # собранный или отдельный frontend при необходимости
├── site/      # будущий публичный сайт
├── data/      # SQLite, user photos, прочие постоянные данные
├── logs/      # runtime-логи
├── scripts/   # внешние служебные скрипты, если понадобятся
├── .env
└── README.md
```

## Базовые принципы

- код хранится отдельно от постоянных данных;
- SQLite не должен лежать рядом с исходниками;
- все постоянные данные проекта должны жить в `../data` относительно backend-директории;
- владельцем проекта должен быть пользователь `krang`;
- `root` используется только для `systemd`, `caddy`, `wireguard` и системных конфигов.

## Текущие URL

- `https://poker-u-molodogo.dimension-x.dedyn.io/` — корень проекта;
- `https://poker-u-molodogo.dimension-x.dedyn.io/app/` — Telegram WebApp;
- `https://poker-u-molodogo.dimension-x.dedyn.io/api/` — backend API;
- `https://poker-u-molodogo.dimension-x.dedyn.io/webhooks/tg` — Telegram webhook;
- `https://poker-u-molodogo.dimension-x.dedyn.io/webhooks/vk` — VK webhook.

## Environment

Рекомендуемый `.env` для backend:

```env
PUBLIC_BASE_URL=https://poker-u-molodogo.dimension-x.dedyn.io
API_BASE_URL=https://poker-u-molodogo.dimension-x.dedyn.io
WEBAPP_BASE_URL=https://poker-u-molodogo.dimension-x.dedyn.io/app

DATA_DIR=../data
LOGS_DIR=../logs
STATIC_DIR=../data/static
USER_PHOTOS_DIR=../data/static/user_photos
WEBAPP_DIST_DIR=../webapp/dist
SITE_DIST_DIR=../site/dist
DATABASE_URL=
```

Если `DATABASE_URL` пустой, приложение автоматически использует:

`sqlite+aiosqlite:///.../data/poker_app.db`

## Deploy scripts

- локальный deploy по умолчанию ходит на `dimension-x:999`;
- удалённое обновление ожидает checkout в `/opt/apps/poker-u-molodogo/backend`;
- restart/reload сервисов выполняется через `sudo -n`, то есть на сервере должен быть настроен passwordless sudo для нужных команд.
