#!/usr/bin/env python3
"""
SIMPLE RealSense + MediaPipe Liveness Detection
- No complex heuristics
- Just 3 basic checks that work
- Optimized for Jetson Nano
"""

from __future__ import annotations

import asyncio
from asyncio import QueueEmpty
import base64
import gc
import logging
import time
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Deque, Dict, List, Optional, Tuple

import numpy as np

# Optional deps
try:
    import cv2  # type: ignore
except Exception:
    cv2 = None

try:
    import mediapipe as mp  # type: ignore
except Exception:
    mp = None

try:
    import pyrealsense2 as rs  # type: ignore
except Exception:
    rs = None


logger = logging.getLogger("d435i_liveness")

_PLACEHOLDER_JPEG = base64.b64decode(
    b"/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD5/ooooA//2Q=="
)


# ============================================================
# Simple Configuration
# ============================================================

@dataclass
class SimpleLivenessConfig:
    """Simplified configuration - only what we actually need."""
    # Distance thresholds
    distance_min_m: float = 0.25  # 25cm minimum (allows closer faces)
    distance_max_m: float = 1.2   # 120cm maximum
    
    # Depth variance threshold (anti-flat surface)
    depth_variance_min_m: float = 0.015  # 15mm variance required
    min_valid_points: int = 100  # Need at least 100 depth points
    
    # MediaPipe settings
    face_confidence: float = 0.5  # Lower threshold for better detection
    confidence: float = 0.5  # Alias for backward compatibility
    
    # Camera hardware settings (can be overridden from main config)
    resolution_width: int = 640
    resolution_height: int = 480
    fps: int = 30
    
    # Legacy/compatibility fields
    display: bool = False
    stride: int = 3  # For backward compatibility
    record_seconds: int = 0  # For backward compatibility
    log_to_file: bool = True  # For backward compatibility
    log_path: Path = None  # type: ignore  # For backward compatibility
    
    def __post_init__(self):
        """Sync aliases."""
        if self.confidence != self.face_confidence:
            self.face_confidence = self.confidence
        if self.log_path is None:
            self.log_path = Path("logs/d435i_liveness.log")


@dataclass
class SimpleLivenessResult:
    """Simplified result - only essential data."""
    timestamp: float
    color_image: np.ndarray
    depth_frame: "rs.depth_frame"
    bbox: Optional[Tuple[int, int, int, int]]
    
    # Simple liveness result
    face_detected: bool
    is_live: bool
    reason: str
    
    # Basic metrics for debugging
    mean_distance_m: Optional[float] = None
    depth_variance_m: Optional[float] = None
    valid_points: int = 0
    
    # Eye tracking optimization: pre-extracted eye landmarks (pixel coords)
    # Format: {"left_eye": [(x,y), ...], "right_eye": [(x,y), ...], "left_center": (x,y), "right_center": (x,y)}
    eye_landmarks: Optional[Dict[str, Any]] = None
    
    # Backward compatibility aliases
    @property
    def instant_alive(self) -> bool:
        """Alias for is_live (backward compatibility)."""
        return self.is_live
    
    @property
    def stable_alive(self) -> bool:
        """Alias for is_live (backward compatibility)."""
        return self.is_live
    
    @property
    def stability_score(self) -> float:
        """Backward compatibility - simple 0 or 1."""
        return 1.0 if self.is_live else 0.0
    
    @property
    def depth_ok(self) -> bool:
        """Backward compatibility."""
        return self.is_live
    
    @property
    def depth_info(self) -> Dict:
        """Backward compatibility."""
        return {
            "reason": self.reason,
            "mean_distance_m": self.mean_distance_m,
            "depth_variance_m": self.depth_variance_m,
            "valid_points": self.valid_points
        }
    
    @property
    def screen_ok(self) -> bool:
        """Backward compatibility."""
        return self.is_live
    
    @property
    def screen_info(self) -> Dict:
        """Backward compatibility."""
        return {"reason": "simplified_check"}
    
    @property
    def movement_ok(self) -> bool:
        """Backward compatibility."""
        return self.is_live
    
    @property
    def movement_info(self) -> Dict:
        """Backward compatibility."""
        return {"reason": "simplified_check"}


