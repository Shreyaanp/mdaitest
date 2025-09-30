# Debug Preview Testing Guide

## 🎯 Purpose

Standalone page to test camera preview with live liveness heuristics, without going through the full session flow.

## 🚀 Quick Start

### Access Debug Preview Page
```
http://localhost:3000/debug-preview
```

### Main UI (Production Flow)
```
http://localhost:3000
```

## 📺 Features

### Split View Interface

**Left Side (Preview):**
- Camera feed (MJPEG or WebRTC)
- Live metrics overlay showing:
  - Stability score
  - Focus score
  - Composite score
  - Instant/Stable liveness indicators
  - Depth, Screen, Movement checks

**Right Side (Controls & Logs):**
- Start/Stop camera button
- WebRTC vs MJPEG toggle
- Real-time event logs
- All debug output visible

## 🔧 How to Use

### 1. Open Debug Preview Page
```bash
# In your browser:
http://localhost:3000/debug-preview
```

### 2. Choose Streaming Method
- **MJPEG** (default): Simple, works everywhere
- **WebRTC**: Lower latency (~50-100ms vs ~200-300ms)

Toggle before clicking "Start Camera"

### 3. Start Camera
Click "Start Camera" button → Camera activates → Heuristics start running

### 4. Watch Metrics Update
The overlay shows real-time liveness checks:
- 🟢 Green = PASS
- 🔴 Red = FAIL

### 5. Check Logs
Right panel shows all events:
- Camera activation
- WebRTC/MJPEG setup
- Frame counts
- Metric updates

### 6. Stop Camera
Click "Stop Camera" when done

## 📊 Liveness Metrics Explained

### Stability Score (0.0 - 1.0)
- How still the person is
- Higher = better

### Focus Score
- Image sharpness (Laplacian variance)
- Higher = sharper image

### Composite Score
- Combined quality metric
- `stability * 0.7 + focus * 0.3 + (stable_alive ? 0.05 : 0)`

### Instant Alive
- Quick liveness check (current frame only)
- Depth profile, IR anti-spoofing

### Stable Alive
- Sustained liveness over time
- Requires movement + depth + IR checks over 2.5 seconds
- This is what triggers the ProcessingScreen animation

### Individual Checks
- **Depth OK**: Face has 3D depth profile (not flat)
- **Screen OK**: IR pattern variance (not a photo/screen)
- **Movement OK**: Micro-movements detected (eyes, mouth, head)

## 🔍 Debug Logs

### Backend Logs
```bash
tail -f /home/ichiro/Desktop/mercleapp/mDai/mdaitest/logs/controller-runtime.log
```

Look for:
- `📹 [WebRTC]` - WebRTC frame capture
- `🔗 [WebRTC]` - WebRTC connection events
- `d435i_liveness` - Camera and liveness processing

### Frontend Logs
- Open browser DevTools (F12) → Console
- Look for `🔍 [DEBUG PREVIEW]` messages

## 🎬 WebRTC vs MJPEG Comparison

### MJPEG (Current Default)
**Pros:**
- ✅ Simple `<img>` tag
- ✅ Works everywhere
- ✅ No complex setup
- ✅ Reliable

**Cons:**
- ⚠️ Higher latency (~200-300ms)
- ⚠️ HTTP overhead per frame

### WebRTC (New Option)
**Pros:**
- ✅ Very low latency (~50-100ms)
- ✅ Peer-to-peer optimized
- ✅ Better for real-time interaction

**Cons:**
- ⚠️ More complex setup
- ⚠️ Browser compatibility
- ⚠️ ICE/STUN/TURN may be needed for remote

## 🐛 Troubleshooting

### Camera doesn't activate
```bash
# Check backend:
curl http://localhost:5000/debug/preview \
  -X POST \
  -H 'Content-Type: application/json' \
  -d '{"enabled": true}'

# Should return: {"status":"enabled"}
```

### No video showing (MJPEG)
```bash
# Test preview endpoint directly:
curl -I http://localhost:5000/preview

# Should return: multipart/x-mixed-replace
```

### WebRTC fails
Check backend logs for:
- `🔗 [WebRTC] Creating offer` - Offer creation
- `📹 [WebRTC] Subscribed to RealSense frames` - Frame capture started
- `📹 [WebRTC] Captured N frames` - Frames flowing

### No metrics showing
- Check WebSocket connection in browser DevTools → Network tab
- Should see `ws://localhost:5000/ws/ui` connected
- Check backend logs for metric broadcasts

## 🎮 Production Flow (Physical ToF Sensor)

For actual kiosk operation:
1. Person approaches → Physical ToF sensor triggers
2. Session starts → QR code displays
3. User scans QR with phone
4. Camera activates → Preview with heuristics
5. Best frame captured and uploaded
6. Session completes

**The debug preview page bypasses steps 1-3** and goes straight to camera + heuristics testing.

## 📁 Related Files

### Backend
- `controller/app/webrtc_stream.py` - WebRTC video track implementation
- `controller/app/sensors/realsense.py` - Camera and liveness heuristics
- `controller/app/main.py` - WebRTC endpoints

### Frontend
- `mdai-ui/src/components/DebugPreview.tsx` - Debug preview page
- `mdai-ui/src/components/PreviewSurface.tsx` - Production preview (WebRTC)
- `mdai-ui/src/main.tsx` - Router for debug page

## 🔑 Key Endpoints

### Camera Control
```bash
# Enable camera
POST /debug/preview {"enabled": true}

# Disable camera
POST /debug/preview {"enabled": false}
```

### WebRTC
```bash
# Get offer
POST /webrtc/offer {}

# Send answer
POST /webrtc/answer {"peer_id": "...", "sdp": "..."}
```

### Preview Streams
```bash
# MJPEG stream
GET /preview

# Metrics stream
WS /ws/ui
```
