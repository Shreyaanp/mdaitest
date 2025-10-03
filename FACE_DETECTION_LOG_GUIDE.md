# Face Detection Log Guide

## Overview
Comprehensive logging has been added to track the RealSense face detection flow. All logs are prefixed with emoji tags for easy filtering.

---

## Log Prefixes & Tags

| Prefix | Component | Description |
|--------|-----------|-------------|
| `🎥 [STARTUP]` | System startup | Camera initialization |
| `🔍 [IDLE_DETECTION]` | Idle detection loop | 1s burst photo captures |
| `⚙️ [MODE_SWITCH]` | Mode changes | Camera operational mode switches |
| `👤 [FACE_TRIGGER]` | Face callbacks | Face detection events & session triggers |
| `🎬 [SESSION_START]` | Session start | New session begins |
| `📷 [SESSION_FLOW]` | Session flow | Camera mode changes during session |
| `⏳ [GRACE_PERIOD]` | Grace period | 3s face detection grace period |
| `🏁 [SESSION_END]` | Session end | Cleanup and return to idle |

---

## Expected Log Flow

### 1. **System Startup**
```
🎥 [STARTUP] Starting RealSense service...
🎥 [STARTUP] Activating camera hardware for idle detection...
🎥 [STARTUP] Setting operational mode to idle_detection...
⚙️ [MODE_SWITCH] Operational mode: idle_detection → idle_detection
⚙️ [MODE_SWITCH] Mode details:
   - idle_detection: 1s bursts, face detection only
   - active: Continuous, face detection only (warm state)
   - validation: Full liveness with depth checks
⚙️ [MODE_SWITCH] Now in 'idle_detection' mode
🎥 [STARTUP] ✅ RealSense started in idle_detection mode
🎥 [STARTUP] 🔍 Camera will take 1-second burst photos to detect faces
🎥 [STARTUP] 👤 Face detection will trigger session start
```

### 2. **Idle Detection Loop (Every 1 Second)**

#### No Face:
```
🔍 [IDLE_DETECTION] Taking burst photo (interval=1.0s)
🔍 [IDLE_DETECTION] No face detected (reason=no_face_detected)
```

#### Face Detected:
```
🔍 [IDLE_DETECTION] Taking burst photo (interval=1.0s)
🔍 [IDLE_DETECTION] Face detected (bbox=(120, 80, 520, 400))
🔍 [IDLE_DETECTION] Face detection state changed: False → True
🔍 [IDLE_DETECTION] Calling 1 registered callback(s)
👤 [FACE_TRIGGER] Received face detection event: detected=True, phase=idle
👤 [FACE_TRIGGER] ✅ Face detected in IDLE - starting session
🔍 [IDLE_DETECTION] Callback 1/1 executed successfully
```

### 3. **Session Start**
```
🎬 [SESSION_START] ================================
🎬 [SESSION_START] New session starting
🎬 [SESSION_START] ================================
📷 [SESSION_START] Camera switched to active mode (warm state)
⚙️ [MODE_SWITCH] Operational mode: idle_detection → active
⚙️ [MODE_SWITCH] Now in 'active' mode
```

### 4. **Early Session Phases**

#### Face Remains (Good):
```
👤 [FACE_TRIGGER] Received face detection event: detected=True, phase=pairing_request
👤 [FACE_TRIGGER] Face still detected (good)
```

#### Face Lost (Warning):
```
👤 [FACE_TRIGGER] Received face detection event: detected=False, phase=hello_human
👤 [FACE_TRIGGER] ⚠️ Face lost in hello_human - starting 3s countdown...
👤 [FACE_TRIGGER] Cancel task created: face-delayed-cancel
👤 [FACE_TRIGGER] Countdown started - will cancel in 3s if face not re-detected
```

#### Face Returns (Saved):
```
👤 [FACE_TRIGGER] Received face detection event: detected=True, phase=hello_human
👤 [FACE_TRIGGER] ✅ Face re-detected after 1.2s - cancel countdown aborted
👤 [FACE_TRIGGER] Cancelling countdown task: face-delayed-cancel
👤 [FACE_TRIGGER] ✅ Cancel countdown aborted (face detected)
```

#### Session Cancelled (User Left):
```
👤 [FACE_TRIGGER] 🚶 No face for 3.0s - CANCELLING SESSION
👤 [FACE_TRIGGER] Session task cancelled due to no face
⚠️ Session cancelled (user walked away)
```

### 5. **Validation Phase**
```
📷 [SESSION_FLOW] Switching camera to validation mode (full liveness checks)
⚙️ [MODE_SWITCH] Operational mode: active → validation
⚙️ [MODE_SWITCH] Now in 'validation' mode
📷 [SESSION_FLOW] Camera switched to validation mode
📸 [SESSION_FLOW] Starting human presence validation
```

#### Grace Period:
```
⏳ [GRACE_PERIOD] Waiting up to 3.0s for face detection...
⏳ [GRACE_PERIOD] Timer resets each time face is detected
⏳ [GRACE_PERIOD] No face yet (0.5s / 3.0s)
⏳ [GRACE_PERIOD] No face yet (1.5s / 3.0s)
⏳ [GRACE_PERIOD] 👤 Face detected after 1.8s - RESETTING TIMER
⏳ [GRACE_PERIOD] ✅ Face detected, exiting grace period
⏳ [GRACE_PERIOD] Grace period complete, starting validation
```

