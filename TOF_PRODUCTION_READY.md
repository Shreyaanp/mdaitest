# ToF Sensor - Production Configuration

## Changes Made

### ✅ Removed Debug/Mock Code

**Files Modified:**
1. `controller/app/sensors/tof.py`
2. `controller/app/sensors/tof_process.py`  
3. `controller/app/session_manager.py`

### What Was Removed:

1. ❌ **Mock distance provider** - No more `mock_distance_provider()` fallback
2. ❌ **Unnecessary debug logging** - Reduced verbose logging
3. ❌ **Soft failures** - Now fails fast if ToF not available
4. ❌ **Optional ToF** - ToF is now required for system to start

---

## Production Behavior

### ✅ Fail-Fast on Missing Hardware

**Before:**
```python
if not self.settings.tof_reader_binary:
    tof_distance_provider = mock_distance_provider  # Silent fallback
```

**After:**
```python
if not self.settings.tof_reader_binary:
    raise RuntimeError("ToF reader binary path not configured")  # Fail immediately
```

### ✅ Fail-Fast on Missing Binary

**Before:**
```python
if not path.exists():
    logger.error("tof-reader binary not found")
    return  # Silent failure
```

**After:**
```python
if not path.exists():
    raise FileNotFoundError(f"ToF reader binary not found: {path}")  # Crash immediately
```

### ✅ Cleaner Logging

**Before:**
```
[DEBUG] Unexpected tof-reader payload: ...
[WARNING] tof-reader stderr: ...
[INFO] ToF polling stopped
[INFO] Starting ToF polling threshold=450 debounce_ms=200 interval_ms=50
```

**After:**
```
[INFO] ToF sensor active (threshold=450mm, debounce=200ms)
[ERROR] ToF sensor error: ...
[ERROR] ToF reader crashed (exit code 1)
```

---

## Configuration Required

### `.env` File MUST Include:

```bash
# ToF Sensor Configuration (REQUIRED)
TOF_READER_BINARY=/path/to/tof-reader
TOF_I2C_BUS=/dev/i2c-1
TOF_I2C_ADDRESS=0x29
TOF_THRESHOLD_MM=450
TOF_DEBOUNCE_MS=200
TOF_OUTPUT_HZ=20

# Optional
TOF_XSHUT_PATH=/sys/class/gpio/gpio123/value
```

### Build ToF Reader Binary

```bash
cd controller/tof/build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j4

# Verify
./tof-reader --help
```

### Test ToF Hardware

```bash
# Test reading
./tof-reader --bus /dev/i2c-1 --addr 0x29 --hz 20

# Expected output:
# {"distance_mm": 450}
# {"distance_mm": 445}
# {"distance_mm": 442}
```

---

## Startup Validation

### System Will Fail to Start If:

1. ❌ `TOF_READER_BINARY` not set in `.env`
2. ❌ Binary file doesn't exist
3. ❌ I2C device not accessible (`/dev/i2c-1`)
4. ❌ ToF sensor not responding
5. ❌ Permission denied (need `i2c` group membership)

### Expected Startup Sequence:

```
[INFO] Starting session manager
[INFO] ToF reader starting on /dev/i2c-1 @ 20Hz
[INFO] ToF sensor active (threshold=450mm, debounce=200ms)
[INFO] Session manager started in IDLE state (camera inactive)
```

### Error Examples:

**Missing Binary:**
```
RuntimeError: ToF reader binary path not configured. Set TOF_READER_BINARY in .env
```

**Binary Not Found:**
```
FileNotFoundError: ToF reader binary not found: /path/to/tof-reader
```

**Sensor Not Responding:**
```
[ERROR] ToF sensor error: I2C communication failed
[ERROR] ToF reader crashed (exit code 1)
```

---

## Permissions Setup

### Add User to I2C Group

```bash
# Add your user to i2c group
sudo usermod -a -G i2c $USER

# Verify
groups $USER

# Logout and login for changes to take effect
```

