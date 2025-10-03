#!/usr/bin/env bash
set -euo pipefail

URL="${1:-http://localhost:3000}"
MAX_ATTEMPTS=${MAX_ATTEMPTS:-60}
SLEEP_SECONDS=${SLEEP_SECONDS:-5}
CHROMIUM_BINARY="${CHROMIUM_BINARY:-/usr/bin/chromium-browser}"
WORKSPACE_INDEX=${WORKSPACE_INDEX:-0}

log() {
  printf '[open-mdai-browser] %s\n' "$1"
}

ensure_workspace_settings() {
  if ! command -v gsettings >/dev/null 2>&1; then
    log "gsettings not available; skipping workspace configuration"
    return
  fi

  if gsettings writable org.gnome.mutter dynamic-workspaces >/dev/null 2>&1; then
    if gsettings get org.gnome.mutter dynamic-workspaces 2>/dev/null | grep -qx 'true'; then
      if gsettings set org.gnome.mutter dynamic-workspaces false >/dev/null 2>&1; then
        log "Disabled dynamic workspaces"
      else
        log "Unable to disable dynamic workspaces"
      fi
    fi
  fi

  desired_count=$(( WORKSPACE_INDEX + 1 ))
  if gsettings writable org.gnome.desktop.wm.preferences num-workspaces >/dev/null 2>&1; then
    current_count=$(gsettings get org.gnome.desktop.wm.preferences num-workspaces 2>/dev/null | tr -dc '0-9')
    if [ -z "$current_count" ] || [ "$current_count" -lt "$desired_count" ]; then
      if gsettings set org.gnome.desktop.wm.preferences num-workspaces "$desired_count" >/dev/null 2>&1; then
        log "Set number of workspaces to $desired_count"
      else
        log "Unable to set number of workspaces"
      fi
    fi
  fi
}

activate_workspace() {
  if ! command -v gdbus >/dev/null 2>&1; then
    log "gdbus not available; skipping workspace activation"
    return
  fi

  js="const idx = ${WORKSPACE_INDEX}; const workspace = global.workspace_manager.get_workspace_by_index(idx); if (workspace) { workspace.activate(global.get_current_time()); true; } else { false; }"

  for attempt in $(seq 1 5); do
    if output=$(gdbus call --session \
      --dest org.gnome.Shell \
      --object-path /org/gnome/Shell \
      --method org.gnome.Shell.Eval "$js" 2>/dev/null); then
      log "Activated workspace ${WORKSPACE_INDEX}"
      return
    fi
    log "Workspace activation attempt ${attempt} failed; retrying"
    sleep 1
  done
  log "Unable to activate workspace ${WORKSPACE_INDEX}; continuing"
}

if ! command -v "$CHROMIUM_BINARY" >/dev/null 2>&1; then
  log "Chromium binary not found: $CHROMIUM_BINARY"
  exit 1
fi

attempt=1
until curl --silent --head --fail "$URL" >/dev/null 2>&1; do
  if (( attempt >= MAX_ATTEMPTS )); then
    log "Reached max attempts ($MAX_ATTEMPTS). Launching browser anyway."
    break
  fi
  log "Waiting for $URL (attempt $attempt/$MAX_ATTEMPTS)"
  attempt=$(( attempt + 1 ))
  sleep "$SLEEP_SECONDS"
done

ensure_workspace_settings
activate_workspace

log "Launching Chromium in kiosk mode at $URL"
exec "$CHROMIUM_BINARY" \
  --kiosk \
  --start-fullscreen \
  --disable-infobars \
  --no-first-run \
  --disable-session-crashed-bubble \
  --no-default-browser-check \
  --disable-features=TranslateUI \
  --no-sandbox \
  --enable-features=UseOzonePlatform \
  --ozone-platform-hint=auto \
  "$URL"
