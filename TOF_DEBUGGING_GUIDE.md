# ToF Sensor Debugging Guide 🔍

## Problem: I2C Error 121 (Remote I/O error)

This error occurs when the VL53L0X sensor gets stuck in a bad state.

---

## 🛠️ Quick Fix (Most Common)

### Option 1: Reset Script (Recommended)
```bash
cd /home/ubuntu/Desktop/mdaitest
python3 reset_tof_sensor.py
```

**What it does:**
- Soft resets the sensor
- Clears stuck I2C states
- Verifies sensor is responding
- Tests a distance reading

**Expected output:**
```
✅ Sensor reset successful!
✅ Test reading: 1234mm
```

### Option 2: Live Debug Tool
```bash
cd /home/ubuntu/Desktop/mdaitest
python3 debug_tof_live.py
```

**What it does:**
- Continuously reads distances (10Hz)
- Shows real-time readings
- Displays trigger status (< 500mm)
- Calculates success rate

**Expected output:**
```
Time         Distance     Status                         Trigger?  
----------------------------------------------------------------------
18:30:15      1220mm      ✅ Normal (idle)                No        
18:30:16       450mm      🚨 WOULD TRIGGER SESSION       YES       
18:30:17      1180mm      ✅ Normal (idle) (Δ+730mm)     No        
```

---

## 🚨 Common Issues & Solutions

### 1. Error 121 on Backend Startup

**Symptoms:**
```
ERROR | Failed to initialize Python ToF sensor: [Errno 121] Remote I/O error
```

**Solution:**
```bash
# Stop the backend server (Ctrl+C)
python3 reset_tof_sensor.py
# Restart backend
```

**Why it happens:**
- Sensor was left in continuous mode from previous session
- I2C bus is in a stuck state
- Sensor needs soft reset

---

### 2. No Distance Readings

**Symptoms:**
- Backend starts OK but no `📏 Python ToF reading` logs
- No trigger when object placed near sensor

**Debug steps:**
```bash
# 1. Check if sensor is detected
sudo i2cdetect -y 1
# Should show "29" in the output

# 2. Run live debug tool
python3 debug_tof_live.py
# Watch for distance readings

# 3. Check backend logs
tail -f controller/backend.log | grep -i tof
```

---

### 3. Sensor Triggers Too Early/Late

**Current threshold:** 500mm (50cm)

**Adjust in `.env`:**
```bash
TOF_THRESHOLD_MM=300    # Trigger at 30cm (closer)
TOF_THRESHOLD_MM=700    # Trigger at 70cm (farther)
```

**Test without restarting backend:**
```bash
# Use mock endpoint
curl -X POST http://127.0.0.1:5000/debug/mock-tof \
  -H "Content-Type: application/json" \
  -d '{"triggered": true, "distance_mm": 250}'
```

---

### 4. Permission Denied (I2C)

**Symptoms:**
```
PermissionError: [Errno 13] Permission denied: '/dev/i2c-1'
```

**Solution:**
```bash
sudo usermod -a -G i2c $USER
sudo reboot
```

---

### 5. Sensor Not Detected (0x29 missing)

**Check detection:**
```bash
sudo i2cdetect -y 1
```

**If 29 is missing:**
1. Check wiring (VCC, GND, SDA, SCL)
2. Check power (3.3V, not 5V!)
3. Try different I2C bus: `sudo i2cdetect -y 0`
4. Power cycle sensor (unplug/replug)
5. Reboot: `sudo reboot`

---

## 📊 Understanding Distance Readings

| Distance | Meaning | Backend Action |
|----------|---------|----------------|
| 1000-1300mm | Normal idle distance | No action |
| 500-999mm | User approaching | Monitoring |
| < 500mm | User at sensor | **🚨 TRIGGER SESSION** |
| > 500mm for 1.5s | User walked away | **Cancel session** |

---

## 🔧 Debug Tools Reference

### 1. Reset Script (`reset_tof_sensor.py`)
**When to use:** 
- Backend fails to start with I2C error 121
- Sensor not responding
- After power cycle

**Features:**
- 3 retry attempts with exponential backoff
- Soft reset sequence
- Test reading verification
- Detailed diagnostic output

---

### 2. Live Debug Tool (`debug_tof_live.py`)
**When to use:**
- Verify sensor is working before starting backend
- Debug trigger distance threshold
- Monitor sensor behavior in real-time
- Calculate success rate

**Features:**
- Continuous readings (10Hz)
- Real-time trigger status
- Distance change delta
- Statistics (success rate, error count)
- Clean Ctrl+C shutdown