### Verify I2C Access

```bash
# Should work without sudo
ls -l /dev/i2c-1

# Test with i2cdetect (optional)
sudo apt-get install -y i2c-tools
i2cdetect -y 1
```

---

## Monitoring in Production

### Check ToF Status

```bash
# View logs
journalctl -u mdai-controller -f | grep -i "tof"

# Expected (healthy):
ToF sensor active (threshold=450mm, debounce=200ms)

# Errors to watch for:
ToF sensor error: ...
ToF reader crashed (exit code 1)
```

### Health Check Endpoint

```bash
# Check if ToF is working
curl http://localhost:5000/healthz

# Should return:
# {"status": "ok", "phase": "idle"}
```

### Manual Trigger Test

```bash
# Simulate ToF trigger
curl -X POST http://localhost:5000/debug/tof-trigger \
  -H "Content-Type: application/json" \
  -d '{"triggered": true, "distance_mm": 400}'

# Check logs for:
[INFO] ToF trigger=True distance=400 phase=SessionPhase.IDLE
```

---

## Troubleshooting

### Issue: "ToF reader binary path not configured"

**Solution:**
```bash
# Add to .env
echo "TOF_READER_BINARY=/full/path/to/tof-reader" >> .env

# Verify
grep TOF_READER_BINARY .env
```

### Issue: "FileNotFoundError: ToF reader binary not found"

**Solution:**
```bash
# Check binary exists
ls -l /path/to/tof-reader

# Rebuild if needed
cd controller/tof/build
make clean && make -j4
```

### Issue: "Permission denied" on I2C

**Solution:**
```bash
# Check permissions
ls -l /dev/i2c-1

# Add user to i2c group
sudo usermod -a -G i2c $USER

# OR run with sudo (not recommended)
sudo uvicorn app.main:app --host 0.0.0.0 --port 5000
```

### Issue: "ToF reader crashed (exit code 1)"

**Solution:**
```bash
# Test binary standalone
/path/to/tof-reader --bus /dev/i2c-1 --addr 0x29 --hz 20

# Check sensor connection
i2cdetect -y 1

# Look for address 0x29
# If not present, check wiring
```

---

## Systemd Service (Production Deployment)

```bash
# Create service file
sudo tee /etc/systemd/system/mdai-controller.service << 'EOF'
[Unit]
Description=mDAI Controller Service
After=network.target

[Service]
Type=simple
User=ichiro
WorkingDirectory=/home/ichiro/Desktop/mercleapp/mDai/mdaitest/controller
Environment="PATH=/home/ichiro/.pyenv/shims:/usr/bin:/bin"
ExecStart=/home/ichiro/.pyenv/shims/uvicorn app.main:app --host 0.0.0.0 --port 5000
Restart=always
RestartSec=5

# Fail if ToF not available
StartLimitBurst=3
StartLimitInterval=60

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable mdai-controller
sudo systemctl start mdai-controller

# Check status
sudo systemctl status mdai-controller

# View logs
journalctl -u mdai-controller -f
```

---

## Rollback (Emergency)

If you need to temporarily disable ToF requirement:

```bash
# Option 1: Set bypass in environment
export TOF_BYPASS=true
uvicorn app.main:app --host 0.0.0.0 --port 5000

# Option 2: Use mock provider (requires code change)
# In session_manager.py, temporarily add:
from .sensors.tof import mock_distance_provider
tof_distance_provider = mock_distance_provider
```

**Note:** Bypass should only be used for emergency debugging!

---

## Summary

✅ **ToF is now required** - System fails fast if not available  
✅ **Cleaner logging** - Production-ready error messages  
✅ **No silent fallbacks** - All failures are explicit  
✅ **Fail-fast startup** - Know immediately if hardware missing  
✅ **Better error messages** - Clear instructions on what to fix  

The system is now **production-ready** with proper hardware requirements!
