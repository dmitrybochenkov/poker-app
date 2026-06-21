#!/usr/bin/env bash
set -euo pipefail

SERVER_HOST="${1:-poker-vds}"
SERVER_PORT="${SERVER_PORT:-999}"
REMOTE_ROOT="${2:-/opt/poker-app}"
REMOTE_SCRIPT="${REMOTE_ROOT}/scripts/server_full_update.sh"

ssh -p "$SERVER_PORT" "$SERVER_HOST" "cd '$REMOTE_ROOT' && '$REMOTE_SCRIPT'"
