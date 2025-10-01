#!/usr/bin/env bash
set -euo pipefail

TARGET_URL="${1:-http://localhost:3000}"

# Use the DISPLAY provided by the environment when available, otherwise fall back to :0
DISPLAY_VALUE="${DISPLAY:-:0}"
export DISPLAY="$DISPLAY_VALUE"

# Locate a usable Xauthority cookie for the active graphical session
XAUTHORITY_VALUE="${XAUTHORITY:-}"
if [[ -n "$XAUTHORITY_VALUE" && ! -f "$XAUTHORITY_VALUE" ]]; then
  XAUTHORITY_VALUE=""
fi

if [[ -z "$XAUTHORITY_VALUE" && -n "${XDG_RUNTIME_DIR:-}" ]]; then
  XWAYLAND_COOKIE=$(ls -t "${XDG_RUNTIME_DIR}"/.mutter-Xwaylandauth.* 2>/dev/null | head -n1 || true)
  if [[ -n "$XWAYLAND_COOKIE" && -f "$XWAYLAND_COOKIE" ]]; then
    XAUTHORITY_VALUE="$XWAYLAND_COOKIE"
  fi
fi

if [[ -z "$XAUTHORITY_VALUE" && -f "${HOME}/.Xauthority" ]]; then
  XAUTHORITY_VALUE="${HOME}/.Xauthority"
fi

if [[ -z "$XAUTHORITY_VALUE" ]]; then
  echo "Unable to locate an Xauthority file for display $DISPLAY_VALUE" >&2
  exit 1
fi

export XAUTHORITY="$XAUTHORITY_VALUE"

# Ensure a display is ready before proceeding
for attempt in {1..120}; do
  if xset -display "$DISPLAY_VALUE" q >/dev/null 2>&1; then
    break
  fi
  sleep 1
  if [[ "$attempt" -eq 120 ]]; then
    echo "Display $DISPLAY_VALUE not ready after 120s" >&2
    exit 1
  fi
done

# Wait for the frontend to respond before launching the browser
for attempt in {1..30}; do
  if curl --silent --fail --max-time 2 "$TARGET_URL" >/dev/null; then
    break
  fi
  sleep 2
  if [[ "$attempt" -eq 30 ]]; then
    echo "Frontend not reachable after 60s; launching browser anyway" >&2
  fi
done

# Prevent screen blanking and power management that could hide the kiosk
if command -v xset >/dev/null; then
  xset -display "$DISPLAY_VALUE" s off || true
  xset -display "$DISPLAY_VALUE" -dpms || true
  xset -display "$DISPLAY_VALUE" s noblank || true
fi

BROWSER=$(command -v chromium-browser || command -v chromium || command -v google-chrome || true)
if [[ -z "$BROWSER" ]]; then
  echo "Chromium browser not found" >&2
  exit 1
fi

exec "$BROWSER" \
  --noerrdialogs \
  --disable-session-crashed-bubble \
  --disable-infobars \
  --kiosk "$TARGET_URL" \
  --start-fullscreen \
  --incognito \
  --overscroll-history-navigation=0
