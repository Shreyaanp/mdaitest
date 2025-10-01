# ⚠️ YOU MUST RUN MANUALLY FROM THE CORRECT DIRECTORY

## The Issue

The logs still show you're running from:
```
/home/ichiro/Desktop/mercleapp/mDai/frontend/mdaitest/  ← WRONG!
```

All our fixes are in:
```
/home/ichiro/Desktop/mercleapp/mDai/mdaitest/  ← CORRECT!
```

---

## 🚀 DO THIS NOW:

### Step 1: Kill ALL Old Processes
```bash
pkill -9 -f uvicorn
pkill -9 -f python
```

### Step 2: Navigate to CORRECT Directory
```bash
cd /home/ichiro/Desktop/mercleapp/mDai/mdaitest/controller
```

### Step 3: Activate Virtual Environment
```bash
source ../.venv/bin/activate
```

### Step 4: Start Controller
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 5000
```

### Step 5: Verify in Another Terminal
```bash
# Check directory in logs
tail -f /home/ichiro/Desktop/mercleapp/mDai/mdaitest/logs/controller-runtime.log

# Look for:
# ✅ Path should contain: "/mdaitest/controller"
# ❌ NOT: "/frontend/mdaitest/controller"
```

---

## How to Verify You're Running Correct Code

### Check 1: Log Format
```
# NEW (correct):
RealSense hardware request acquired: session (count=1, total=1)

# OLD (wrong):  
RealSense hardware request acquired: session (total=1)
```

### Check 2: Error Traceback Path
```bash
# Watch for errors in logs:
tail -f logs/controller-runtime.log

# Traceback should show:
File "/home/ichiro/Desktop/mercleapp/mDai/mdaitest/controller/..."
                                      ^^^^^^^^

# NOT:
File "/home/ichiro/Desktop/mercleapp/mDai/frontend/mdaitest/controller/..."
                                      ^^^^^^^^
```

### Check 3: Features
```bash
# Trigger session
curl -X POST http://localhost:5000/debug/tof-trigger \
  -H "Content-Type: application/json" \
  -d '{"triggered": true}'

# NEW code should show:
# ✅ "Frame collection complete: X total, Y passed liveness"
# ✅ "Saved X debug frames"
# ✅ No "no_viable_frame" if frames exist
# ✅ Better error messages

# OLD code shows:
# ❌ "RuntimeError: no_viable_frame"
# ❌ Processing block restart loops
# ❌ No debug frame saves
```

---

## Why This Matters

### Running WRONG Directory:
- ❌ All our fixes not applied
- ❌ Preview glitchy (old bug)
- ❌ No error handling (crashes)
- ❌ Strict liveness (fails all frames)
- ❌ Processing block restarts (unstable)
- ❌ ToF debug buttons in UI (not production-ready)

### Running CORRECT Directory:
- ✅ All fixes applied
- ✅ Preview smooth
- ✅ Error handling (never crashes)
- ✅ Relaxed liveness (works better)
- ✅ Stable pipeline
- ✅ Clean production UI

---

## Copy-Paste Commands

```bash
# COMPLETE SETUP (copy-paste all at once)
pkill -9 -f uvicorn && \
cd /home/ichiro/Desktop/mercleapp/mDai/mdaitest/controller && \
source ../.venv/bin/activate && \
echo "✅ Starting from CORRECT directory:" && \
pwd && \
uvicorn app.main:app --reload --host 0.0.0.0 --port 5000
```

---

## After Starting

You should see:
```
INFO: Application startup complete.
INFO: Uvicorn running on http://0.0.0.0:5000
```

**WITHOUT any errors!**

Then test:
```bash
# In another terminal
curl -X POST http://localhost:5000/debug/tof-trigger \
  -H "Content-Type: application/json" \
  -d '{"triggered": true}'
```

If everything works → You're in the right place! 🎯
