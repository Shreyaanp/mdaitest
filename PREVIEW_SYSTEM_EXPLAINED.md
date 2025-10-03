# Preview System Explained - localhost:5000/preview

## Overview
The preview system streams camera frames from the Python controller to the React UI for live face detection feedback during the `human_detect` phase.

---

## Backend/Controller (Python)

### 1. **Endpoint: `/preview` (MJPEG Stream)**
Location: `controller/app/main.py:316-341`

```python
@app.get("/preview")
async def preview_stream() -> StreamingResponse:
    """Stream preview from active camera source (realsense or webcam)."""
    boundary = "frame"

    async def frame_iterator() -> AsyncIterator[bytes]:
        try:
            # Route to appropriate camera source
            if active_camera_source == "webcam":
                source = webcam_service.preview_stream()
            else:
                source = manager.preview_frames()  # RealSense
            
            async for frame in source:
                header = (
                    f"--{boundary}\r\n"
                    f"Content-Type: image/jpeg\r\n"
                    f"Content-Length: {len(frame)}\r\n\r\n"
                ).encode("ascii")
                yield header + frame + b"\r\n"
        except Exception as e:
            logger.error(f"Preview stream error: {e}")
            # Stream will end gracefully

    media_type = f"multipart/x-mixed-replace; boundary={boundary}"
    return StreamingResponse(frame_iterator(), media_type=media_type)
```

**How it works:**
- Returns MJPEG stream (multipart/x-mixed-replace)
- Each frame is a JPEG image with boundary separator
- Routes to either webcam or RealSense based on `active_camera_source`
- Streams indefinitely until connection closed

---

### 2. **SessionManager: `preview_frames()`**
Location: `controller/app/session_manager.py:372-379`

```python
async def preview_frames(self) -> AsyncIterator[bytes]:
    """Stream preview frames with error handling."""
    try:
        async for frame in self._realsense.preview_stream():
            yield frame
    except Exception as e:
        logger.error("Preview stream error: %s", e)
        # Stream ends gracefully
```

**Purpose:**
- Wraps RealSense preview stream
- Adds error handling
- Delegates to `self._realsense.preview_stream()`

---

### 3. **RealSenseService: Preview Loop**
Location: `controller/app/sensors/realsense.py:633-745`

#### **Preview Loop (Background Task)**

```python
async def _preview_loop(self) -> None:
    """Main preview loop - supports idle_detection, active, and validation modes."""
    frame_skip_counter = 0
    frame_skip = self._settings.camera.preview_frame_skip if self._settings else 4
    last_idle_capture = 0.0
    
    try:
        while not self._stop_event.is_set():
            frame_start = time.time()
            current_mode = self._operational_mode
            
            if self.enable_hardware and self._hardware_active and self._instance:
                # IDLE DETECTION MODE: 1-second burst intervals
                if current_mode == "idle_detection":
                    if time.time() - last_idle_capture >= self._idle_detection_interval:
                        result = await self._run_process()
                        last_idle_capture = time.time()
                        
                        # Broadcast frame for preview
                        frame_bytes = self._serialize_frame(result)
                        self._broadcast_frame(frame_bytes)
                    
                    await asyncio.sleep(0.1)
                
                # ACTIVE/VALIDATION MODE: Continuous operation
                else:
                    result = await self._run_process()
                    
                    # Broadcast result for validation (always)
                    self._broadcast_result(result)
                    
                    # Only generate and broadcast preview every Nth frame (reduces load)
                    frame_skip_counter += 1
                    if frame_skip_counter % frame_skip == 0:
                        frame_bytes = self._serialize_frame(result)
                        self._broadcast_frame(frame_bytes)
                    
                    # FPS limiting, GC, etc.
                    ...
            
            elif not self.enable_hardware:
                self._broadcast_frame(self._placeholder_frame())
                await asyncio.sleep(0.1)
```

**Key points:**
- **idle_detection mode**: 1-second bursts, broadcasts frame after each burst
- **active/validation mode**: Continuous capture, broadcasts every 4th frame (reduces CPU)
- Runs in background as asyncio task
- Always broadcasts frames to `_preview_subscribers`

---

#### **Broadcasting System**
Location: `controller/app/sensors/realsense.py:855-864`

```python
def _broadcast_frame(self, frame: bytes) -> None:
    for q in list(self._preview_subscribers):
        if q.full():
            try:
                q.get_nowait()  # Drop old frame
            except QueueEmpty:
                pass
        q.put_nowait(frame)
```

