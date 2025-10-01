# Camera Lifecycle Fix - Preventing Premature Deactivation

## Problem

The camera was stopping unexpectedly during active sessions, even when biometric capture was in progress. This was caused by:

1. **Double Deactivation**: Camera was being deactivated twice at session end
2. **Order-of-Operations Issue**: Phase change to IDLE triggered deactivation AFTER finally block
3. **Missing Activation Tracking**: No flag to track if camera was actually activated

## Root Cause Analysis

### Previous Flow (Buggy)
```python
async def _run_session(self) -> None:
    try:
        # ... session logic ...
        await self._set_phase(SessionPhase.HUMAN_DETECT)
        await self._realsense.set_hardware_active(True, source="session")  # ✅ Activate (count: 1)
        # ... capture frames ...
    finally:
        await self._realsense.set_hardware_active(False, source="session")  # ❌ Deactivate (count: 0)
        await self._set_phase(SessionPhase.IDLE)  # ❌ Triggers ANOTHER deactivate!

async def _set_phase(self, phase: SessionPhase, ...):
    self._phase = phase
    if phase == SessionPhase.IDLE:
        await self._realsense.set_hardware_active(False, source="session")  # ❌ Double deactivation!
```

**Issues:**
- Line 1: Activate camera → count = 1 ✅
- Line 2: Deactivate in finally → count = 0 ✅
- Line 3: Deactivate in _set_phase → count = -1 or ignored ❌
- **Result**: Potential counter corruption or unexpected behavior

### Additional Issues
1. If session failed BEFORE camera activation, finally block still tried to deactivate
2. No clear logging of camera lifecycle events
3. No tracking of whether camera was actually activated

## Solution

### 1. Track Camera Activation State
```python
async def _run_session(self) -> None:
    camera_activated = False  # ✅ Track activation state
    try:
        # ... QR code, pairing phases (camera OFF) ...
        
        # Activate camera for human detection
        await self._set_phase(SessionPhase.HUMAN_DETECT)
        await self._realsense.set_hardware_active(True, source="session")
        camera_activated = True  # ✅ Mark as activated
        logger.info("Camera activated for biometric capture")
        
        # ... capture, upload, wait for ack ...
    finally:
        # Deactivate only if it was activated
        if camera_activated:  # ✅ Conditional deactivation
            await self._realsense.set_hardware_active(False, source="session")
            logger.info("Camera deactivated after session")
        await self._set_phase(SessionPhase.IDLE)  # ✅ No longer triggers deactivation
```

### 2. Remove Deactivation from Phase Change
```python
async def _set_phase(self, phase: SessionPhase, ...):
    self._phase = phase
    await self._broadcast(ControllerEvent(...))
    self._phase_started_at = time.time()
    # ✅ No camera control here - session manages it
```

### 3. Improve Reference Counting Logging
```python
async def set_hardware_active(self, active: bool, *, source: str = "session"):
    if active:
        self._hardware_requests[source] += 1
        logger.info(
            "RealSense hardware request acquired: %s (count=%s, total=%s)",
            source,
            self._hardware_requests[source],  # ✅ Show individual counter
            sum(self._hardware_requests.values())  # ✅ Show total
        )
    else:
        current_count = self._hardware_requests.get(source, 0)
        if current_count > 0:
            self._hardware_requests[source] -= 1
            logger.info(
                "RealSense hardware request released: %s (was=%s, remaining=%s)",
                source,
                current_count,  # ✅ Show what it was
                sum(self._hardware_requests.values())  # ✅ Show what's left
            )
```

## Fixed Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Startup                                                      │
│ - camera_activated = False (implicit)                       │
│ - No camera activation/deactivation calls                   │
│ - Counter: session=0                                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Session Start (ToF trigger)                                  │
│ - camera_activated = False                                  │
│ - Phase: pairing_request → qr_display → waiting_activation │
│ - Counter: session=0 (camera still OFF)                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Camera Activation (human_detect)                            │
│ - set_hardware_active(True, source="session")              │
│ - camera_activated = True                                   │
│ - Counter: session=1 ✅                                     │
│ - Log: "Camera activated for biometric capture"            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Active Capture (stabilizing, uploading, waiting_ack)       │
│ - Camera stays active                                        │
│ - counter: session=1 ✅                                     │
│ - Preview streams frames                                     │
│ - Liveness detection running                                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Session End (finally block)                                 │
│ - if camera_activated:                                      │
│   - set_hardware_active(False, source="session")           │
│   - Counter: session=0 ✅                                   │
│   - Log: "Camera deactivated after session"                │
│ - _set_phase(SessionPhase.IDLE)                            │
│   - No camera control (✅ fixed!)                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Back to IDLE                                                 │
│ - camera_activated = N/A (session ended)                   │
│ - Counter: session=0                                         │
│ - Camera OFF ✅                                             │
└─────────────────────────────────────────────────────────────┘
```

## Error Scenarios Handled

### Scenario 1: Session Cancelled Before Camera Activation
```python
try:
    # Token request fails or mobile doesn't connect
    raise Exception("Connection failed")
    # Camera never activated
