#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -d ".git" ]]; then
  echo "Error: run from inside git repository."
  exit 1
fi

if [[ ! -d ".venv" ]]; then
  echo "Error: .venv not found in $ROOT_DIR"
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
source .venv/bin/activate

echo "==> Updating python deps"
python -m pip install -U pip >/dev/null
python -m pip install -e .

echo "==> Applying alembic migrations"
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