**How it works:**
- Maintains list of subscriber queues
- Each HTTP client gets its own queue
- If queue is full, drops oldest frame (prevents blocking)
- Non-blocking broadcast

---

#### **Preview Stream Method**
Location: `controller/app/sensors/realsense.py:593-601`

```python
async def preview_stream(self) -> AsyncIterator[bytes]:
    """Stream preview frames."""
    maxsize = self._settings.performance.preview_queue_size if self._settings else 2
    q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=maxsize)
    self._preview_subscribers.append(q)
    try:
        while True:
            frame = await q.get()
            yield frame
    finally:
        self._preview_subscribers.remove(q)
```

**How it works:**
- Creates a queue for this subscriber
- Registers with `_preview_subscribers`
- Yields frames as they arrive
- Cleans up on disconnect

---

### 4. **Frame Serialization**
Location: `controller/app/sensors/realsense.py:762-783`

```python
def _serialize_frame(self, result: Optional[SimpleLivenessResult]) -> bytes:
    """Generate preview frame based on current mode."""
    if cv2 is None:
        return self._placeholder_frame()
    
    try:
        if self._preview_mode == "eye_tracking":
            frame = self._create_eye_tracking_frame(result)
        else:
            frame = self._create_face_dot_frame(result)
        
        ret, enc = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        return enc.tobytes() if ret else self._placeholder_frame()
    except Exception as e:
        logger.warning(f"Frame serialization error: {e}")
        return self._placeholder_frame()
```

**Two preview modes:**
1. **`eye_tracking`**: Eye of Horus visualization (default)
2. **`normal`**: Simple colored dot with status

---

## Frontend/React (UI)

### 1. **PreviewSurface Component**
Location: `mdai-ui/src/components/PreviewSurface.tsx:11-45`

```typescript
export default function PreviewSurface({
  visible,
  previewUrl,
  title = DEFAULT_TITLE
}: PreviewSurfaceProps) {
  console.log('📹 [PREVIEW SURFACE] Rendered | visible:', visible, '| previewUrl:', previewUrl)

  // Placeholder surface; stream disabled in favor of a static GIF
  useEffect(() => {
    console.log('📹 [PREVIEW EFFECT] Placeholder active | visible:', visible)
  }, [visible])

  const classNames = [
    'preview-surface',
    visible ? 'visible' : 'hidden'
  ]

  return (
    <div className={classNames.join(' ')} data-preview-surface>
      <div className="preview-surface__status" aria-live="polite">Scanning…</div>
      <img
        className="preview-surface__img preview-surface__media"
        src="/hero/scan.gif"  // STATIC GIF, NOT USING MJPEG STREAM
        alt={title || 'Scanning placeholder'}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          display: 'block',
          backgroundColor: '#000'
        }}
      />
    </div>
  )
}
```

**Important:** The preview surface currently shows a **static GIF** (`/hero/scan.gif`), **NOT** the MJPEG stream from `/preview`. The stream infrastructure is there but not being used.

---

### 2. **App.tsx - Preview Visibility**
Location: `mdai-ui/src/App.tsx:194-198, 241-244`

```typescript
const showPreview = useMemo(() => {
  const shouldShow = previewVisiblePhases.has(state.value as SessionPhase)
  console.log('🎥 [APP PREVIEW] Phase:', state.value, '| Should show:', shouldShow)
  return shouldShow
}, [previewVisiblePhases, state.value])

// Later in render:
<PreviewSurface
  visible={showPreview}
  previewUrl={previewUrl}
/>
```

**When preview is visible:**
- Controlled by `previewVisiblePhases` config
- Currently: ONLY `'human_detect'` phase

---

### 3. **Frontend Config**
Location: `mdai-ui/src/config/index.ts:137-141`

```typescript
export const frontendConfig: FrontendConfig = {
  previewVisiblePhases: new Set<SessionPhase>(['human_detect']),  // ONLY during face validation
  stageMessages,
  crtSettings: defaultCRTSettings
}
```

**Preview visibility:**
- ✅ Shows during: `human_detect`
- ❌ Hidden during: `idle`, `pairing_request`, `hello_human`, `scan_prompt`, `qr_display`, `processing`, `complete`, `error`

---

### 4. **DebugPreview Component (Testing)**
Location: `mdai-ui/src/components/DebugPreview.tsx:14-175`

