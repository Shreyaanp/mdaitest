# ⚠️ IMPORTANT: Directory Structure

## You Have TWO Copies of the Project!

### ✅ CORRECT Directory (We edited this one):
```
/home/ichiro/Desktop/mercleapp/mDai/mdaitest/
├── controller/          ← Use this one!
├── mdai-ui/
├── captures/
└── START_CONTROLLER.sh  ← New startup script
```

### ❌ WRONG Directory (Old code):
```
/home/ichiro/Desktop/mercleapp/mDai/frontend/mdaitest/
├── controller/          ← Don't use this one!
└── ...
```

---

## How to Use the CORRECT Directory

### Start Backend (Controller)
```bash
# Option 1: Use startup script
cd /home/ichiro/Desktop/mercleapp/mDai/mdaitest
./START_CONTROLLER.sh

# Option 2: Manual
cd /home/ichiro/Desktop/mercleapp/mDai/mdaitest/controller
uvicorn app.main:app --reload --host 0.0.0.0 --port 5000
```

### Start Frontend (UI)
```bash
cd /home/ichiro/Desktop/mercleapp/mDai/mdaitest/mdai-ui
npm run dev
```

---

## Verify You're Using Correct Code

### Check for new log format:
```bash
# CORRECT directory logs show:
RealSense hardware request acquired: session (count=1, total=1)
#                                             ^^^^^^ NEW FORMAT

# WRONG directory logs show:
RealSense hardware request acquired: session (total=1)
#                                    NO "count=" ← OLD FORMAT
```

### Check for new error handling:
```bash
# CORRECT directory should NOT crash on errors
# WRONG directory will crash

# Test:
curl -X POST http://localhost:5000/debug/tof-trigger \
  -H "Content-Type: application/json" \
  -d '{"triggered": true}'

# If session runs and handles errors gracefully → CORRECT
# If it crashes or shows old logs → WRONG
```

---

## Clean Up Old Directory (Optional)

```bash
# Backup old directory
mv /home/ichiro/Desktop/mercleapp/mDai/frontend/mdaitest \
   /home/ichiro/Desktop/mercleapp/mDai/frontend/mdaitest.backup

# Or delete if you don't need it
# rm -rf /home/ichiro/Desktop/mercleapp/mDai/frontend/mdaitest
```

---

## Summary

**All our fixes are in:**
```
/home/ichiro/Desktop/mercleapp/mDai/mdaitest/
```

**You've been running:**
```
/home/ichiro/Desktop/mercleapp/mDai/frontend/mdaitest/  ← OLD CODE!
```

**Use the startup script to avoid confusion:**
```bash
cd /home/ichiro/Desktop/mercleapp/mDai/mdaitest
./START_CONTROLLER.sh
```

This ensures you always run the correct directory! 🎯
