# 🚨 QUICK FIX: You're Running the Wrong Directory!

## The Problem

You have **TWO copies** of the project:

```
❌ /home/ichiro/Desktop/mercleapp/mDai/frontend/mdaitest/  ← OLD CODE (you're running this)
✅ /home/ichiro/Desktop/mercleapp/mDai/mdaitest/          ← NEW CODE (we edited this)
```

**All our fixes are in the second directory, but you're running the first one!**

---

## Proof

Your logs show **OLD code**:
```
RealSense hardware request acquired: session (total=1)  ← OLD FORMAT
RealSense hardware request acquired: preview (total=2)  ← PREVIEW ACTIVATING CAMERA (bug)
RuntimeError: no_viable_frame                           ← OLD BUG
```

New code should show:
```
RealSense hardware request acquired: session (count=1, total=1)  ← NEW FORMAT
Frame collection complete: 15 total, 8 passed liveness            ← NEW FEATURE
Saved 15 debug frames                                             ← NEW FEATURE
```

---

## The Fix (3 Steps)

### 1. Kill Old Process
```bash
# Stop the controller running from wrong directory
pkill -f "uvicorn app.main:app"
```

### 2. Start from CORRECT Directory
```bash
# Use the startup script
cd /home/ichiro/Desktop/mercleapp/mDai/mdaitest
./START_CONTROLLER.sh
```

**OR manually:**
```bash
cd /home/ichiro/Desktop/mercleapp/mDai/mdaitest/controller
source ../.venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 5000
```

### 3. Verify Correct Code is Running
```bash
# Trigger session
curl -X POST http://localhost:5000/debug/tof-trigger \
  -H "Content-Type: application/json" \
  -d '{"triggered": true}'

# Watch logs
tail -f logs/controller-runtime.log

# Look for NEW FORMAT:
# ✅ "RealSense hardware request acquired: session (count=1, total=1)"
# ✅ "Frame collection complete: X total, Y passed liveness"
# ✅ "Saved X debug frames"

# If you see OLD FORMAT, you're still in wrong directory!
```

---

## Expected Behavior After Fix

### ✅ Preview Should Work Smoothly:
- No glitching
- No opening/closing
- Stable 30 FPS stream
- No processing block failures

### ✅ Liveness Should Work:
- Frames pass liveness checks
- No "no_viable_frame" errors
- Debug frames saved to `captures/debug/`

### ✅ Logs Should Be Clean:
```
[INFO] ToF TRIGGERED (distance=400mm, phase=idle)
[INFO] Starting session from ToF trigger
[INFO] Phase → pairing_request
[INFO] Phase → qr_display
[INFO] Phase → waiting_activation
[INFO] Bridge message received: from_app
[INFO] Phase → human_detect
[INFO] RealSense hardware request acquired: session (count=1, total=1)  ← NEW!
[INFO] Activating RealSense pipeline (requests={'session': 1})
[INFO] Connected to Intel RealSense D435I (S/N 215322072881)
[INFO] Frame collection complete: 15 total, 8 passed liveness, best_score=0.750  ← NEW!
[INFO] Saved 15 debug frames  ← NEW!
[INFO] Saved best frame to captures/...
[INFO] Phase → uploading
```

### ✅ No Shutdown Errors:
```
# OLD (errors on shutdown):
asyncio.exceptions.CancelledError
ERROR: Exception in ASGI application

# NEW (clean shutdown):
[INFO] Session manager stopped
[INFO] Application shutdown complete
```

---

## Cleanup (Optional)

### Remove or Rename Old Directory
```bash
# Option 1: Rename (keep backup)
mv /home/ichiro/Desktop/mercleapp/mDai/frontend/mdaitest \
   /home/ichiro/Desktop/mercleapp/mDai/frontend/mdaitest.OLD

# Option 2: Delete (if you don't need it)
# rm -rf /home/ichiro/Desktop/mercleapp/mDai/frontend/mdaitest
```

---

## Troubleshooting

### "I'm in the right directory but still see old logs"

**Possible causes:**
1. Old process still running
```bash
# Kill all Python processes
pkill -9 -f uvicorn
pkill -9 -f python

# Start fresh
./START_CONTROLLER.sh
```

2. Wrong Python environment
```bash
# Verify virtual environment
which python
# Should show: /home/ichiro/Desktop/mercleapp/mDai/mdaitest/.venv/bin/python

# If not, activate:
source /home/ichiro/Desktop/mercleapp/mDai/mdaitest/.venv/bin/activate
```

3. Code not saved
```bash
# Check file modification time
stat controller/app/main.py
stat controller/app/session_manager.py

# Should show recent timestamps
```

---

## Final Checklist

- [ ] In correct directory: `/home/ichiro/Desktop/mercleapp/mDai/mdaitest/`
- [ ] Old processes killed
- [ ] Virtual environment activated
- [ ] Controller started with `./START_CONTROLLER.sh`
- [ ] Logs show NEW format: `(count=1, total=1)`
- [ ] No "no_viable_frame" errors
- [ ] No "processing block" restart loops
- [ ] Preview works smoothly
- [ ] No CancelledError on shutdown

---

## Quick Start

```bash
# 1. Go to CORRECT directory
cd /home/ichiro/Desktop/mercleapp/mDai/mdaitest

# 2. Kill old processes
pkill -f uvicorn

# 3. Start controller
./START_CONTROLLER.sh

# 4. In another terminal, test
curl -X POST http://localhost:5000/debug/tof-trigger \
  -H "Content-Type: application/json" \
  -d '{"triggered": true}'

# 5. Watch logs
tail -f logs/controller-runtime.log

# Should see NEW format and features!
```

---

## Summary

🔴 **Problem:** Running old code from wrong directory  
✅ **Solution:** Use `/home/ichiro/Desktop/mercleapp/mDai/mdaitest/`  
🚀 **Script:** `./START_CONTROLLER.sh` ensures correct directory  

**All your issues will disappear once you run from the correct location!** 🎯
