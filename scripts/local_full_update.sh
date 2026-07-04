#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
WEBAPP_DIR="${ROOT_DIR}/webapp"
cd "$ROOT_DIR"

if [[ ! -d ".git" ]]; then
  echo "Error: run from inside git repository."
  exit 1
fi

PYTHON_VENV="${ROOT_DIR}/.venv"
if [[ ! -d "$PYTHON_VENV" && -d "$BACKEND_DIR/.venv" ]]; then
  PYTHON_VENV="$BACKEND_DIR/.venv"
fi

if [[ ! -d "$PYTHON_VENV" ]]; then
  echo "Error: python venv not found in $ROOT_DIR/.venv or $BACKEND_DIR/.venv"
  exit 1
fi

if [[ $# -gt 0 ]]; then
  COMMIT_MSG="$*"
else
  read -r -p "Commit message: " COMMIT_MSG
fi

if [[ -z "${COMMIT_MSG// }" ]]; then
  echo "Error: commit message is empty."
  exit 1
fi

echo "==> Activating venv"
source "$PYTHON_VENV/bin/activate"

echo "==> Updating python deps"
cd "$BACKEND_DIR"
python -m pip install -U pip >/dev/null
python -m pip install -e .

echo "==> Applying alembic migrations"
alembic upgrade head

if [[ -d "$WEBAPP_DIR" ]]; then
  echo "==> Building webapp"
  cd "$WEBAPP_DIR"
  if [[ -f "package-lock.json" ]]; then
    npm ci
  else
    npm install
  fi
  npm run build
  cd "$ROOT_DIR"
fi

echo "==> Git sync/rebase"
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
git fetch origin
git pull --rebase origin "$CURRENT_BRANCH"

echo "==> Commit & push"
git add -A
if git diff --cached --quiet; then
  echo "No changes to commit."
  exit 0
fi

git commit -m "$COMMIT_MSG"
git push origin "$CURRENT_BRANCH"

echo "Done."
