# RealSense Camera Flow - Visual Diagram

## 🔄 Complete System Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    SESSION MANAGER                               │
│                                                                   │
│  1. Mobile app connects → Pre-warm camera                        │
│  2. Start validation → Activate camera (if not pre-warmed)       │
│  3. Collect frames for 10s                                       │
│  4. Select best frame                                            │
│  5. Deactivate camera                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              SIMPLE REALSENSE SERVICE (Async)                    │
│                                                                   │
│  ┌───────────────────────────────────────────────────┐          │
│  │          HARDWARE LIFECYCLE MANAGER               │          │
│  │  • Reference counting (multiple sources)          │          │
│  │  • Activate: sum(requests) > 0                    │          │
│  │  • Deactivate: sum(requests) == 0                 │          │
│  └───────────────────────────────────────────────────┘          │
│                              │                                    │
│  ┌───────────────────────────────────────────────────┐          │
│  │            PREVIEW LOOP (Background Task)         │          │
│  │                                                    │          │
│  │  while True:                                       │          │
│  │    1. Process frame (blocking → executor)         │          │
│  │    2. Broadcast result to ALL subscribers         │          │
│  │    3. Encode JPEG every 4th frame                 │          │
│  │    4. Broadcast preview to UI subscribers         │          │
│  │    5. GC every 30s                                │          │
│  │    6. Sleep to limit FPS                          │          │
│  └───────────────────────────────────────────────────┘          │
│                              │                                    │
│                    ┌─────────┴─────────┐                         │
│                    ↓                   ↓                          │
│         ┌──────────────────┐  ┌──────────────────┐              │
│         │ Result Broadcast │  │ Preview Broadcast│              │
│         │  (Every frame)   │  │  (Every 4th)     │              │
│         └──────────────────┘  └──────────────────┘              │
└─────────────────────────────────────────────────────────────────┘
                    │                           │
                    ↓                           ↓
    ┌───────────────────────────┐   ┌──────────────────────┐
    │   RESULT SUBSCRIBERS      │   │  PREVIEW SUBSCRIBERS │
    │  (SessionManager queue)   │   │   (WebSocket queue)  │
    └───────────────────────────┘   └──────────────────────┘
```

---

## 🎥 Frame Processing Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│            SIMPLE MEDIAPIPE LIVENESS (Blocking)                  │
│                                                                   │
│  ┌────────────────────────────────────────────────────┐         │
│  │  1. CAPTURE FRAMES                                  │         │
│  │     frames = pipe.wait_for_frames(timeout=1s)      │         │
│  │     frames = align_to_color.process(frames)        │         │
│  │                                                     │         │
│  │     depth_frame  ────┐                             │         │
│  │     color_frame  ────┤                             │         │
│  └─────────────────────┬┴─────────────────────────────┘         │
│                        │                                         │
│  ┌─────────────────────▼──────────────────────────────┐         │
│  │  2. FACE DETECTION (MediaPipe)                      │         │
│  │     rgb = cv2.cvtColor(color, BGR2RGB)             │         │
│  │     mesh_result = face_mesh.process(rgb)           │         │
│  │                                                     │         │
│  │     if no face:                                     │         │
│  │       return Result(face_detected=False)           │         │
│  │                                                     │         │
│  │     Extract landmarks → Compute bbox               │         │
│  └─────────────────────┬────────────────────────────────┘       │
│                        │                                         │
│  ┌─────────────────────▼──────────────────────────────┐         │
│  │  3. LIVENESS CHECK (3 Simple Tests)                │         │
│  │                                                     │         │
│  │  ┌─────────────────────────────────────────────┐  │         │
│  │  │ CHECK 1: Sufficient Data                    │  │         │
│  │  │   valid_depths = depth_patch[depth > 0]     │  │         │
│  │  │   if len(valid_depths) < 100:               │  │         │
│  │  │     ❌ FAIL: "insufficient_depth_data"       │  │         │
│  │  └─────────────────────────────────────────────┘  │         │
│  │                                                     │         │
│  │  ┌─────────────────────────────────────────────┐  │         │
│  │  │ CHECK 2: Distance Range                     │  │         │
│  │  │   mean_dist = np.mean(valid_depths)         │  │         │
│  │  │   if mean_dist < 0.25m:                     │  │         │
│  │  │     ❌ FAIL: "too_close"                     │  │         │
│  │  │   if mean_dist > 1.2m:                      │  │         │
│  │  │     ❌ FAIL: "too_far"                       │  │         │
│  │  └─────────────────────────────────────────────┘  │         │
│  │                                                     │         │
│  │  ┌─────────────────────────────────────────────┐  │         │
│  │  │ CHECK 3: Depth Variance (Anti-Spoof)        │  │         │
│  │  │   depth_std = np.std(valid_depths)          │  │         │
│  │  │   if depth_std < 0.015m:                    │  │         │
│  │  │     ❌ FAIL: "flat_surface" (photo/screen)  │  │         │
│  │  │                                              │  │         │
│  │  │   ✅ PASS: "live_face"                       │  │         │
│  │  └─────────────────────────────────────────────┘  │         │
│  └─────────────────────┬────────────────────────────────┘       │
│                        │                                         │
│  ┌─────────────────────▼──────────────────────────────┐         │
│  │  4. RETURN RESULT                                   │         │
│  │     SimpleLivenessResult(                          │         │
│  │       face_detected=True,                          │         │
│  │       is_live=True/False,                          │         │
│  │       reason="live_face" / "flat_surface" / ...,   │         │
│  │       mean_distance_m=0.65,                        │         │
│  │       depth_variance_m=0.023,                      │         │
│  │       color_image=<frame>,                         │         │
│  │       bbox=(x0, y0, x1, y1)                        │         │
│  │     )                                               │         │
│  └─────────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎨 Preview Rendering

```
SimpleLivenessResult
        │
        ↓
