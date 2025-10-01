# 🚀 ToF Sensor - Quick Start

## ✅ Status: Sensor Reset and Working!

Your ToF sensor has been reset and is now reading **20mm** (something very close).

---

## 🎯 Next Steps

### 1. Clear any objects near the sensor
Move your hand or any objects away from the sensor (at least 1 meter away).

### 2. Start the backend server
```bash
cd /home/ubuntu/Desktop/mdaitest/controller
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 5000
```

### 3. Watch for these logs:
```
🐍 Using Python ToF implementation
✅ VL53L0X initialization successful (test reading: 1234mm)
Python ToF provider started @ 10Hz
📏 Python ToF reading: 1220mm > 500mm (no trigger)
```

### 4. Test the trigger
- **Physical test:** Move your hand slowly toward the sensor
- **Watch logs:** When distance < 500mm, you'll see:
  ```
  📏 Python ToF reading: 450mm ≤ 500mm (TRIGGER)
  👆 ToF triggered (distance=450mm ≤ 500mm) - starting session
  ```

---

## 🛠️ If Backend Fails to Start

Run this first:
```bash
cd /home/ubuntu/Desktop/mdaitest
python3 reset_tof_sensor.py
```

Then restart the backend.

---

## 🐛 Debug Tools Available

### Live Distance Monitor
```bash
python3 debug_tof_live.py
```
Shows real-time distances and trigger status. Press Ctrl+C to stop.

### Test Session Flow (Mock)
```bash
./test_tof_trigger.sh
```
Simulates user approaching/leaving without physical sensor.

---

## ⚙️ Current Settings

| Setting | Value | Description |
|---------|-------|-------------|
| Threshold | 500mm (50cm) | Distance to trigger session |
| Debounce | 1500ms (1.5s) | Time before cancel |
| Polling | 10Hz | Readings per second |
| I2C Bus | /dev/i2c-1 | I2C bus path |
| Address | 0x29 | Sensor I2C address |

Change in `.env` file if needed.

---

## 📚 Full Documentation

- **Debugging Guide:** `TOF_DEBUGGING_GUIDE.md`
- **Integration Details:** `PYTHON_TOF_INTEGRATION_COMPLETE.md`
- **Quick Reference:** `QUICK_START_PYTHON_TOF.md`

---

## ✅ What Got Fixed

1. **Added retry logic** (3 attempts with backoff)
2. **Soft reset on startup** (clears stuck I2C states)
3. **Test reading verification** (confirms sensor working)
4. **Better error messages** (detailed diagnostics)
5. **Debug tools** (reset script, live monitor)

---

## 🎉 You're Ready!

Your ToF sensor integration is complete. Start the backend and test it out! 🚀

**Current Reading:** 20mm (move objects away for normal operation)


