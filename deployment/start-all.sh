#!/usr/bin/env bash
set -euo pipefail

echo "======================================"
echo "Starting All MDAI Services"
echo "======================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

success() {
  echo -e "${GREEN}✓${NC} $1"
}

info() {
  echo -e "${BLUE}ℹ${NC} $1"
}

error() {
  echo -e "${RED}✗${NC} $1"
}

# Start services
info "Starting backend..."
systemctl --user start mdai-backend.service
sleep 2

info "Starting frontend..."
systemctl --user start mdai-frontend.service
sleep 2

info "Starting updater timer..."
systemctl --user start mdai-updater.timer
sleep 1

echo ""
echo "======================================"
echo "Service Status"
echo "======================================"
echo ""

# Check status
for service in mdai-backend.service mdai-frontend.service mdai-updater.timer; do
  if systemctl --user is-active "$service" >/dev/null 2>&1; then
    success "$service is running"
  else
    error "$service is NOT running"
  fi
done

echo ""
echo "======================================"
echo "Quick Checks"
echo "======================================"
echo ""

# Check backend
if curl --silent --fail --max-time 2 http://localhost:5000/health >/dev/null 2>&1; then
  success "Backend responding on :5000"
else
  info "Backend not responding yet (may need more time to start)"
fi

# Check frontend
if curl --silent --fail --max-time 2 http://localhost:3000 >/dev/null 2>&1; then
  success "Frontend responding on :3000"
else
  info "Frontend not responding yet (may need more time to start)"
fi

echo ""
echo "To view logs:"
echo "  tail -f ~/Desktop/mdaitest/logs/backend.log"
echo "  tail -f ~/Desktop/mdaitest/logs/frontend.log"
echo ""
echo "To check detailed status:"
echo "  systemctl --user status mdai-backend.service"
echo "  systemctl --user status mdai-frontend.service"
echo ""

# Note about kiosk
echo "NOTE: Kiosk service will start automatically when you login to the GUI."
echo "      It requires DISPLAY :0 to be available (graphical session)."
echo ""

