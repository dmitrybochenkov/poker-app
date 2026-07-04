#!/usr/bin/env bash
set -euo pipefail

SERVER_HOST="${1:-dimension-x}"
SERVER_PORT="${SERVER_PORT:-999}"
REMOTE_ROOT="${2:-/opt/apps/poker-u-molodogo}"
REMOTE_SCRIPT="${REMOTE_ROOT}/scripts/server_full_update.sh"

ssh -tt -p "$SERVER_PORT" "$SERVER_HOST" \
  "git config --global --add safe.directory '$REMOTE_ROOT' >/dev/null 2>&1 || true; cd '$REMOTE_ROOT' && '$REMOTE_SCRIPT' '$REMOTE_ROOT'"
