# Poker u Molodogo

Рабочая копия проекта предполагается в каталоге:

`/opt/apps/poker-u-molodogo`

Целевая серверная структура на Dimension-X:

```text
/opt/apps/poker-u-molodogo/
├── backend/   # FastAPI, TG/VK bot logic, alembic, tests
├── webapp/    # Telegram WebApp frontend
├── site/      # будущий публичный сайт
├── data/      # SQLite, user photos, прочие постоянные данные
├── logs/      # runtime-логи
├── scripts/   # служебные скрипты
├── .env
└── README.md
```

## Базовые принципы

- код хранится отдельно от постоянных данных;
- SQLite не должен лежать рядом с исходниками;
- все постоянные данные проекта должны жить в `data/`, а backend обращается к ним через `../data`;
- владельцем проекта должен быть пользователь `krang`;
- `root` используется только для `systemd`, `caddy`, `wireguard` и системных конфигов.

## Текущие URL

- `https://poker-u-molodogo.dimension-x.dedyn.io/` — корень проекта;
- `https://poker-u-molodogo.dimension-x.dedyn.io/app/` — Telegram WebApp;
- `https://poker-u-molodogo.dimension-x.dedyn.io/api/` — backend API;
- `https://poker-u-molodogo.dimension-x.dedyn.io/webhooks/tg` — Telegram webhook;
- `https://poker-u-molodogo.dimension-x.dedyn.io/webhooks/vk` — VK webhook.

## Environment

Рекомендуемый `.env` в корне проекта:

```env
PUBLIC_BASE_URL=https://poker-u-molodogo.dimension-x.dedyn.io
CORS_ALLOWED_ORIGINS=https://poker-u-molodogo.dimension-x.dedyn.io,http://localhost:5173
DATABASE_URL=
```

`API_BASE_URL` и `WEBAPP_BASE_URL` обычно не нужно задавать отдельно:
- `API_BASE_URL` по умолчанию берётся из `PUBLIC_BASE_URL`
- `WEBAPP_BASE_URL` по умолчанию считается как `PUBLIC_BASE_URL + /app`

Пути до `data/`, `logs/`, `static/`, `webapp/dist` и `site/dist` тоже можно не выносить в `.env`, если проект лежит в стандартной структуре.

Backend теперь разрешает относительные пути от каталога `backend/`, а не от текущего `cwd`, поэтому одинаково работает и локально, и под `systemd`.

Основной `.env` должен лежать в корне проекта. Дублировать его в `backend/.env` не требуется.

Если `DATABASE_URL` пустой, приложение автоматически использует:

`sqlite+aiosqlite:///.../data/poker_app.db`

## Backend commands

Локально backend теперь запускается из подкаталога `backend/`:

```bash
cd backend
source ../.venv/bin/activate
python -m pip install -e .
alembic upgrade head
uvicorn app.main:app --reload
```

Собрать WebApp:

```bash
cd webapp
npm install
npm run build
```

## Быстрый подъем на VDS

После `git pull` на сервере достаточно:

```bash
cd /opt/apps/poker-u-molodogo/backend
source .venv/bin/activate
python -m pip install -e .
alembic upgrade head
sudo systemctl restart poker-u-molodogo
sudo journalctl -u poker-u-molodogo -n 50 --no-pager
```

Перед этим нужно только:

- положить рабочий `.env` в `/opt/apps/poker-u-molodogo/.env`
- перенести базу в `/opt/apps/poker-u-molodogo/data/poker_app.db`
- проверить наличие `credentials.json`, если нужен Google backup

## Deploy scripts

- локальный deploy по умолчанию ходит на `dimension-x:999`;
- удалённое обновление ожидает checkout в `/opt/apps/poker-u-molodogo`;
- restart/reload сервисов выполняется через `sudo -n`, то есть на сервере должен быть настроен passwordless sudo для нужных команд.
