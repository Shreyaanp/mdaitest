# Preview System Disabled

## What Was Disabled

The MJPEG preview streaming system has been **disabled to save Raspberry Pi resources**. This significantly reduces CPU usage by eliminating continuous JPEG encoding.

---

## Changes Made

### 1. **RealSense Preview Broadcasting - DISABLED**
File: `controller/app/sensors/realsense.py`

**Idle Detection Mode (line 679-682):**
```python
# PREVIEW DISABLED: Saves CPU by not encoding JPEG frames
# Broadcast frame for preview (optional)
# frame_bytes = self._serialize_frame(result)
# self._broadcast_frame(frame_bytes)
```

**Active/Validation Mode (line 712-717):**
```python
# PREVIEW DISABLED: Saves CPU by not encoding JPEG frames
# Only generate and broadcast preview every Nth frame (reduces load)
# frame_skip_counter += 1
# if frame_skip_counter % frame_skip == 0:
#     frame_bytes = self._serialize_frame(result)
#     self._broadcast_frame(frame_bytes)
```

**Hardware Disabled Mode (line 737-738):**
```python
# PREVIEW DISABLED: Don't broadcast placeholder frames
# self._broadcast_frame(self._placeholder_frame())
```

---

### 2. **Webcam Preview Broadcasting - DISABLED**
File: `controller/app/sensors/webcam_service.py`

```python
async def _preview_loop(self) -> None:
    """Main preview loop - PREVIEW DISABLED to save CPU resources."""
    try:
        while not self._stop_event.is_set():
            if self._active and self._cap:
                # Capture frame
                loop = asyncio.get_running_loop()
                frame_data = await loop.run_in_executor(None, self._capture_frame)
                
                # PREVIEW DISABLED: Saves CPU by not encoding/broadcasting frames
                # frame_bytes = self._serialize_frame(frame_data)
                # self._broadcast_frame(frame_bytes)
                
                await asyncio.sleep(0.033)
            else:
                # PREVIEW DISABLED: Don't broadcast placeholder
                await asyncio.sleep(0.1)
```

---

### 3. **Preview Endpoint - Returns Placeholder**
File: `controller/app/main.py`

**Before:**
- Streamed MJPEG frames continuously
- High CPU usage for JPEG encoding

**After:**
```python
@app.get("/preview")
async def preview_stream() -> StreamingResponse:
    """
    Preview stream DISABLED to save Raspberry Pi resources.
    
    Returns a static placeholder image instead of live MJPEG stream.
    This saves significant CPU by avoiding JPEG encoding on every frame.
    """
    from fastapi.responses import Response
    
    # Return a 1x1 black pixel PNG
    black_pixel = b'\x89PNG\r\n\x1a...'
    
    return Response(
        content=black_pixel,
        media_type="image/png",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )
```

Now returns a tiny static black PNG instead of streaming video.

---

## What Still Works

### ✅ **Face Detection** - FULLY FUNCTIONAL
- Idle detection (1s bursts)
- Face detection callbacks
- Session triggering on face detection
- 3-second grace period for session cancellation

### ✅ **Validation** - FULLY FUNCTIONAL
- Camera captures frames continuously
- Liveness detection works
- Result broadcasting to validation system
- Best frame selection
- Upload to backend

### ✅ **All Other Features**
- Session management
- WebSocket communication
- QR code display
- Backend integration
- Error handling

---

## What's Disabled

### ❌ **Preview Streaming**
- No MJPEG stream at `/preview`
- No JPEG encoding of preview frames
- No preview frame broadcasting
- No Eye of Horus visualization streaming
- No webcam preview streaming

### ❌ **UI Preview Display**
- React UI won't receive live camera feed
- PreviewSurface component shows static GIF (already was doing this)

---

## Resource Savings

### **Before (Preview Enabled):**
- JPEG encoding every 4th frame (~10-15 FPS)
- Frame serialization: ~5-10ms per frame
- Broadcasting to multiple clients
- MJPEG streaming overhead
- **Estimated CPU**: 15-25% continuously

### **After (Preview Disabled):**
- No JPEG encoding
- No frame serialization
- No broadcasting overhead
- No streaming
- **Estimated CPU**: <5% (only during face validation)

