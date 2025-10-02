#!/usr/bin/env bash
set -euo pipefail

echo "======================================"
echo "MDAI Kiosk Status Check"
echo "======================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

success() {
  echo -e "${GREEN}✓${NC} $1"
}

error() {
  echo -e "${RED}✗${NC} $1"
}

warning() {
  echo -e "${YELLOW}⚠${NC} $1"
}

info() {
  echo -e "${BLUE}ℹ${NC} $1"
}

# Check services
echo "Service Status:"
echo "─────────────────────────────────────"
for service in mdai-backend.service mdai-frontend.service mdai-updater.timer mdai-kiosk.service; do
  if systemctl --user is-active "$service" >/dev/null 2>&1; then
    success "$service is running"
  elif systemctl --user is-enabled "$service" >/dev/null 2>&1; then
    warning "$service is enabled but not running"
  else
    error "$service is not enabled"
  fi
done

echo ""
echo "Network Endpoints:"
echo "─────────────────────────────────────"
# Check backend
if curl --silent --fail --max-time 2 http://localhost:5000/health >/dev/null 2>&1 || \
   curl --silent --fail --max-time 2 http://localhost:5000 >/dev/null 2>&1; then
  success "Backend responding on http://localhost:5000"
else
  error "Backend NOT responding on :5000"
fi

# Check frontend
if curl --silent --fail --max-time 2 http://localhost:3000 >/dev/null 2>&1; then
  success "Frontend responding on http://localhost:3000"
else
  error "Frontend NOT responding on :3000"
fi

echo ""
echo "Log Files:"
echo "─────────────────────────────────────"
LOGS_DIR="/home/ubuntu/Desktop/mdaitest/logs"
for log in backend.log frontend.log kiosk.log updater.log; do
  if [[ -f "$LOGS_DIR/$log" ]]; then
    SIZE=$(du -h "$LOGS_DIR/$log" | cut -f1)
    LINES=$(wc -l < "$LOGS_DIR/$log")
    success "$log exists ($SIZE, $LINES lines)"
  else
    warning "$log not found (service may not have started yet)"
  fi
done

echo ""
echo "Configuration:"
echo "─────────────────────────────────────"

# Check lingering
if loginctl show-user ubuntu 2>/dev/null | grep -q "Linger=yes"; then
  success "Lingering enabled (services start on boot)"
else
  warning "Lingering NOT enabled - run: sudo loginctl enable-linger ubuntu"
fi

# Check I²C
if groups ubuntu | grep -q "i2c"; then
  success "I²C permissions configured"
else
  warning "I²C permissions NOT configured"
fi

# Check display (for kiosk)
if [[ -n "${DISPLAY:-}" ]]; then
  success "DISPLAY set to: $DISPLAY"
else
  warning "DISPLAY not set (kiosk won't start)"
fi

echo ""
echo "Quick Actions:"
echo "─────────────────────────────────────"
echo "  Start services:  ./start-all.sh"
echo "  View logs:       tail -f ~/Desktop/mdaitest/logs/backend.log"
echo "  Stop services:   systemctl --user stop mdai-backend mdai-frontend mdai-kiosk"
echo "  Restart:         systemctl --user restart mdai-backend.service"
echo ""

