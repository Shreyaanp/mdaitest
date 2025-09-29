# Camera Control Architecture - Implementation Guide

## Problem Statement

The original implementation had a **critical flow issue**: the camera could be activated in IDLE state due to conflicting control mechanisms between the session manager and preview system.

### Issues Identified:

1. **Dual Control Systems**: Both session manager and preview subscribers could activate the camera
2. **IDLE State Violations**: Camera could remain on or be activated during IDLE state
3. **Race Conditions**: Multiple activation sources created unpredictable behavior
4. **Privacy Concerns**: Camera potentially active when no session is running

---

## Solution: Single Source of Control

**Core Principle**: The `SessionManager` is the SOLE controller of camera hardware activation.

### Architecture Changes

```
BEFORE (Problematic):
┌─────────────────┐         ┌──────────────────┐
│ Session Manager │────────►│ RealSense Camera │
└─────────────────┘         └──────────────────┘
                                      ▲
┌─────────────────┐                  │
│ Preview System  │──────────────────┘
└─────────────────┘
    (Both can activate camera - CONFLICT!)

AFTER (Fixed):
┌─────────────────┐         ┌──────────────────┐
│ Session Manager │────────►│ RealSense Camera │
└─────────────────┘         └──────────────────┘
                                      │
┌─────────────────┐                  │
│ Preview System  │◄─────────────────┘
└─────────────────┘
    (Only receives frames, cannot activate)
```

---

## Implementation Details

### 1. Session Manager (`controller/app/session_manager.py`)

#### Camera Activation at Startup
```python
async def start(self) -> None:
    logger.info("Starting session manager")
    if self._tof_process:
        await self._tof_process.start()
    await self._realsense.start()
    await self._tof.start()
    # Ensure camera is off in initial IDLE state
    await self._realsense.set_hardware_active(False, source="session")
    self._background_tasks.append(asyncio.create_task(self._heartbeat_loop(), name="controller-heartbeat"))
```

#### Phase-Based Camera Control
```python
async def _set_phase(self, phase: SessionPhase, *, data: Optional[Dict[str, Any]] = None, error: Optional[str] = None) -> None:
    self._phase = phase
    await self._broadcast(ControllerEvent(type="state", data=data or {}, phase=phase, error=error))
    self._phase_started_at = time.time()
    
    # Ensure camera is OFF when entering IDLE state
    if phase == SessionPhase.IDLE:
        await self._realsense.set_hardware_active(False, source="session")
        logger.info("Camera deactivated for IDLE state")
```

#### Session Flow
```python
async def _run_session(self) -> None:
    try:
        # ... QR code and pairing phases (camera OFF) ...
        
        await self._set_phase(SessionPhase.HUMAN_DETECT)
        await self._realsense.set_hardware_active(True, source="session")  # ✅ Camera ON
        await self._ensure_phase_duration(3.0)
        
        await self._collect_best_frame()  # Camera stays ON
        await self._upload_frame()         # Camera stays ON
        await self._wait_for_ack()         # Camera stays ON
        
        await self._set_phase(SessionPhase.COMPLETE)
        await self._ensure_phase_duration(3.0)
        
    finally:
        await self._realsense.set_hardware_active(False, source="session")  # ✅ Camera OFF
        await self._ws_client.disconnect()
        await self._set_phase(SessionPhase.IDLE)
```

---

### 2. RealSense Service (`controller/app/sensors/realsense.py`)

#### Class Documentation
```python
class RealSenseService:
    """Coordinates preview streaming and liveness evaluation.
    
    Important: Camera hardware activation is controlled ONLY by the session manager
    via set_hardware_active(). Preview subscribers do NOT activate the camera - they
    only receive frames when the camera is already active.
    """
```

#### Removed Features
- ❌ `_allow_preview_activation` flag
- ❌ `set_preview_can_activate_hardware()` method
- ❌ `_ensure_preview_active()` method
- ❌ Preview-based hardware activation logic

