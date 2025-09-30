# Complete Flow Test Guide

## 🚀 Quick Start

### Services Status
Check both are running:
```bash
curl http://localhost:5000/healthz  # Controller
curl http://localhost:3000          # UI
```

## 🧪 Test the Complete Production Flow

### Step 1: Open Production UI
```
http://localhost:3000
```

You should see the idle screen with animations.

### Step 2: Trigger ToF Sensor (Start Session)
```bash
curl -X POST 'http://localhost:5000/debug/mock-tof' \
  -H 'Content-Type: application/json' \
  -d '{"triggered": true, "distance_mm": 345}'
```

**What happens:**
- ✅ Session starts
- ✅ Animations play (idle exit → hero hold → scan prompt)
- ✅ QR code displays

### Step 3: Scan QR Code with Mobile App
- Use your mobile app to scan the QR code
- App connects to backend via WebSocket

**OR simulate app connection (for testing without phone):**
```bash
curl -X POST 'http://localhost:5000/debug/app-ready' \
  -H 'Content-Type: application/json' \
  -d '{"platform_id": "TEST_USER_123"}'
```

### Step 4: Camera Activates (human_detect phase)
**What you should see:**
- ✅ Animations complete
- ✅ **Camera preview appears** (raw feed, no metrics overlay)
- ✅ ProcessingScreen overlay with instructions
- ✅ Backend runs liveness checks continuously

### Step 5: Hold Steady (stabilizing phase)
- System collects frames for ~5 seconds
- Liveness checks run
- Best frame selected

### Step 6: Upload
- Frame uploads to backend
- Processing messages shown

### Step 7: Complete
- Success message
- Returns to idle

### Step 8: End Session (Stop ToF)
```bash
curl -X POST 'http://localhost:5000/debug/mock-tof' \
  -H 'Content-Type: application/json' \
  -d '{"triggered": false}'
```

## 📊 Debug While Testing

### Watch Backend Logs
```bash
tail -f logs/controller-runtime.log | grep -E "(Phase|✅ LIVENESS|Session)"
```

### Watch Browser Console
- Open DevTools (F12) → Console
- Look for phase transitions and preview visibility logs

## 🎯 What to Verify

### Idle Screen
- [x] Hello Human Hero animation
- [x] TV bars effect
- [x] Clean design

### After ToF Trigger
- [x] Idle exit animation plays
- [x] "scan this to get started" message
- [x] QR code displays correctly

### After App Connection
- [x] Camera preview appears
- [x] Preview is CONTINUOUS (no flickering/stopping)
- [x] ProcessingScreen overlay shows instructions
- [x] Backend liveness shows: `✅ LIVENESS PASS`

### During Stabilizing
- [x] Preview stays on
- [x] Frames being collected
- [x] Best frame selected (check captures/ folder)

### Upload & Complete
- [x] Upload animation
- [x] Success message
- [x] Returns to idle

## 🐛 Common Issues

### Preview not showing
```bash
# Check if camera activated:
tail -f logs/controller-runtime.log | grep "hardware"

# Should see:
# "Camera activated for biometric capture"
```

### QR code not appearing
```bash
# Check phase:
curl http://localhost:5000/healthz

# Should show: "qr_display" or "waiting_activation"
```

### Liveness always failing
```bash
# Check actual values:
tail -f logs/controller-runtime.log | grep "DEPTH FAIL"

# Should be mostly passing now with new thresholds
```

## 🎮 Quick Test Commands

### Start Session
```bash
curl -X POST http://localhost:5000/debug/mock-tof \
  -H 'Content-Type: application/json' \
  -d '{"triggered": true, "distance_mm": 345}'
```

### Skip App Wait
```bash
curl -X POST http://localhost:5000/debug/app-ready \
  -H 'Content-Type: application/json' \
  -d '{"platform_id": "TEST_123"}'
```

### Check Current State
```bash
curl http://localhost:5000/healthz
```

## 📁 Check Captured Frames

After a successful session:
```bash
ls -lht captures/ | head -5

# Should see:
# 20250930_HHMMSS_TEST_123_BEST.jpg
# 20250930_HHMMSS_TEST_123_BEST.json
```

## 🎬 Expected Timeline

```
00:00 - ToF trigger → Session starts
00:03 - Animations complete → QR code shows
00:10 - User scans QR (or you mock it)
00:13 - Camera activates → Preview visible
00:16 - Stabilizing → Collecting frames
00:21 - Upload → Processing
00:24 - Complete → Return to idle
```

Total: ~25-30 seconds for full flow
