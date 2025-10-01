# Production Mode Cleanup - Complete

## ToF Debug Code Removed

### ✅ Frontend (mdai-ui)

#### Files Modified:

1. **`src/App.tsx`**
   - ❌ Removed `isTofTriggering` state
   - ❌ Removed `triggerTof()` callback
   - ❌ Removed `onMockTof` prop passing to StageRouter
   - ❌ Removed ToF-related props to ControlPanel

2. **`src/components/StageRouter.tsx`**
   - ❌ Removed `onMockTof` from interface
   - ❌ Removed `onMockTof` prop from function signature
   - ❌ Removed `onMockTof` prop passing to IdleScreen

3. **`src/components/IdleScreen.tsx`**
   - ❌ Removed `onMockTof` from interface
   - ❌ Removed "Mock ToF" button from idle screen

4. **`src/components/ControlPanel.tsx`**
   - ❌ Removed `onTofTrigger` prop
   - ❌ Removed `tofTriggerDisabled` prop
   - ❌ Removed `isTofTriggering` prop
   - ❌ Removed "ToF Trigger" button from control panel

### ✅ Backend (controller)

#### Files Modified:

1. **`app/main.py`**
   - ❌ Removed `TofTriggerRequest` model
   - ❌ Removed `TofBypassRequest` model
   - ❌ Removed `/debug/tof-trigger` endpoint
   - ❌ Removed `/debug/tof-bypass` endpoint

2. **`app/session_manager.py`**
   - ❌ Removed `_tof_bypass` flag
   - ❌ Removed `simulate_tof_trigger()` method
   - ❌ Removed `set_tof_bypass()` method
   - ✅ Cleaned up `_handle_tof_trigger()` logic
   - ✅ Production-ready logging

3. **`app/sensors/tof.py`**
   - ❌ Removed `mock_distance_provider()`
   - ✅ Cleaner logging (removed verbose debug)

4. **`app/sensors/tof_process.py`**
   - ✅ Fail-fast on missing binary
   - ✅ Better error messages

---

## What Remains (Production Features)

### ✅ Frontend

**Debug Features (Kept):**
- ✅ "Trigger Session" button (simulates ToF for testing)
- ✅ Control panel with metrics
- ✅ Log console
- ✅ Preview toggle

**UI Flow:**
```
IDLE Screen → (Wait for ToF or manual trigger) → QR Code → ...
```

**No ToF debug buttons visible!** ✨

### ✅ Backend

**Debug Endpoints (Kept):**
- ✅ `POST /debug/trigger` - Manual session start
- ✅ `POST /debug/app-ready` - Simulate mobile connection
- ✅ `POST /debug/preview` - Toggle preview
- ✅ `GET /healthz` - Health check

**Removed:**
- ❌ `POST /debug/tof-trigger` - Simulate ToF sensor
- ❌ `POST /debug/tof-bypass` - Bypass ToF requirement

---

## Production Behavior

### ToF Sensor Control

**Before (Debug Mode):**
```
- Mock ToF button in UI ❌
- ToF trigger endpoint ❌
- ToF bypass mode ❌
- Mock distance provider fallback ❌
```

**After (Production Mode):**
```
- Real ToF hardware REQUIRED ✅
- No UI override buttons ✅
- No bypass mechanisms ✅
- Fail-fast if hardware missing ✅
```

### Expected Flow

```
1. System starts
   └─> ToF sensor must be connected (fails if not)

2. User approaches kiosk
   └─> ToF sensor detects proximity (< 450mm)

3. Session starts automatically
   └─> No manual intervention needed

4. User steps away
   └─> ToF sensor releases (> 450mm)
   └─> Session cancels if in progress
```

### Logs (Production)

**ToF Trigger:**
```
[INFO] ToF TRIGGERED (distance=420mm, phase=idle)
[INFO] Starting session from ToF trigger
```

**ToF Release:**
```
[INFO] ToF released (distance=480mm, phase=stabilizing)
[WARNING] ToF sensor released mid-session - cancelling
```

**No Debug Spam:**
```
❌ No "Simulated ToF trigger" logs
❌ No "ToF bypass enabled" logs
❌ No "Mock distance provider" logs
```

---

## Remaining Debug Features

### Still Available (For Development)

1. **Manual Session Trigger**
   ```bash
   # Bypass ToF sensor for testing
   curl -X POST http://localhost:5000/debug/trigger
   ```
   - UI button: "Trigger Session"
   - Use case: Test session flow without physical ToF trigger

