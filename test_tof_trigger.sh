#!/bin/bash
# Test ToF trigger using the mock endpoint

echo "🧪 Testing ToF trigger with mock distance..."
echo ""
echo "Simulating user approaching (distance=250mm < 500mm threshold)..."

curl -X POST http://127.0.0.1:5000/debug/mock-tof \
  -H "Content-Type: application/json" \
  -d '{"triggered": true, "distance_mm": 250}' | jq

echo ""
echo "Wait 5 seconds, then simulate user walking away..."
sleep 5

curl -X POST http://127.0.0.1:5000/debug/mock-tof \
  -H "Content-Type: application/json" \
  -d '{"triggered": false, "distance_mm": 1500}' | jq

echo ""
echo "✅ Test complete!"


