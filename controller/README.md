# mdai controller

FastAPI-based supervisor that coordinates ToF triggers, RealSense capture, and the websocket bridge for the Jetson kiosk.

## Features (scaffold)

- `/healthz` liveness endpoint and `/preview` MJPEG feed for the kiosk iframe
- Local WebSocket (`/ws/ui`) broadcasting session phase updates to the React frontend
- Session manager that mints bridge tokens, manages the hardware websocket lifecycle, and orchestrates liveness capture + uploads
- ToF polling abstraction with debounce and pluggable distance provider
- RealSense service wrapper with an embedded MediaPipe liveness implementation (`controller/app/sensors/realsense.py`)

## Running locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r controller/requirements.txt
uvicorn controller.app.main:app --reload --host 0.0.0.0 --port 5000
```

Populate the root `.env` with bridge settings:

```
BACKEND_API_URL=https://mdai.mercle.ai
BACKEND_WS_URL=wss://mdai.mercle.ai/ws
HARDWARE_API_KEY=HARDWARE-DEV-KEY
```

(Existing `VITE_` entries remain for the React build.)

### Enabling the VL53L0X ToF sensor

1. Build the native reader once on the Jetson:

   ```bash
   mkdir -p controller/tof/build
   cmake -S controller/tof -B controller/tof/build
   cmake --build controller/tof/build --target tof-reader
   sudo cp controller/tof/build/tof-reader /usr/local/bin/
   ```

2. Point the controller at the binary and bus wiring via `.env`:

   ```
   TOF_READER_BINARY=/usr/local/bin/tof-reader
   TOF_I2C_BUS=/dev/i2c-1
   TOF_I2C_ADDRESS=0x29
   # Optional: expose XSHUT GPIO if you wired it
   # TOF_XSHUT_PATH=/sys/class/gpio/gpio216/value
   # TOF_OUTPUT_HZ=20
   ```

   With these values set the FastAPI service will spawn the process reader
   at startup and emit real ToF transitions instead of the mocked provider.

## Next integration steps

1. Tune the ToF thresholds/noise filtering now that hardware measurements are available through `TOF_*` settings.
2. Enable hardware capture in `RealSenseService` by ensuring the Jetson has the `pyrealsense2`, `mediapipe`, and `opencv-python` builds installed.
3. Flesh out bridge message handling (additional app ↔ hardware events) once the mobile contract is final.
4. Add automated tests for session transitions (happy path, cancellation, error handling) using `asyncio` fakes.