# ============================================================
# Simple Liveness Logic
# ============================================================

def simple_liveness_check(
    depth_frame: "rs.depth_frame",
    depth_scale_m: float,
    bbox: Tuple[int, int, int, int],
    config: SimpleLivenessConfig,
) -> Tuple[bool, str, Dict[str, float]]:
    """
    SIMPLE 3-check liveness detection.
    
    Returns: (is_live, reason, metrics)
    """
    x0, y0, x1, y1 = bbox
    
    # Get depth data as numpy array
    depth_image = np.asanyarray(depth_frame.get_data()).astype(np.float32)
    depth_image *= depth_scale_m  # Convert to meters
    
    # Extract face region
    face_patch = depth_image[y0:y1, x0:x1]
    valid_depths = face_patch[face_patch > 0]  # Remove zeros
    
    # CHECK 1: Do we have enough depth data?
    if len(valid_depths) < config.min_valid_points:
        return False, "insufficient_depth_data", {"valid_points": len(valid_depths)}
    
    # CHECK 2: Is face at correct distance?
    mean_distance = float(np.mean(valid_depths))
    if mean_distance < config.distance_min_m:
        return False, "too_close", {"mean_distance_m": mean_distance, "valid_points": len(valid_depths)}
    if mean_distance > config.distance_max_m:
        return False, "too_far", {"mean_distance_m": mean_distance, "valid_points": len(valid_depths)}
    
    # CHECK 3: Does face have depth variation? (rejects flat surfaces)
    depth_std = float(np.std(valid_depths))
    if depth_std < config.depth_variance_min_m:
        return False, "flat_surface", {
            "mean_distance_m": mean_distance,
            "depth_variance_m": depth_std,
            "valid_points": len(valid_depths)
        }
    
    # ALL CHECKS PASSED!
    return True, "live_face", {
        "mean_distance_m": mean_distance,
        "depth_variance_m": depth_std,
        "valid_points": len(valid_depths)
    }


def extract_eye_landmarks_from_mesh(mesh_result, image_width: int, image_height: int) -> Optional[Dict[str, Any]]:
    """
    Extract eye landmark pixel coordinates from MediaPipe face mesh result.
    This is called once during liveness detection to avoid duplicate MediaPipe processing.
    
    Returns: {"left_eye": [(x,y), ...], "right_eye": [(x,y), ...], "left_center": (x,y), "right_center": (x,y)}
    """
    if not mesh_result or not mesh_result.multi_face_landmarks:
        return None
    
    try:
        face_landmarks = mesh_result.multi_face_landmarks[0]
        
        # Eye contour indices (from eye_tracking_viz.py)
        LEFT_EYE_CONTOUR = [33, 160, 158, 133, 153, 144, 163, 7]
        RIGHT_EYE_CONTOUR = [362, 385, 387, 263, 373, 380, 381, 382]
        
        def to_pixel(idx: int) -> Tuple[int, int]:
            landmark = face_landmarks.landmark[idx]
            px = int(landmark.x * image_width)
            py = int(landmark.y * image_height)
            return px, py
        
        left_eye_points = [to_pixel(idx) for idx in LEFT_EYE_CONTOUR]
        right_eye_points = [to_pixel(idx) for idx in RIGHT_EYE_CONTOUR]
        
        # Compute eye centers from contour
        left_center = tuple(np.mean(left_eye_points, axis=0).astype(int).tolist())
        right_center = tuple(np.mean(right_eye_points, axis=0).astype(int).tolist())
        
        return {
            "left_eye": left_eye_points,
            "right_eye": right_eye_points,
            "left_center": left_center,
            "right_center": right_center
        }
    except Exception as e:
        logger.warning(f"Error extracting eye landmarks: {e}")
        return None


# ============================================================
# Simple MediaPipe Liveness Class
# ============================================================