---

### 3. Mock ToF Endpoint (`/debug/mock-tof`)
**When to use:**
- Test session flow without physical sensor
- Simulate user approaching/leaving
- Debug session lifecycle

**Examples:**
```bash
# Simulate user approaching (trigger)
curl -X POST http://127.0.0.1:5000/debug/mock-tof \
  -H "Content-Type: application/json" \
  -d '{"triggered": true, "distance_mm": 250}'

# Simulate user leaving (cancel after 1.5s)
curl -X POST http://127.0.0.1:5000/debug/mock-tof \
  -H "Content-Type: application/json" \
  -d '{"triggered": false, "distance_mm": 1500}'
```

---

## 🚀 Recommended Workflow

### First Time / After Issues:

1. **Reset sensor:**
   ```bash
   python3 reset_tof_sensor.py
   ```

2. **Verify with live debug:**
   ```bash
   python3 debug_tof_live.py
   # Watch for steady readings
   # Press Ctrl+C after 10-20 readings
   ```

3. **Start backend:**
   ```bash
   cd controller
   source .venv/bin/activate
   uvicorn app.main:app --host 0.0.0.0 --port 5000
   ```

4. **Monitor logs:**
   ```bash
   tail -f controller/backend.log | grep -E "(ToF|session)"
   ```

---

## 📝 Backend Logs - What to Look For

### ✅ Good Startup:
```
🐍 Using Python ToF implementation
Initializing VL53L0X (attempt 1/3)...
VL53L0X found: Model ID 0xee, Revision ID 0x10
✅ VL53L0X initialization successful (test reading: 1234mm)
Python ToF sensor initialized on I2C bus 1, address 0x29
Python ToF provider started @ 10Hz
```

### ✅ Normal Operation:
```
📏 Python ToF reading: 1220mm > 500mm (no trigger)
📏 Python ToF reading: 1215mm > 500mm (no trigger)
```

### ✅ Trigger Event:
```
📏 Python ToF reading: 450mm ≤ 500mm (TRIGGER)
👆 ToF triggered (distance=450mm ≤ 500mm) - starting session
```

### ❌ Problem Indicators:
```
ERROR | Failed to initialize Python ToF sensor: [Errno 121]
WARNING | Init attempt 1/3 failed: [Errno 121]
ERROR | Failed to start ToF sensor: [Errno 121]
```

**Action:** Stop backend, run reset script, restart

---

## 🔍 Advanced Debugging

### Enable Verbose ToF Logging:

In `controller/app/sensors/python_tof.py`, change line 179:
```python
logger.debug("📏 Python ToF: No reading available")
```
to:
```python
logger.info("📏 Python ToF: No reading available")
```

### Check I2C Bus Speed:
```bash
sudo i2cdetect -y 1
# If slow, check /boot/config.txt for:
# dtparam=i2c_arm=on,i2c_baudrate=400000
```

### Monitor I2C Traffic:
```bash
sudo i2cdump -y 1 0x29
```

---

## 🎯 Success Criteria

After reset and backend start, you should see:

- ✅ Backend starts without errors
- ✅ Logs show "🐍 Using Python ToF implementation"
- ✅ Sensor initialization succeeds on first attempt
- ✅ Distance readings appear every 1 second
- ✅ Readings are in valid range (100-2000mm)
- ✅ Sensor triggers when object < 500mm
- ✅ No I2C errors in logs

---

## 📞 Still Having Issues?

1. **Check physical connections:**
   - VCC → 3.3V (NOT 5V!)
   - GND → Ground
   - SDA → GPIO 2 (pin 3)
   - SCL → GPIO 3 (pin 5)

2. **Check I2C is enabled:**
   ```bash
   sudo raspi-config
   # Interface Options → I2C → Enable
   ```

3. **Try I2C bus 0 instead of 1:**
   In `.env`, change:
   ```bash
   TOF_I2C_BUS=/dev/i2c-0
   ```

4. **Power cycle everything:**
   ```bash
   sudo shutdown -h now
   # Wait 10 seconds, power back on
   ```

---

## 📚 Files Reference

| File | Purpose |
|------|---------|
| `reset_tof_sensor.py` | Fix I2C Error 121, soft reset |
| `debug_tof_live.py` | Live distance readings, diagnostics |
| `test_tof_trigger.sh` | Test session flow with mock data |
| `controller/app/sensors/python_tof.py` | Main ToF implementation |
| `.env` | Configuration (threshold, bus, address) |

---

**Last Updated:** October 1, 2025  
**Status:** Tools tested and working ✅