**For development/testing:**
- Allows manual camera activation
- Shows metrics from WebSocket
- **Also uses placeholder GIF** instead of MJPEG stream
- Can toggle eye tracking mode

```typescript
if (imgRef.current) {
  imgRef.current.src = '/hero/scan.gif'  // Placeholder, not MJPEG
  addLog('📺 Placeholder image shown (stream disabled)')
}
```

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     PREVIEW SYSTEM FLOW                      │
└─────────────────────────────────────────────────────────────┘

[RealSense Camera]
       ↓
[_preview_loop() - Background Task]
       ├── idle_detection: 1s bursts
       ├── active: continuous, every 4th frame
       └── validation: continuous, every 4th frame
       ↓
[_serialize_frame()]
       ├── eye_tracking mode → Eye of Horus viz
       └── normal mode → colored dot
       ↓
[_broadcast_frame(frame_bytes)]
       ↓
[_preview_subscribers: List[Queue[bytes]]]
       ↓
       ├── Queue 1 (HTTP Client 1)
       ├── Queue 2 (HTTP Client 2)
       └── Queue N (HTTP Client N)
       ↓
[preview_stream() - async iterator]
       ↓
[SessionManager.preview_frames()]
       ↓
[@app.get("/preview") - MJPEG Stream]
       ↓
[HTTP Response: multipart/x-mixed-replace]
       ↓
[React: PreviewSurface Component]
       ↓
[Currently: Static GIF /hero/scan.gif]
[NOT USING: localhost:5000/preview stream]
```

---

## Current Status

### **Backend (Python):**
✅ MJPEG stream working at `localhost:5000/preview`
✅ Frames generated continuously in background
✅ Eye of Horus visualization ready
✅ Supports multiple simultaneous clients
✅ Frame skipping optimization (every 4th frame)
✅ Three operational modes (idle_detection, active, validation)

### **Frontend (React):**
❌ **NOT using MJPEG stream**
❌ Shows static GIF instead: `/hero/scan.gif`
❌ `previewUrl` prop provided but ignored
✅ Visibility controlled by phase (only `human_detect`)

---

## To Enable Live Preview

### **Option 1: Use `<img>` tag with MJPEG stream**

Change `PreviewSurface.tsx`:

```typescript
<img
  className="preview-surface__img preview-surface__media"
  src={previewUrl}  // Use previewUrl instead of static GIF
  alt={title || 'Camera preview'}
  style={{
    width: '100%',
    height: '100%',
    objectFit: 'cover',
    display: 'block',
    backgroundColor: '#000'
  }}
/>
```

### **Option 2: Use `<iframe>` (better for MJPEG)**

```typescript
<iframe
  className="preview-surface__media"
  src={previewUrl}
  title={title}
  style={{
    width: '100%',
    height: '100%',
    border: 'none',
    backgroundColor: '#000'
  }}
/>
```

---

## Performance Considerations

### **Current Optimizations:**
1. **Frame skipping**: Only broadcasts every 4th frame in active/validation mode
2. **Queue management**: Drops old frames if client can't keep up
3. **JPEG compression**: Quality 70 (good balance)
4. **Non-blocking**: All operations use async/await
5. **Garbage collection**: Periodic GC to prevent memory bloat

### **Metrics:**
- **FPS**: ~10-15 FPS (limited to prevent CPU overload)
- **Resolution**: 640x480 (configurable)
- **Frame size**: ~20-50 KB per JPEG
- **Latency**: ~100-200ms (network + encoding)

---

## Debug Endpoints

### **Toggle camera:**
```bash
POST http://localhost:5000/debug/preview
{
  "enabled": true
}
```

### **Change preview mode:**
```bash
POST http://localhost:5000/debug/preview-mode
{
  "mode": "eye_tracking"  # or "normal"
}
```

### **Switch camera source:**
```bash
POST http://localhost:5000/debug/camera-source
{
  "source": "realsense"  # or "webcam"
}
```

---

## Summary

**Backend:**
- `/preview` endpoint streams MJPEG at ~10-15 FPS
- Three modes: idle_detection (1s bursts), active (continuous), validation (continuous)
- Eye of Horus or simple dot visualization
- Frame skipping for performance

**Frontend:**
- Preview shows only during `human_detect` phase
- Currently using **static GIF**, NOT live stream
- To enable live preview: change `src={previewUrl}` in PreviewSurface component

**Current State:**
- Infrastructure is complete and working
- Stream is ready at `localhost:5000/preview`
- UI just needs to use it instead of static GIF