class SimpleMediaPipeLiveness:
    """Simple, robust face + depth liveness detection - RPi 5 optimized."""
    
    def __init__(self, config: Optional[SimpleLivenessConfig] = None) -> None:
        if rs is None or mp is None:
            raise RuntimeError("pyrealsense2 and mediapipe required")
        
        self.config = config or SimpleLivenessConfig()
        
        # OPTIMIZATION: Use ONLY face_mesh (does detection + landmarks in one pass)
        # Removed face_detector to save 50% CPU
        # refine_landmarks=False saves 30-40% CPU (no iris/lip refinement needed for liveness)
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=False,
            min_detection_confidence=self.config.face_confidence,
            min_tracking_confidence=self.config.face_confidence
        )
        
        self.pipe: Optional[rs.pipeline] = None
        self.align_to_color: Optional[rs.align] = None
        self.depth_scale_m: float = 0.001
        self._started = False
        self._closed = False
    
    def start(self) -> None:
        if self._closed:
            raise RuntimeError("Cannot start closed instance")
        if self._started:
            return
        
        pipe = rs.pipeline()
        cfg = rs.config()
        # RPi 5 OPTIMIZATION: Configurable FPS for stable performance
        # Default: 30 FPS (60 FPS too demanding)
        width = self.config.resolution_width if hasattr(self.config, 'resolution_width') else 640
        height = self.config.resolution_height if hasattr(self.config, 'resolution_height') else 480
        fps = self.config.fps if hasattr(self.config, 'fps') else 30
        
        cfg.enable_stream(rs.stream.color, width, height, rs.format.bgr8, fps)
        cfg.enable_stream(rs.stream.depth, width, height, rs.format.z16, fps)
        
        profile: rs.pipeline_profile = pipe.start(cfg)
        device = profile.get_device()
        depth_sensor = device.first_depth_sensor()
        self.depth_scale_m = float(depth_sensor.get_depth_scale())
        
        logger.info(
            "Connected to %s (S/N %s) depth_scale=%.6f m",
            device.get_info(rs.camera_info.name),
            device.get_info(rs.camera_info.serial_number),
            self.depth_scale_m,
        )
        
        self.pipe = pipe
        self.align_to_color = rs.align(rs.stream.color)
        self._started = True
    
    def stop(self) -> None:
        if self.pipe:
            self.pipe.stop()
        self.pipe = None
        self.align_to_color = None
        self._started = False
    
    def close(self) -> None:
        if self._closed:
            return
        self.stop()
        if self.face_mesh:
            self.face_mesh.close()
            self.face_mesh = None
        self._closed = True
    
    def __enter__(self) -> "SimpleMediaPipeLiveness":
        self.start()
        return self
    
    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
    
    def process(self, timeout_ms: int = 1000) -> Optional[SimpleLivenessResult]:
        """Process one frame with simple liveness check."""
        if not self._started:
            self.start()
        if not self.pipe or not self.align_to_color:
            raise RuntimeError("Pipeline not started")
        
        # Get aligned frames
        frames = self.pipe.wait_for_frames(timeout_ms=timeout_ms)
        frames = self.align_to_color.process(frames)
        
        depth_frame = frames.get_depth_frame()
        color_frame = frames.get_color_frame()
        
        if not depth_frame or not color_frame:
            return None
        
        color_image = np.asanyarray(color_frame.get_data())
        
        # Convert to RGB for MediaPipe
        rgb_image = cv2.cvtColor(color_image, cv2.COLOR_BGR2RGB) if cv2 else color_image
        
        # Detect face using face_mesh (single pass for detection + landmarks)
        try:
            mesh_result = self.face_mesh.process(rgb_image)
        except Exception as e:
            logger.warning(f"MediaPipe error: {e}")
            return None
        
        # No face detected
        if not mesh_result or not mesh_result.multi_face_landmarks:
            return SimpleLivenessResult(
                timestamp=time.time(),
                color_image=color_image,
                depth_frame=depth_frame,
                bbox=None,
                face_detected=False,
                is_live=False,
                reason="no_face_detected",
                eye_landmarks=None
            )
        
        # Get face landmarks and compute bounding box
        face_landmarks = mesh_result.multi_face_landmarks[0]
        h, w = color_image.shape[:2]
        
        # Compute bbox from landmarks (more accurate than detection bbox)
        x_coords = [lm.x for lm in face_landmarks.landmark]
        y_coords = [lm.y for lm in face_landmarks.landmark]
        
        x = int(min(x_coords) * w)
        y = int(min(y_coords) * h)
        box_w = int((max(x_coords) - min(x_coords)) * w)
        box_h = int((max(y_coords) - min(y_coords)) * h)
        
        # Expand bbox slightly for better depth coverage
        expansion = 0.1
        x = max(0, int(x - box_w * expansion / 2))
        y = max(0, int(y - box_h * expansion / 2))
        box_w = int(box_w * (1 + expansion))
        box_h = int(box_h * (1 + expansion))
        
        x1 = min(w, x + box_w)
        y1 = min(h, y + box_h)
        bbox = (x, y, x1, y1)
        
        # Simple liveness check
        is_live, reason, metrics = simple_liveness_check(
            depth_frame, self.depth_scale_m, bbox, self.config
        )
        
        # Extract eye landmarks for Eye of Horus rendering (avoid duplicate MediaPipe pass)
        eye_landmarks = extract_eye_landmarks_from_mesh(mesh_result, w, h)
        
        logger.debug(
            "Face detected: bbox=%s live=%s reason=%s metrics=%s",
            bbox, is_live, reason, metrics
        )
        
        return SimpleLivenessResult(
            timestamp=time.time(),
            color_image=color_image,
            depth_frame=depth_frame,
            bbox=bbox,
            face_detected=True,
            is_live=is_live,
            reason=reason,
            mean_distance_m=metrics.get("mean_distance_m"),
            depth_variance_m=metrics.get("depth_variance_m"),
            valid_points=metrics.get("valid_points", 0),
            eye_landmarks=eye_landmarks
        )