#### Simplified Preview Stream
```python
async def preview_stream(self) -> AsyncIterator[bytes]:
    """Stream preview frames. Does NOT activate camera - session controls that."""
    q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=2)
    self._preview_subscribers.append(q)
    try:
        while True:
            frame = await q.get()
            yield frame
    finally:
        self._preview_subscribers.remove(q)
```

**Key Point**: Preview stream is now **passive** - it only distributes frames when the camera is active.

---

## Complete Session Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Phase: IDLE                                                  │
│ Camera: OFF ❌                                              │
│ UI: Idle screen (no preview)                                │
│ Action: Waiting for ToF sensor trigger                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
                   ToF Sensor Detects Person
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase: pairing_request → qr_display → waiting_activation   │
│ Camera: OFF ❌                                              │
│ UI: QR code displayed                                        │
│ Action: Waiting for mobile app connection                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
                   Mobile App Connects
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase: human_detect                                          │
│ Camera: ON ✅ (session activates)                           │
│ UI: Preview visible, instruction "Center your face"         │
│ Action: Face detection & liveness checks start              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase: stabilizing                                           │
│ Camera: ON ✅ (stays active)                                │
│ UI: Preview visible, instruction "Hold steady"              │
│ Action: Collecting best frame (3-5 seconds)                 │
│        - Depth profile analysis                              │
│        - IR anti-spoofing checks                             │
│        - Movement & vitality detection                       │
│        - Focus scoring                                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase: uploading → waiting_ack                              │
│ Camera: ON ✅ (stays active)                                │
│ UI: Preview visible, processing messages                    │
│ Action: Uploading best frame to backend                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase: complete                                              │
│ Camera: ON → OFF ✅ (session deactivates)                  │
│ UI: Success message                                          │
│ Action: Cleanup and prepare for next session                │
└─────────────────────────────────────────────────────────────┘
                            ↓
                      Return to IDLE
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase: IDLE                                                  │
│ Camera: OFF ❌ (guaranteed)                                 │
│ UI: Idle screen                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## State Guarantees

| Phase | Camera State | Preview Visible (UI) | Controller |
|-------|--------------|---------------------|------------|
| `idle` | **OFF** ❌ | No | Session Manager |
| `pairing_request` | **OFF** ❌ | No | Session Manager |
| `qr_display` | **OFF** ❌ | No | Session Manager |
| `waiting_activation` | **OFF** ❌ | No | Session Manager |
| `human_detect` | **ON** ✅ | Yes | Session Manager |
| `stabilizing` | **ON** ✅ | Yes | Session Manager |
| `uploading` | **ON** ✅ | Yes | Session Manager |
| `waiting_ack` | **ON** ✅ | Yes | Session Manager |
| `complete` | **ON → OFF** ✅ | No | Session Manager |

---

## Frontend Integration (`mdai-ui/src/App.tsx`)

### Preview Visibility Logic
```typescript
// Line 15-20
const previewVisibleStates = new Set([
  'human_detect',
  'stabilizing',
  'uploading',
  'waiting_ack'
])

// Line 247
const showPreview = useMemo(() => 
  previewVisibleStates.has(state.value as string), 
  [state.value]
)
```

### Preview Component
```typescript
// Line 321-324
<PreviewSurface
  visible={showPreview}
  previewUrl={previewUrl}  // http://127.0.0.1:5000/preview
/>
```

**Important**: When `visible` becomes `true`, the `<img>` tag loads the MJPEG stream from `/preview`. However, this **does NOT** activate the camera - it only displays frames if the session has already activated the camera.

---

## Testing Checklist

### Manual Testing
- [ ] **IDLE State**: Camera is off, no LED indicator
- [ ] **ToF Trigger**: Session starts, camera remains off during QR display
- [ ] **Mobile Connection**: Camera activates at `human_detect` phase
- [ ] **Preview Display**: Frames visible in UI during active phases
- [ ] **Session Complete**: Camera deactivates when returning to IDLE
- [ ] **Error Recovery**: Camera deactivates on session errors
- [ ] **Multiple Cycles**: Camera behavior consistent across multiple sessions