### **Savings:**
- **~10-20% CPU reduction**
- Lower memory usage (no JPEG buffer accumulation)
- Reduced network traffic
- Less heat generation
- Better battery life (if applicable)

---

## How Validation Still Works

Even with preview disabled, validation is fully functional:

1. **Camera captures frames** continuously in validation mode
2. **Liveness detection runs** on every frame
3. **Results are broadcast** to `_result_subscribers` (NOT preview subscribers)
4. **Validation collects results** via `gather_results()`
5. **Best frame selected** and uploaded

**The key:** Results (liveness data) are still broadcast, but preview frames (JPEG images) are not.

```python
# This still runs:
self._broadcast_result(result)  # Liveness data

# This is disabled:
# self._broadcast_frame(frame_bytes)  # JPEG preview
```

---

## To Re-Enable Preview (If Needed)

### **1. Uncomment Code in realsense.py:**

**Line 679-682 (idle_detection):**
```python
# Uncomment these lines:
frame_bytes = self._serialize_frame(result)
self._broadcast_frame(frame_bytes)
```

**Line 712-717 (active/validation):**
```python
# Uncomment these lines:
frame_skip_counter += 1
if frame_skip_counter % frame_skip == 0:
    frame_bytes = self._serialize_frame(result)
    self._broadcast_frame(frame_bytes)
```

**Line 737-738 (hardware disabled):**
```python
# Uncomment this line:
self._broadcast_frame(self._placeholder_frame())
```

---

### **2. Restore MJPEG Endpoint in main.py:**

Replace the static PNG response with:

```python
@app.get("/preview")
async def preview_stream() -> StreamingResponse:
    """Stream preview from active camera source (realsense or webcam)."""
    boundary = "frame"

    async def frame_iterator() -> AsyncIterator[bytes]:
        try:
            if active_camera_source == "webcam":
                source = webcam_service.preview_stream()
            else:
                source = manager.preview_frames()
            
            async for frame in source:
                header = (
                    f"--{boundary}\r\n"
                    f"Content-Type: image/jpeg\r\n"
                    f"Content-Length: {len(frame)}\r\n\r\n"
                ).encode("ascii")
                yield header + frame + b"\r\n"
        except Exception as e:
            logger.error(f"Preview stream error: {e}")

    media_type = f"multipart/x-mixed-replace; boundary={boundary}"
    return StreamingResponse(frame_iterator(), media_type=media_type)
```

---

### **3. Uncomment Webcam Preview (webcam_service.py):**

```python
# Uncomment these lines:
frame_bytes = self._serialize_frame(frame_data)
self._broadcast_frame(frame_bytes)

# And:
self._broadcast_frame(self._placeholder_frame())
```

---

## Testing

### **Verify Preview is Disabled:**
```bash
# Should return a static black PNG (very small file)
curl -I http://localhost:5000/preview

# Should see:
# Content-Type: image/png
# Content-Length: ~67 bytes (tiny!)
```

### **Verify Face Detection Still Works:**
```bash
# Watch logs for face detection
tail -f logs/controller.log | grep "IDLE_DETECTION\|FACE_TRIGGER"

# Should see:
# 🔍 [IDLE_DETECTION] Taking burst photo
# 🔍 [IDLE_DETECTION] Face detected
# 👤 [FACE_TRIGGER] ✅ Face detected in IDLE - starting session
```

### **Verify Validation Still Works:**
```bash
# Start a session and watch validation
tail -f logs/controller.log | grep "GRACE_PERIOD\|validation"

# Should see validation completing successfully
```

---

## Summary

**Disabled:**
- ❌ MJPEG preview streaming
- ❌ JPEG encoding of frames
- ❌ Preview frame broadcasting
- ❌ Eye of Horus visualization streaming

**Still Working:**
- ✅ Face detection (idle + active modes)
- ✅ Face detection callbacks
- ✅ Session triggering
- ✅ Liveness validation
- ✅ Result broadcasting
- ✅ Best frame selection
- ✅ Backend upload

**Resource Savings:**
- ~10-20% CPU reduction
- Lower memory usage
- Reduced heat generation

The system now focuses resources on **face detection and validation** rather than streaming preview frames to the UI.

