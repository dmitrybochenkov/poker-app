#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${1:-/opt/apps/poker-u-molodogo/backend}"
SERVICE_NAME="${2:-poker-app}"
BRANCH="${3:-main}"

cd "$ROOT_DIR"

if [[ ! -d ".git" ]]; then
  echo "Error: $ROOT_DIR is not a git repository."
  exit 1
fi

# Newer git versions can block worktrees owned by another user.
# Mark the deploy directory as safe before any fetch/pull operations.
git config --global --add safe.directory "$ROOT_DIR" >/dev/null 2>&1 || true

if [[ ! -d ".venv" ]]; then
  echo "Error: .venv not found in $ROOT_DIR"
  exit 1
fi

echo "==> Pulling latest branch: $BRANCH"
git fetch origin
git checkout "$BRANCH"
git pull --rebase origin "$BRANCH"

echo "==> Activating venv"
source .venv/bin/activate

echo "==> Updating python deps"
python -m pip install -U pip >/dev/null
python -m pip install -e .

echo "==> Running alembic migrations"
alembic upgrade head

if [[ -d "webapp" ]]; then
  echo "==> Building webapp"
  cd webapp
  if [[ -f "package-lock.json" ]]; then
    npm ci
  else
    npm install
  fi
  npm run build
  cd "$ROOT_DIR"
fi

echo "==> Restarting backend service: $SERVICE_NAME"
if ! sudo -n systemctl restart "$SERVICE_NAME"; then
  echo "Error: passwordless sudo is required for restarting $SERVICE_NAME."
  exit 1
fi

if systemctl list-unit-files | grep -q '^caddy\.service'; then
  echo "==> Reloading caddy"
  if ! sudo -n systemctl reload caddy; then
    echo "Warning: could not reload caddy without sudo password. Skipping."
  fi
fi

echo "==> Service status"
sudo -n systemctl --no-pager --full status "$SERVICE_NAME" | sed -n '1,12p'

echo "Done."
