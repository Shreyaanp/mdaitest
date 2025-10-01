#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

NVM_DIR="${HOME}/.nvm"
if [ -s "$NVM_DIR/nvm.sh" ]; then
  # shellcheck disable=SC1091
  source "$NVM_DIR/nvm.sh"
elif [ -s "/usr/share/nvm/nvm.sh" ]; then
  # shellcheck disable=SC1091
  source "/usr/share/nvm/nvm.sh"
else
  echo "nvm not found" >&2
  exit 1
fi

nvm use 22 >/dev/null

if ! git pull --rebase --autostash; then
  echo "git pull failed; retrying in 10s" >&2
  sleep 10
  exit 1
fi

npm install --prefer-offline --no-fund

export HOST=0.0.0.0
export PORT=3000

exec npm run dev -- --host "$HOST" --port "$PORT"
