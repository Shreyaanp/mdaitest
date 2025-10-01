#!/bin/bash
# Start the mDAI controller from the CORRECT directory

set -e

# Ensure we're in the right directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROLLER_DIR="$SCRIPT_DIR/controller"

echo "======================================"
echo "  mDAI Controller Startup Script"
echo "======================================"
echo ""
echo "Working directory: $CONTROLLER_DIR"
echo ""

# Check if virtual environment exists
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    echo "⚠️  Virtual environment not found at $SCRIPT_DIR/.venv"
    echo "Please create it first:"
    echo "  python3 -m venv .venv"
    echo "  source .venv/bin/activate"
    echo "  pip install -r controller/requirements.txt"
    exit 1
fi

# Activate virtual environment
source "$SCRIPT_DIR/.venv/bin/activate"

# Check if uvicorn is installed
if ! command -v uvicorn &> /dev/null; then
    echo "⚠️  uvicorn not found. Installing..."
    pip install uvicorn
fi

# Change to controller directory
cd "$CONTROLLER_DIR"

echo "✅ Starting controller..."
echo "   - Host: 0.0.0.0"
echo "   - Port: 5000"
echo "   - Reload: enabled"
echo ""
echo "Press CTRL+C to stop"
echo "======================================"
echo ""

# Start uvicorn
exec uvicorn app.main:app --reload --host 0.0.0.0 --port 5000