┌───────────────────────────────────────────┐
│  Mode Selection                            │
│  • "eye_tracking" (default)                │
│  • "normal" (face dot)                     │
└───────────────────┬───────────────────────┘
                    │
        ┌───────────┴────────────┐
        ↓                        ↓
┌──────────────────┐    ┌─────────────────────┐
│  NORMAL MODE     │    │  EYE TRACKING MODE  │
│  (Face Dot)      │    │  (Eye of Horus)     │
├──────────────────┤    ├─────────────────────┤
│                  │    │                     │
│ Black canvas     │    │ Black canvas        │
│     │            │    │     │               │
│     ↓            │    │     ↓               │
│ if no face:      │    │ if no face:         │
│   • Red dot      │    │   • Ghost eyes      │
│   • "No Face"    │    │   • "looking for    │
│                  │    │     face..."        │
│ if face:         │    │   • "adjust your    │
│   • Dot at bbox  │    │     position"       │
│     center       │    │                     │
│   • Green=live   │    │ if face:            │
│   • Orange=not   │    │   • Full eyes track │
│   • Show dist    │    │     face position   │
│                  │    │   • Progress bar    │
│                  │    │   • Breathing anim  │
└──────────────────┘    └─────────────────────┘
        │                        │
        └───────────┬────────────┘
                    ↓
            ┌───────────────┐
            │ cv2.imencode  │
            │  (.jpg, 70%)  │
            └───────┬───────┘
                    ↓
            ┌───────────────┐
            │  JPEG bytes   │
            └───────────────┘
                    ↓
            Broadcast to UI
```

---

## 🔄 Validation Flow (10 seconds)

```
SessionManager._validate_human_presence()
        │
        ↓
┌───────────────────────────────────────────────────────────┐
│  1. ACTIVATE CAMERA                                        │
│     • Check if pre-warmed                                  │
│     • If cold: activate + 2s warmup                        │
│     • If warm: activate + 0.5s stabilize                   │
└───────────────────────┬───────────────────────────────────┘
                        ↓
┌───────────────────────────────────────────────────────────┐
│  2. COLLECT FRAMES (10 seconds)                            │
│                                                             │
│     passing_frames = []                                    │
│     best_score = -1.0                                      │
│                                                             │
│     for each 0.1s window:                                  │
│       results = await gather_results(0.1)                  │
│                                                             │
│       for result in results:                               │
│         if result.depth_ok:  # Passed liveness             │
│           passing_frames.append(result)                    │
│                                                             │
│           # Update Eye of Horus progress bar               │
│           progress = len(passing_frames) / 10              │
│           set_validation_progress(progress)                │
│                                                             │
│           # Calculate quality score                        │
│           focus = laplacian_variance(color_image)          │
│           score = (stability * 0.7) + (focus * 0.3)        │
│                                                             │
│           if score > best_score:                           │
│             best_score = score                             │
│             best_frame = result                            │
└───────────────────────┬───────────────────────────────────┘
                        ↓
┌───────────────────────────────────────────────────────────┐
│  3. VALIDATE RESULTS                                        │
│                                                             │
│     if face_detected_count == 0:                           │
│       ❌ "you dont seem to have facial features"           │
│                                                             │
│     if face_detected_count < 30% of frames:                │
│       ❌ "lost tracking, please stay in frame"             │
│                                                             │
│     if passing_frames < 10:                                │
│       ❌ "validation failed, please try again"             │
│                                                             │
│     ✅ PASS: Use best_frame                                │
└───────────────────────┬───────────────────────────────────┘
                        ↓
