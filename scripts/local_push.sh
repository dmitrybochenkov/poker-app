#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -d ".git" ]]; then
  echo "Error: not a git repository: $ROOT_DIR"
  exit 1
fi

if [[ $# -gt 0 ]]; then
  COMMIT_MSG="$*"
else
  read -r -p "Commit message: " COMMIT_MSG
fi

if [[ -z "${COMMIT_MSG// }" ]]; then
  echo "Error: empty commit message"
  exit 1
fi

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
echo "==> Branch: $BRANCH"

git add -A
if git diff --cached --quiet; then
  echo "No changes to commit."
  exit 0
fi

git commit -m "$COMMIT_MSG"
git push origin "$BRANCH"

echo "Done."