Or if no face:
```
⏳ [GRACE_PERIOD] ⚠️ No face detected during 3.0s grace period, proceeding anyway...
⏳ [GRACE_PERIOD] Grace period complete, starting validation
```

### 6. **Session End**
```
📸 [SESSION_FLOW] Validation completed successfully
✅ Session completed successfully
🏁 [SESSION_END] Session cleanup starting
📷 [SESSION_END] Returning camera to idle_detection mode
⚙️ [MODE_SWITCH] Operational mode: validation → idle_detection
⚙️ [MODE_SWITCH] Now in 'idle_detection' mode
📷 [SESSION_END] Camera returned to idle_detection mode (1s burst intervals)
🏁 [SESSION_END] ================================
🏁 [SESSION_END] Session ended, back to IDLE
🏁 [SESSION_END] ================================
```

---

## Troubleshooting with Logs

### Issue: Camera not detecting faces in IDLE

**Look for:**
```
🔍 [IDLE_DETECTION] Taking burst photo (interval=1.0s)
🔍 [IDLE_DETECTION] No face detected (reason=no_face_detected)
```

**Solution:** Check camera angle, lighting, distance

---

### Issue: Sessions starting randomly

**Look for:**
```
🔍 [IDLE_DETECTION] Face detected (bbox=...)
👤 [FACE_TRIGGER] ✅ Face detected in IDLE - starting session
```

**Check:** bbox coordinates - are they valid face regions?

---

### Issue: Sessions cancelling unexpectedly

**Look for:**
```
👤 [FACE_TRIGGER] ⚠️ Face lost in <phase> - starting 3s countdown...
👤 [FACE_TRIGGER] 🚶 No face for 3.0s - CANCELLING SESSION
```

**Solution:** User is walking away - check camera positioning

---

### Issue: Grace period always timing out

**Look for:**
```
⏳ [GRACE_PERIOD] No face yet (0.5s / 3.0s)
⏳ [GRACE_PERIOD] No face yet (1.5s / 3.0s)
⏳ [GRACE_PERIOD] No face yet (2.5s / 3.0s)
⏳ [GRACE_PERIOD] ⚠️ No face detected during 3.0s grace period
```

**Solution:** Face detection not working during validation - check camera warmup

---

### Issue: Camera not switching modes

**Look for:**
```
⚙️ [MODE_SWITCH] Operational mode: <old> → <new>
```

**If missing:** Mode switch call failed - check for exceptions

---

## Useful grep Commands

### Filter by component:
```bash
# Startup logs
grep "🎥 \[STARTUP\]" logs/controller.log

# Idle detection only
grep "🔍 \[IDLE_DETECTION\]" logs/controller.log

# Face triggers
grep "👤 \[FACE_TRIGGER\]" logs/controller.log

# Mode switches
grep "⚙️ \[MODE_SWITCH\]" logs/controller.log

# Grace period
grep "⏳ \[GRACE_PERIOD\]" logs/controller.log

# Session lifecycle
grep -E "(🎬 \[SESSION_START\]|🏁 \[SESSION_END\])" logs/controller.log
```

### Track a full session:
```bash
# From face detection to end
grep -E "(👤 \[FACE_TRIGGER\]|🎬 \[SESSION|⚙️ \[MODE|⏳ \[GRACE|🏁 \[SESSION_END\])" logs/controller.log
```

### Debug face detection issues:
```bash
# All face detection events
grep -E "(🔍 \[IDLE_DETECTION\]|👤 \[FACE_TRIGGER\])" logs/controller.log | tail -100
```

---

## Log Levels

- `INFO`: Normal operation, state changes, important events
- `DEBUG`: Detailed operation, every burst photo, callback execution
- `WARNING`: Unexpected but handled situations (no face in grace period)
- `ERROR`: Failures that need attention

---

## Debug Mode

To see detailed burst capture logs (every 1 second), set log level to DEBUG:

```python
# In controller/app/main.py or via environment
logging.basicConfig(level=logging.DEBUG)
```

This will show:
```
🔍 [IDLE_DETECTION] Taking burst photo (interval=1.0s)
🔍 [IDLE_DETECTION] No face detected (reason=no_face_detected)
👤 [FACE_TRIGGER] Received face detection event: detected=False, phase=idle
👤 [FACE_TRIGGER] No face in IDLE (ignoring)
```

---

## Summary

**Key logs to watch:**
1. ✅ Startup: `🎥 [STARTUP]` - confirms camera in idle mode
2. 🔁 Burst photos: `🔍 [IDLE_DETECTION]` - every 1 second
3. 🚀 Session trigger: `👤 [FACE_TRIGGER] ✅ Face detected in IDLE`
4. 🔄 Mode changes: `⚙️ [MODE_SWITCH]` - idle → active → validation → idle
5. ⏳ Grace period: `⏳ [GRACE_PERIOD]` - 3s wait with timer reset
6. 🏁 Session end: `🏁 [SESSION_END]` - back to idle

All logs are tagged with emojis and bracketed component names for easy filtering and debugging.

