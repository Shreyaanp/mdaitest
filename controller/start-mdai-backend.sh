#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

log() {
  printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$1" >&2
}

if ! git pull --rebase --autostash; then
  log "git pull failed; retrying in 10s"
  sleep 10
  exit 1
fi

if [ ! -d ".venv" ]; then
  log "Python venv missing; creating"
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

pip install --upgrade --disable-pip-version-check -r requirements.txt

export UVICORN_HOST="0.0.0.0"
export UVICORN_PORT="5000"

exec uvicorn app.main:app --host "$UVICORN_HOST" --port "$UVICORN_PORT" --reload
