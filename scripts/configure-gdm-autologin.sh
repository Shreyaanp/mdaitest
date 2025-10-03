#!/usr/bin/env bash
set -euo pipefail

SESSION_NAME=${1:-gnome-xorg}
LANGUAGE=${LANG:-en_US.UTF-8}
DMRC_PATH="$HOME/.dmrc"
AUTOSTART_DIR="$HOME/.config/autostart"
AUTOSTART_FILE="$AUTOSTART_DIR/gnome-initial-setup-first-login.desktop"
SETUP_FLAG="$HOME/.config/gnome-initial-setup-done"

log() {
  printf '[configure-gdm-autologin] %s\n' "$1"
}

ensure_dmrc() {
  cat <<EOF_DMRC >"$DMRC_PATH"
[Desktop]
Session=$SESSION_NAME
Language=$LANGUAGE
EOF_DMRC
  chmod 600 "$DMRC_PATH"
  log "Wrote $DMRC_PATH with session '$SESSION_NAME'"
}

disable_initial_setup() {
  mkdir -p "$AUTOSTART_DIR"
  cat <<'EOF_AUTOSTART' >"$AUTOSTART_FILE"
[Desktop Entry]
Type=Application
Name=GNOME Initial Setup
NoDisplay=true
Hidden=true
X-GNOME-Autostart-enabled=false
EOF_AUTOSTART
  chmod 644 "$AUTOSTART_FILE"
  touch "$SETUP_FLAG"
  log "Disabled GNOME initial setup screens"
}

ensure_dmrc
disable_initial_setup

log "GDM autologin will now use the '$SESSION_NAME' desktop without prompts."
log "If you have not already, enable automatic login in /etc/gdm3/custom.conf."