2. **App Ready Shortcut**
   ```bash
   # Skip mobile pairing
   curl -X POST http://localhost:5000/debug/app-ready \
     -H "Content-Type: application/json" \
     -d '{"platform_id": "test123"}'
   ```
   - Use case: Test capture flow without mobile app

3. **Preview Toggle**
   ```bash
   # Enable/disable camera preview
   curl -X POST http://localhost:5000/debug/preview \
     -H "Content-Type: application/json" \
     -d '{"enabled": true}'
   ```
   - Use case: Debug camera without full session

### Recommended for Production Deployment

**Keep these debug endpoints** during initial deployment for troubleshooting.

**Remove later** once system is stable:
```python
# In app/main.py - comment out for production:
# @app.post("/debug/trigger")
# @app.post("/debug/app-ready")
# @app.post("/debug/preview")
```

---

## UI Changes Summary

### Before (Debug Mode UI):
```
┌─────────────────────────────────┐
│ IDLE Screen                     │
│                                 │
│ [Mock ToF Button]  ← Removed    │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│ Control Panel                   │
│ [ToF Trigger]      ← Removed    │
│ [Trigger Session]  ← Kept       │
└─────────────────────────────────┘
```

### After (Production Mode UI):
```
┌─────────────────────────────────┐
│ IDLE Screen                     │
│                                 │
│ (Clean - no buttons)            │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│ Control Panel                   │
│ [Trigger Session]  ← For testing│
└─────────────────────────────────┘
```

---

## Deployment Checklist

### Before Starting Production

- [ ] ToF reader binary built and tested
- [ ] ToF sensor connected to I2C bus
- [ ] User added to `i2c` group
- [ ] `.env` has `TOF_READER_BINARY` path
- [ ] RealSense D435i connected
- [ ] Frontend rebuilt (to remove debug buttons)
- [ ] Backend restarted with new code

### Verify Production Mode

```bash
# 1. Check no ToF endpoints exist
curl -X POST http://localhost:5000/debug/tof-trigger
# Should return 404

# 2. Check ToF sensor running
journalctl -u mdai-controller | grep "ToF sensor active"

# 3. Check UI has no debug buttons
# Open http://localhost:3000
# IDLE screen should have NO buttons

# 4. Test real ToF trigger
# Wave hand in front of sensor (< 45cm)
# Session should start automatically
```

---

## Migration Steps

### 1. Rebuild Frontend

```bash
cd mdai-ui
npm run build

# Or for development
npm run dev
```

### 2. Restart Backend

```bash
cd controller
uvicorn app.main:app --reload --host 0.0.0.0 --port 5000
```

### 3. Test ToF Hardware

```bash
# Test ToF reader directly
./controller/tof/build/tof-reader --bus /dev/i2c-1 --addr 0x29

# Should output:
{"distance_mm": 450}
{"distance_mm": 445}
...
```

### 4. Test Complete Flow

```
1. Approach kiosk (distance < 450mm)
   → Session starts automatically
   
2. Step back (distance > 450mm)
   → Session cancels (if in progress)

3. No manual intervention needed!
```

---

## Summary

### Removed (Production Cleanup):

| Component | What Removed | Reason |
|-----------|--------------|--------|
| **Frontend** | Mock ToF button | No manual ToF simulation in production |
| **Frontend** | ToF Trigger button | ToF hardware controls flow |
| **Frontend** | ToF state tracking | Not needed without UI controls |
| **Backend** | `/debug/tof-trigger` | Hardware controls triggering |
| **Backend** | `/debug/tof-bypass` | No bypass in production |
| **Backend** | `simulate_tof_trigger()` | Hardware-only triggering |
| **Backend** | `set_tof_bypass()` | No bypass in production |
| **Backend** | `mock_distance_provider()` | Real hardware required |

### Kept (Essential Features):

| Component | What Kept | Reason |
|-----------|-----------|--------|
| **Frontend** | Trigger Session button | Manual testing |
| **Backend** | `/debug/trigger` | Development/testing |
| **Backend** | `/debug/app-ready` | Skip mobile pairing for tests |
| **Backend** | Real ToF sensor integration | Production requirement |

---

## Result

✅ **Clean production UI** - No confusing debug buttons  
✅ **Hardware-driven flow** - ToF sensor controls everything  
✅ **Fail-fast on missing hardware** - Clear error messages  
✅ **Production-ready logs** - Clean, informative  
✅ **Simplified codebase** - Less debug cruft  

The system now behaves like a **real production kiosk** with ToF sensor control! 🎯
