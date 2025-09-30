# ⚡ Quick Reference Card

## 🚀 Start Services

```bash
# Controller (Terminal 1)
cd controller && uvicorn app.main:app --reload --port 5000

# UI (Terminal 2)
cd mdai-ui && npm run dev
```

## 🔗 URLs

| Purpose | URL |
|---------|-----|
| **Main App** | http://localhost:5173 |
| **Debug Gallery** | http://localhost:5173/debug |
| **Camera Preview** | http://localhost:5173/debug-preview |
| **Controller API** | http://localhost:5000/healthz |
| **Preview Stream** | http://localhost:5000/preview |

## 📋 Session Phases (in order)

```
1. idle (∞)           → TV bars static
2. pairing (1.5s)     → Exit animation + request token
3. hello (2s)         → "Hello Human"
4. scan (3s)          → "Scan this to get started"
5. qr (∞)             → QR code
6. detect (3.5s)      → Camera validation
7. process (3-15s)    → Upload + wait
8. complete/error (3s) → Done
```

## 🎮 Debug Controls

```bash
# Mock ToF trigger
curl -X POST http://localhost:5000/debug/mock-tof \
  -H "Content-Type: application/json" \
  -d '{"triggered": true, "distance_mm": 350}'

# Mock mobile app ready
curl -X POST http://localhost:5000/debug/app-ready \
  -H "Content-Type: application/json" \
  -d '{"platform_id": "PLT_DebugTest123"}'

# Enable camera preview
curl -X POST http://localhost:5000/debug/preview \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

## 🚶 ToF Behavior

| Condition | Action |
|-----------|--------|
| **IDLE + distance ≤ 450mm** | Start session |
| **Active + distance > 450mm for 1.2s** | Cancel → IDLE |
| **COMPLETE/ERROR state** | No monitoring |

## 🎯 Validation Requirements

| Metric | Threshold |
|--------|-----------|
| **Duration** | 3.5s exactly |
| **Min frames** | 10 passing frames |
| **Liveness** | depth_ok only (hybrid) |
| **Result** | Best frame (quality score) |

## 📊 Timing Quick Ref

```
IDLE → Session starts
  ↓ 1.5s  (pairing)
  ↓ 2.0s  (hello)
  ↓ 3.0s  (scan)
  ↓ ~5-30s (QR wait)
  ↓ 3.5s  (validation)
  ↓ 3-15s (processing)
  ↓ 3.0s  (complete)
  ↓ 4.0s  (entry animation)
IDLE again
```

## 🎨 Animation States

| Transition | Animation | Duration |
|------------|-----------|----------|
| **IDLE → other** | EXIT (retract) | 4s |
| **other → IDLE** | ENTRY (fall) | 4s |
| **In IDLE** | Static | - |

## 🐛 Common Issues

### **"Scan prompt not showing"**
```python
# Check: HELLO_HUMAN duration complete?
# File: session_manager.py → _show_hello_human()
await self._advance_phase(SessionPhase.HELLO_HUMAN, min_duration=2.0)
```

### **"Validation always fails"**
```python
# Check: MIN_PASSING_FRAMES too high?
# File: session_manager.py → _validate_human_presence()
MIN_PASSING_FRAMES = 10  # Lower to 5 for testing
```

### **"Camera doesn't activate"**
```bash
# Check RealSense is connected
rs-enumerate-devices

# Check logs for activation
grep "Camera activated" logs/controller-runtime.log
```

### **"Processing times out"**
```python
# Check: Backend responding?
# File: session_manager.py → _process_and_upload()
timeout=15.0  # Increase to 30.0 if needed
```

## 📁 Key Files

| Purpose | File |
|---------|------|
| **Phase definitions** | `controller/app/state.py` |
| **Session flow** | `controller/app/session_manager.py` |
| **Frontend phases** | `mdai-ui/src/app-state/sessionMachine.ts` |
| **UI routing** | `mdai-ui/src/components/StageRouter.tsx` |
| **Debug gallery** | `mdai-ui/src/components/DebugScreenGallery.tsx` |

## 🔍 Log Grep Patterns

```bash
# Monitor session flow
tail -f logs/controller-runtime.log | grep -E "📱|👋|📸|🚀|✅|❌"

# ToF events
tail -f logs/controller-runtime.log | grep "ToF"

# Validation results
tail -f logs/controller-runtime.log | grep "Validation complete"

# Errors only
tail -f logs/controller-runtime.log | grep "ERROR"
```

## 💡 Quick Tips

- Press **Space** in debug gallery to auto-play screens
- Use **/debug** route to preview UI without backend
- ToF cancellation is **intentional** (not an error)
- Depth-only check is **forgiving** (won't reject real humans)
- Best frame quality = **70% stability + 30% focus**

---

**Need help? Check `FINAL_IMPLEMENTATION_GUIDE.md` for full details!**