### Automated Tests
```python
# Test: Camera state during IDLE
async def test_camera_off_during_idle():
    session_manager = SessionManager()
    await session_manager.start()
    assert session_manager._realsense._hardware_active == False
    assert session_manager.phase == SessionPhase.IDLE

# Test: Camera activation during human_detect
async def test_camera_on_during_detection():
    session_manager = SessionManager()
    await session_manager._set_phase(SessionPhase.HUMAN_DETECT)
    await session_manager._realsense.set_hardware_active(True, source="session")
    assert session_manager._realsense._hardware_active == True

# Test: Preview cannot activate camera
async def test_preview_cannot_activate():
    realsense = RealSenseService()
    await realsense.start()
    
    # Subscribe to preview
    async for _ in realsense.preview_stream():
        break
    
    # Camera should still be off
    assert realsense._hardware_active == False
```

---

## Key Benefits

### 1. **Privacy Guaranteed**
- Camera is **never on** during IDLE state
- Clear separation between active and inactive states
- Physical LED indicator matches actual camera state

### 2. **Simplified Control Flow**
- Single source of truth for camera activation
- No race conditions or conflicts
- Predictable behavior across all phases

### 3. **Better Resource Management**
- Camera only active when needed
- Reduced power consumption during idle
- Hardware lifecycle clearly managed

### 4. **Improved Debugging**
- Clear logs for camera activation/deactivation
- Easy to trace camera state through session phases
- Reference counting still works for session-based activation

---

## Logs to Monitor

```
# Expected log sequence:

[INFO] Starting session manager
[INFO] Camera deactivated for IDLE state

# ... ToF trigger ...

[INFO] Phase → pairing_request
[INFO] Phase → qr_display
[INFO] Phase → waiting_activation

# ... Mobile connects ...

[INFO] Phase → human_detect
[INFO] Activating RealSense pipeline (requests={'session': 1})

[INFO] Phase → stabilizing
# Camera stays on

[INFO] Phase → uploading
# Camera stays on

[INFO] Phase → complete
[INFO] Deactivating RealSense pipeline (no active requests)

[INFO] Phase → idle
[INFO] Camera deactivated for IDLE state
```

---

## Migration Notes

### Breaking Changes
None - this is an internal refactor.

### Rollback Plan
If issues arise:
1. Revert `controller/app/sensors/realsense.py` to previous version
2. Revert `controller/app/session_manager.py` to previous version
3. Restart controller service

### Performance Impact
- **Positive**: Reduced resource usage during IDLE
- **Neutral**: No impact on active session performance
- **Note**: Camera startup time (2-3 seconds) occurs at `human_detect` phase, not on preview subscription

---

## Future Enhancements

1. **Add Camera State API**
   ```python
   @app.get("/camera/status")
   async def camera_status():
       return {
           "active": manager._realsense._hardware_active,
           "phase": manager.phase.value,
           "subscribers": len(manager._realsense._preview_subscribers)
       }
   ```

2. **Add Privacy Indicator in UI**
   ```typescript
   // Show camera state in ControlPanel
   <div className="camera-status">
     Camera: {cameraActive ? '🔴 ON' : '⚫ OFF'}
   </div>
   ```

3. **Add Telemetry**
   ```python
   # Track camera activation events
   logger.info("camera_event", extra={
       "event": "activated",
       "phase": self._phase,
       "duration_since_idle": time.time() - self._phase_started_at
   })
   ```

---

## Summary

✅ **Camera is OFF during IDLE** - Guaranteed by session manager  
✅ **Single source of control** - Only session manager activates camera  
✅ **Preview is passive** - Only displays frames, never activates  
✅ **Clear phase transitions** - Logged and trackable  
✅ **Privacy focused** - Camera only on when actively needed  

This implementation ensures the camera behaves predictably and respects user privacy.