finally:
    if camera_activated:  # ✅ False, skips deactivation
        await self._realsense.set_hardware_active(False, source="session")
    # Result: No unnecessary deactivation call
```

### Scenario 2: Session Cancelled During Capture
```python
try:
    await self._realsense.set_hardware_active(True, source="session")
    camera_activated = True  # ✅ Marked as activated
    # User cancels (Ctrl+C or ToF reset)
    raise asyncio.CancelledError()
finally:
    if camera_activated:  # ✅ True, properly deactivates
        await self._realsense.set_hardware_active(False, source="session")
    # Result: Camera properly deactivated
```

### Scenario 3: Multiple Rapid Sessions
```python
# Session 1
activate(True) → count = 1
# ... capture ...
activate(False) → count = 0
phase → IDLE (no deactivation) ✅

# Session 2 (immediately after)
activate(True) → count = 1 ✅
# ... capture ...
activate(False) → count = 0 ✅
phase → IDLE (no deactivation) ✅

# Result: Counter stays consistent
```

## Expected Logs

### Successful Session
```
[INFO] Session manager started in IDLE state (camera inactive)
[INFO] ToF trigger=True distance=150 phase=idle
[INFO] Phase → pairing_request
[INFO] Phase → qr_display
[INFO] Phase → waiting_activation
[INFO] Phase → human_detect
[INFO] RealSense hardware request acquired: session (count=1, total=1)
[INFO] Activating RealSense pipeline (requests={'session': 1})
[INFO] Connected to Intel RealSense D435i (S/N 123456789)
[INFO] Camera activated for biometric capture
[INFO] Phase → stabilizing
[INFO] Phase → uploading
[INFO] Phase → waiting_ack
[INFO] Phase → complete
[INFO] RealSense hardware request released: session (was=1, remaining=0)
[INFO] Deactivating RealSense pipeline (no active requests)
[INFO] Camera deactivated after session
[INFO] Phase → idle
```

### Session Cancelled Before Camera Activation
```
[INFO] Session manager started in IDLE state (camera inactive)
[INFO] ToF trigger=True distance=150 phase=idle
[INFO] Phase → pairing_request
[ERROR] Token issue failed
[INFO] Phase → error
[INFO] Phase → idle
# ✅ No camera activation/deactivation logs - correct!
```

### Session Error During Capture
```
[INFO] Phase → human_detect
[INFO] RealSense hardware request acquired: session (count=1, total=1)
[INFO] Camera activated for biometric capture
[ERROR] Frame timeout: Frame didn't arrive within 1000ms
[INFO] Session failed: RuntimeError
[INFO] Phase → error
[INFO] RealSense hardware request released: session (was=1, remaining=0)
[INFO] Camera deactivated after session
[INFO] Phase → idle
```

## Validation

### Counter Integrity Check
```python
# Expected counter states:
IDLE: session=0
PAIRING/QR/WAITING: session=0
HUMAN_DETECT onwards: session=1
FINALLY block: session=1 → 0
IDLE again: session=0

# Log patterns to monitor:
- "acquired: session (count=1" → Camera ON
- "released: session (was=1" → Camera OFF
- Never see "count=2" (double activation)
- Never see "was=0" (deactivating when not active)
```

## Benefits

1. ✅ **Prevents Premature Deactivation**: Camera stays on during entire capture
2. ✅ **No Double Deactivation**: Only deactivates once per activation
3. ✅ **Robust Error Handling**: Works correctly even if session fails early
4. ✅ **Clear Lifecycle**: Easy to trace camera state through logs
5. ✅ **Counter Integrity**: Reference counting stays consistent
6. ✅ **IDLE Guarantee**: Camera guaranteed OFF in IDLE state

## Testing

### Manual Test
1. Start system → Check camera is OFF
2. Trigger session → Camera stays OFF during QR
3. Connect mobile → Camera turns ON at human_detect
4. Complete session → Camera turns OFF at IDLE
5. Check logs for counter consistency

### Stress Test
1. Run 10 consecutive sessions
2. Cancel session at different phases
3. Monitor counter: should always return to 0
4. No "leaked" activations

### Error Test
1. Disconnect camera mid-session
2. Check error recovery
3. Verify camera state returns to OFF
4. No zombie processes or locked resources

## Related Files

- `controller/app/session_manager.py` - Camera lifecycle management
- `controller/app/sensors/realsense.py` - Reference counting implementation
- `CAMERA_CONTROL_FIX.md` - Original architecture documentation