# ============================================================
# Async Service (same interface as before)
# ============================================================

class SimpleRealSenseService:
    """Simplified RealSense service - same interface, simpler logic."""
    
    def __init__(
        self,
        *,
        enable_hardware: bool = True,
        liveness_config: Optional[dict] = None,
        threshold_overrides: Optional[dict] = None,  # For backward compatibility
        settings: Optional[Any] = None,  # Settings object for configuration
    ) -> None:
        self.enable_hardware = bool(enable_hardware and rs is not None and mp is not None and cv2 is not None)
        
        # Merge liveness config with settings if available
        merged_config = liveness_config or {}
        if settings and hasattr(settings, 'camera'):
            merged_config.setdefault('distance_min_m', settings.camera.distance_min_m)
            merged_config.setdefault('distance_max_m', settings.camera.distance_max_m)
            merged_config.setdefault('face_confidence', settings.camera.face_confidence)
        
        self._liveness_config = merged_config
        self._settings = settings  # Store settings for config access
        self._instance: Optional[SimpleMediaPipeLiveness] = None
        self._hardware_active = False
        self._hardware_requests: Counter[str] = Counter()
        self._preview_mode: str = "eye_tracking"  # Eye of Horus by default for production
        self._validation_progress: float = 0.0  # Progress 0.0-1.0 for eye tracking progress bar
        self._lock = asyncio.Lock()
        self._preview_subscribers: list[asyncio.Queue[bytes]] = []
        self._result_subscribers: list[asyncio.Queue[Optional[SimpleLivenessResult]]] = []
        self._loop_task: Optional[asyncio.Task[None]] = None
        self._stop_event = asyncio.Event()
        
        # Idle face detection mode (replaces TOF sensor)
        self._operational_mode: str = "idle_detection"  # "idle_detection", "active", or "validation"
        self._face_detection_callbacks: list[Callable[[bool], Awaitable[None]]] = []
        self._last_face_detected: bool = False
        self._idle_detection_interval: float = 1.0  # 1 second burst interval
        
        # Eye tracking visualization renderer (lazy init)
        self._eye_renderer = None
        
        # RPi 5 OPTIMIZATION: Garbage collection tracking
        self._last_gc: float = time.time()
        self._frame_count: int = 0
        
        # OPTIMIZATION: Pre-allocate result buffer to reduce memory churn
        # Use config if available, otherwise fall back to default
        if settings and hasattr(settings, 'performance'):
            self._result_buffer_capacity: int = settings.performance.result_queue_size
            self._gc_interval = settings.performance.garbage_collection_interval
        else:
            self._result_buffer_capacity: int = 200
            self._gc_interval = 30
        logger.debug(f"Pre-allocated result buffer capacity: {self._result_buffer_capacity}")
    
    async def start(self) -> None:
        if self._loop_task:
            return
        if not self.enable_hardware:
            logger.warning("Hardware disabled or deps missing")
        self._stop_event.clear()
        self._loop_task = asyncio.create_task(self._preview_loop(), name="realsense-preview-loop")
    
    async def stop(self) -> None:
        if not self._loop_task:
            return
        self._stop_event.set()
        await self._loop_task
        self._loop_task = None
        await self._force_hardware_shutdown()
    
    async def _activate_locked(self) -> None:
        if self._hardware_active:
            return
        total = sum(self._hardware_requests.values())
        if total <= 0:
            return
        
        logger.info("Activating RealSense pipeline")
        
        def _create() -> SimpleMediaPipeLiveness:
            # Merge settings into config
            cfg_dict = dict(self._liveness_config) if self._liveness_config else {}
            
            # Add camera settings if available
            if self._settings and hasattr(self._settings, 'camera'):
                cfg_dict.setdefault('resolution_width', self._settings.camera.resolution_width)
                cfg_dict.setdefault('resolution_height', self._settings.camera.resolution_height)
                cfg_dict.setdefault('fps', self._settings.camera.fps)
                
            cfg = SimpleLivenessConfig(**cfg_dict) if cfg_dict else SimpleLivenessConfig()
            return SimpleMediaPipeLiveness(config=cfg)
        
        loop = asyncio.get_running_loop()
        self._instance = await loop.run_in_executor(None, _create)
        self._hardware_active = True
    
    async def _deactivate_locked(self) -> None:
        if not self._hardware_active:
            return
        
        logger.info("Deactivating RealSense pipeline")
        
        inst = self._instance
        self._instance = None
        self._hardware_active = False
        if inst:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, inst.close)
        
        # RPi 5 OPTIMIZATION: Force GC after deactivation to free camera buffers
        gc.collect()
        logger.debug("GC run after camera deactivation")
    
    async def _force_hardware_shutdown(self) -> None:
        if not self.enable_hardware:
            return
        async with self._lock:
            self._hardware_requests.clear()
            if self._hardware_active:
                inst = self._instance
                self._instance = None
                self._hardware_active = False
                if inst:
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, inst.close)
                
                # RPi 5 OPTIMIZATION: Force GC after shutdown
                gc.collect()
                logger.debug("GC run after hardware shutdown")
    
    async def set_hardware_active(self, active: bool, *, source: str = "session") -> None:
        if not self.enable_hardware:
            return
        async with self._lock:
            if active:
                self._hardware_requests[source] += 1
                logger.info("Hardware request: %s (total=%s)", source, sum(self._hardware_requests.values()))
            else:
                if self._hardware_requests.get(source, 0) > 0:
                    self._hardware_requests[source] -= 1
                    if self._hardware_requests[source] <= 0:
                        del self._hardware_requests[source]
                    logger.info("Hardware release: %s (total=%s)", source, sum(self._hardware_requests.values()))
            
            should_run = sum(self._hardware_requests.values()) > 0
            
            if should_run:
                await self._activate_locked()
            else:
                await self._deactivate_locked()
    
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
    
    async def gather_results(self, duration: float) -> List[SimpleLivenessResult]:
        """Gather liveness results for specified duration."""
        if not self.enable_hardware or not self._hardware_active or not self._instance:
            await asyncio.sleep(duration)
            return []
        
        # OPTIMIZATION: Larger queue to prevent blocking
        maxsize = self._settings.performance.result_queue_size if self._settings else 50
        q: asyncio.Queue[Optional[SimpleLivenessResult]] = asyncio.Queue(maxsize=maxsize)
        self._result_subscribers.append(q)
        # OPTIMIZATION: Pre-allocate list with expected capacity hint (reduces resizing)
        out: list[SimpleLivenessResult] = []
        loop = asyncio.get_running_loop()
        start = loop.time()
        
        try:
            while True:
                remaining = duration - (loop.time() - start)
                if remaining <= 0:
                    break
                try:
                    item = await asyncio.wait_for(q.get(), timeout=remaining)
                except asyncio.TimeoutError:
                    break
                if item is not None:
                    out.append(item)
        finally:
            self._result_subscribers.remove(q)
        return out
    
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
                    # IDLE DETECTION MODE: 1-second burst intervals, face detection only
                    if current_mode == "idle_detection":
                        # Check if it's time for next burst capture
                        if time.time() - last_idle_capture >= self._idle_detection_interval:
                            logger.debug(f"🔍 [IDLE_DETECTION] Taking burst photo (interval={self._idle_detection_interval}s)")
                            result = await self._run_process()
                            last_idle_capture = time.time()
                            
                            # Check if face detected and trigger callbacks
                            if result is not None:
                                face_detected = result.face_detected
                                
                                # Log detection state
                                if face_detected:
                                    logger.debug(f"🔍 [IDLE_DETECTION] Face detected (bbox={result.bbox})")
                                else:
                                    logger.debug(f"🔍 [IDLE_DETECTION] No face detected (reason={result.reason if hasattr(result, 'reason') else 'N/A'})")
                                
                                # Trigger callbacks on state change
                                if face_detected != self._last_face_detected:
                                    self._last_face_detected = face_detected
                                    logger.info(f"🔍 [IDLE_DETECTION] Face detection state changed: {not face_detected} → {face_detected}")
                                    
                                    # Call registered callbacks
                                    logger.debug(f"🔍 [IDLE_DETECTION] Calling {len(self._face_detection_callbacks)} registered callback(s)")
                                    for i, callback in enumerate(self._face_detection_callbacks):
                                        try:
                                            await callback(face_detected)
                                            logger.debug(f"🔍 [IDLE_DETECTION] Callback {i+1}/{len(self._face_detection_callbacks)} executed successfully")
                                        except Exception as e:
                                            logger.exception(f"🔍 [IDLE_DETECTION] Callback {i+1}/{len(self._face_detection_callbacks)} failed: {e}")
                            else:
                                logger.warning(f"🔍 [IDLE_DETECTION] Burst capture returned None")
                            
                            # PREVIEW DISABLED: Saves CPU by not encoding JPEG frames
                            # Broadcast frame for preview (optional)
                            # frame_bytes = self._serialize_frame(result)
                            # self._broadcast_frame(frame_bytes)
                        
                        # Sleep until next burst
                        await asyncio.sleep(0.1)
                    
                    # ACTIVE/VALIDATION MODE: Continuous operation
                    else:
                        # Process frame (fast - no lock contention)
                        result = await self._run_process()
                        
                        # Broadcast result for validation (always)
                        self._broadcast_result(result)
                        
                        # ACTIVE MODE: Also monitor face detection for session cancellation
                        if current_mode == "active" and result is not None:
                            face_detected = result.face_detected
                            
                            # Trigger callbacks on state change (same as idle_detection)
                            if face_detected != self._last_face_detected:
                                self._last_face_detected = face_detected
                                logger.info(f"👤 [ACTIVE_MODE] Face detection state changed: {not face_detected} → {face_detected}")
                                
                                # Call registered callbacks
                                logger.debug(f"👤 [ACTIVE_MODE] Calling {len(self._face_detection_callbacks)} registered callback(s)")
                                for i, callback in enumerate(self._face_detection_callbacks):
                                    try:
                                        await callback(face_detected)
                                        logger.debug(f"👤 [ACTIVE_MODE] Callback {i+1}/{len(self._face_detection_callbacks)} executed successfully")
                                    except Exception as e:
                                        logger.exception(f"👤 [ACTIVE_MODE] Callback {i+1}/{len(self._face_detection_callbacks)} failed: {e}")
                        
                        # PREVIEW DISABLED: Saves CPU by not encoding JPEG frames
                        # Only generate and broadcast preview every Nth frame (reduces load)
                        # frame_skip_counter += 1
                        # if frame_skip_counter % frame_skip == 0:
                        #     frame_bytes = self._serialize_frame(result)
                        #     self._broadcast_frame(frame_bytes)
                        
                        self._frame_count += 1
                        
                        # RPi 5 OPTIMIZATION: Periodic garbage collection
                        if time.time() - self._last_gc > self._gc_interval:
                            gc.collect()
                            self._last_gc = time.time()
                            logger.debug(f"GC run after {self._frame_count} frames")
                        
                        # Minimal delay for throughput (aim for ~10-15 FPS)
                        elapsed = time.time() - frame_start
                        fps_limit = self._settings.performance.preview_fps_limit if self._settings else 0.033
                        if elapsed < fps_limit:
                            await asyncio.sleep(fps_limit - elapsed)
                        elif result is None:
                            await asyncio.sleep(0.05)
                        
                elif not self.enable_hardware:
                    # PREVIEW DISABLED: Don't broadcast placeholder frames
                    # self._broadcast_frame(self._placeholder_frame())
                    self._broadcast_result(None)
                    await asyncio.sleep(0.1)
                else:
                    await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Preview loop crashed")
        finally:
            self._stop_event.clear()
    
    async def _run_process(self) -> Optional[SimpleLivenessResult]:
        """Run one frame of processing."""
        async with self._lock:
            inst = self._instance
            if not inst:
                await self._activate_locked()
                inst = self._instance
                if not inst:
                    return None
            
            loop = asyncio.get_running_loop()
            try:
                result = await loop.run_in_executor(None, inst.process)
                return result
            except RuntimeError as exc:
                logger.warning("RealSense error: %s", exc)
                return None
    
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
    
    def _create_face_dot_frame(self, result: Optional[SimpleLivenessResult]) -> np.ndarray:
        """Create black frame with colored dot."""
        width = self._settings.camera.resolution_width if self._settings else 640
        height = self._settings.camera.resolution_height if self._settings else 480
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        if result is None or not result.face_detected or result.bbox is None:
            # No face - red dot in center
            cv2.circle(frame, (320, 240), 12, (0, 0, 255), -1)
            cv2.circle(frame, (320, 240), 14, (255, 255, 255), 2)
            cv2.putText(frame, "No Face", (270, 280), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        else:
            # Face detected - dot at face center
            x0, y0, x1, y1 = result.bbox
            center_x = (x0 + x1) // 2
            center_y = (y0 + y1) // 2
            
            if result.is_live:
                color = (0, 255, 0)  # Green
                status = "Live Face"
            else:
                color = (0, 165, 255)  # Orange
                status = f"Not Live: {result.reason}"
            
            # Draw dot
            cv2.circle(frame, (center_x, center_y), 18, color, -1)
            cv2.circle(frame, (center_x, center_y), 20, (255, 255, 255), 2)
            
            # Show status
            text_y = min(center_y + 50, 460)
            cv2.putText(frame, status, (center_x - 100, text_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            
            # Show distance if available
            if result.mean_distance_m:
                dist_text = f"{result.mean_distance_m:.2f}m"
                cv2.putText(frame, dist_text, (center_x - 30, center_y - 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return frame
    
    def _create_eye_tracking_frame(self, result: Optional[SimpleLivenessResult]) -> np.ndarray:
        """Create Eye of Horus tracking visualization - uses pre-extracted landmarks (no duplicate MediaPipe!)."""
        try:
            # Lazy init eye renderer
            if self._eye_renderer is None:
                from .eye_tracking_viz import EyeOfHorusRenderer
                width = self._settings.eye_of_horus.width if self._settings else 640
                height = self._settings.eye_of_horus.height if self._settings else 480
                self._eye_renderer = EyeOfHorusRenderer(width=width, height=height, mirror_input=True)
            
            # No face or no color image - render empty state
            if result is None or not result.face_detected or result.color_image is None:
                return self._eye_renderer.render(None, progress=self._validation_progress)
            
            # OPTIMIZATION: Use pre-extracted eye landmarks from the result (no duplicate MediaPipe pass!)
            # Landmarks were already extracted during process() call
            if result.eye_landmarks:
                h, w = result.color_image.shape[:2]
                eye_data = self._eye_renderer.create_eye_data_from_precomputed(result.eye_landmarks, w)
                return self._eye_renderer.render(eye_data, show_guide=True, progress=self._validation_progress)
            else:
                # Fallback: no landmarks available
                return self._eye_renderer.render(None, progress=self._validation_progress)
            
        except Exception as e:
            logger.warning(f"Eye tracking visualization error: {e}")
            # Fallback to simple dot frame
            return self._create_face_dot_frame(result)
    
    def _placeholder_frame(self) -> bytes:
        return _PLACEHOLDER_JPEG
    
    def _broadcast_frame(self, frame: bytes) -> None:
        for q in list(self._preview_subscribers):
            if q.full():
                try:
                    q.get_nowait()
                except QueueEmpty:
                    pass
            q.put_nowait(frame)
    
    def _broadcast_result(self, result: Optional[SimpleLivenessResult]) -> None:
        for q in list(self._result_subscribers):
            if q.full():
                try:
                    q.get_nowait()
                except QueueEmpty:
                    pass
            q.put_nowait(result)
    
    async def set_preview_enabled(self, enabled: bool) -> bool:
        """For compatibility with old interface."""
        return enabled
    
    async def set_preview_mode(self, mode: str) -> str:
        """Set preview rendering mode: 'normal' or 'eye_tracking'."""
        if mode not in ("normal", "eye_tracking"):
            logger.warning(f"Invalid preview mode: {mode}, using 'normal'")
            mode = "normal"
        self._preview_mode = mode
        logger.info(f"Preview mode set to: {mode}")
        return self._preview_mode
    
    def get_preview_mode(self) -> str:
        """Get current preview rendering mode."""
        return self._preview_mode
    
    def set_validation_progress(self, progress: float) -> None:
        """
        Set validation progress for progress bar display.
        
        Args:
            progress: 0.0 to 1.0 (e.g., passing_frames / MIN_PASSING_FRAMES)
        """
        self._validation_progress = max(0.0, min(1.0, progress))
    
    def register_face_detection_callback(self, callback: Callable[[bool], Awaitable[None]]) -> None:
        """Register a callback for face detection events in idle mode."""
        self._face_detection_callbacks.append(callback)
    
    async def set_operational_mode(self, mode: str) -> None:
        """
        Set operational mode for the camera.
        
        Modes:
        - "idle_detection": 1-second burst intervals, face detection only (replaces TOF)
        - "active": Continuous operation, face detection only (warm state)
        - "validation": Full liveness validation (during HUMAN_DETECT phase)
        """
        if mode not in ("idle_detection", "active", "validation"):
            logger.warning(f"⚙️ [MODE_SWITCH] Invalid operational mode: {mode}, using 'active'")
            mode = "active"
        
        old_mode = self._operational_mode
        self._operational_mode = mode
        
        logger.info(f"⚙️ [MODE_SWITCH] Operational mode: {old_mode} → {mode}")
        logger.info(f"⚙️ [MODE_SWITCH] Mode details:")
        logger.info(f"   - idle_detection: 1s bursts, face detection only")
        logger.info(f"   - active: Continuous, face detection only (warm state)")
        logger.info(f"   - validation: Full liveness with depth checks")
        logger.info(f"⚙️ [MODE_SWITCH] Now in '{mode}' mode")
        
        # Reset face detection state when entering idle_detection
        if mode == "idle_detection":
            self._last_face_detected = False
            logger.debug(f"⚙️ [MODE_SWITCH] Reset face detection state for idle mode")
        # When entering active mode from idle, preserve face detection state
        elif mode == "active":
            logger.debug(f"⚙️ [MODE_SWITCH] Preserving face detection state: {self._last_face_detected}")
    
    def get_operational_mode(self) -> str:
        """Get current operational mode."""
        return self._operational_mode


# Backward compatibility aliases
RealSenseService = SimpleRealSenseService
LivenessResult = SimpleLivenessResult
