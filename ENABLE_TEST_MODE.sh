#!/bin/bash
# Enable Test Mode (No Hardware Required)
# Run this before testing without RealSense + ToF

cd "$(dirname "$0")"

echo "🧪 Enabling Test Mode..."
echo ""

# Backup ToF binary if it exists
if [ -f "controller/tof/build/tof-reader" ]; then
    echo "📦 Backing up ToF binary..."
    mv controller/tof/build/tof-reader controller/tof/build/tof-reader.arm.backup
    echo "✅ ToF binary moved to tof-reader.arm.backup"
fi

# Install psutil if not installed
echo ""
echo "📦 Installing psutil for CPU/memory monitoring..."
pip install psutil >/dev/null 2>&1 && echo "✅ psutil installed" || echo "⚠️ psutil install failed"

echo ""
echo "✅ Test Mode Enabled!"
echo ""
echo "What this does:"
echo "  • Disables RealSense hardware (uses webcam)"
echo "  • Disables ToF binary (uses mock slider)"
echo "  • Enables simulated validation"
echo "  • No spam errors in logs"
echo ""
echo "To restore production mode:"
echo "  mv controller/tof/build/tof-reader.arm.backup controller/tof/build/tof-reader"
echo ""
echo "Now run: ./START_CONTROLLER.sh"