┌───────────────────────────────────────────────────────────┐
│  4. ENCODE & SAVE                                           │
│     • Encode best frame as JPEG (95% quality)              │
│     • Save to captures/{timestamp}_{platform_id}_BEST.jpg  │
│     • Save metadata JSON                                   │
└───────────────────────┬───────────────────────────────────┘
                        ↓
┌───────────────────────────────────────────────────────────┐
│  5. DEACTIVATE CAMERA                                       │
│     await set_hardware_active(False, source="validation")  │
└───────────────────────────────────────────────────────────┘
```

---

## 🚀 Performance Optimization Strategy

```
┌─────────────────────────────────────────────────────┐
│             OPTIMIZATION TECHNIQUES                  │
├─────────────────────────────────────────────────────┤
│                                                      │
│  1. FRAME SKIPPING (75% CPU reduction)               │
│     • Process: Every frame → validation              │
│     • Encode: Every 4th frame → preview              │
│                                                      │
│  2. SINGLE MEDIAPIPE MODEL (50% CPU reduction)       │
│     • Old: face_detector + face_mesh                 │
│     • New: face_mesh only (does both)                │
│                                                      │
│  3. NO LANDMARK REFINEMENT (40% CPU reduction)       │
│     • refine_landmarks=False                         │
│     • Skip iris/lip detail (not needed)              │
│                                                      │
│  4. EXECUTOR PATTERN (non-blocking)                  │
│     • RealSense SDK is blocking                      │
│     • Run in executor → event loop continues         │
│                                                      │
│  5. QUEUE SIZE TUNING                                │
│     • Preview: maxsize=2 (drop old frames)           │
│     • Results: maxsize=50 (keep all)                 │
│                                                      │
│  6. PERIODIC GC (prevent memory bloat)               │
│     • gc.collect() every 30 seconds                  │
│     • Force GC after deactivation                    │
│                                                      │
│  7. FPS LIMITING                                     │
│     • Target: 30 FPS (33ms per frame)                │
│     • Sleep if processing faster                     │
│                                                      │
│  8. JPEG QUALITY (bandwidth vs quality)              │
│     • 70% quality for preview (good enough)          │
│     • 95% quality for validation (high quality)      │
│                                                      │
└─────────────────────────────────────────────────────┘
```

---

## 🎯 Reference Counting Example

```
Time    Action                              Requests          Active?
────────────────────────────────────────────────────────────────────
0.0s    Initial state                       {}                 ❌
        
1.0s    Debug preview ON                    {preview: 1}       ✅
        → Camera activates
        
2.0s    Session starts (pre-warm)           {preview: 1,       ✅
        → Camera already active             validation: 1}
        
3.0s    Validation starts                   {preview: 1,       ✅
        → Camera already active             validation: 1}
        
13.0s   Validation ends                     {preview: 1}       ✅
        → Camera stays on (preview active)
        
15.0s   Preview OFF                         {}                 ❌
        → Camera deactivates
```

**Key Point:** Multiple sources can request camera simultaneously, and it stays active until **all** release it.

---

## 📊 Data Structures

### SimpleLivenessResult
```python
@dataclass
class SimpleLivenessResult:
    timestamp: float              # Unix timestamp
    color_image: np.ndarray       # BGR image (H, W, 3)
    depth_frame: rs.depth_frame   # Raw depth frame
    bbox: Tuple[int, int, int, int] | None  # (x0, y0, x1, y1)
    
    # Detection
    face_detected: bool           # True if face found
    is_live: bool                 # True if passed liveness
    reason: str                   # "live_face", "flat_surface", etc.
    
    # Metrics
    mean_distance_m: float | None # Average face distance
    depth_variance_m: float | None # Depth standard deviation
    valid_points: int             # Number of valid depth pixels
```

### SimpleLivenessConfig
```python
@dataclass
class SimpleLivenessConfig:
    # Distance thresholds
    distance_min_m: float = 0.25  # 25cm min
    distance_max_m: float = 1.2   # 120cm max
    
    # Depth variance (anti-spoof)
    depth_variance_min_m: float = 0.015  # 15mm variance
    min_valid_points: int = 100
    
    # MediaPipe
    face_confidence: float = 0.5
    
    # Hardware
    resolution_width: int = 640
    resolution_height: int = 480
    fps: int = 30
```

---

This visual guide complements the detailed `REALSENSE_CAMERA_EXPLAINED.md` document! 🎯

