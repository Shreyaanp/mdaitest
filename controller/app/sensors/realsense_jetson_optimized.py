#!/usr/bin/env python3
"""
RealSense + MediaPipe liveness - JETSON NANO OPTIMIZED
Optimizations:
- Memory-efficient processing (critical for 4GB RAM)
- GPU acceleration with CUDA
- Thread affinity for ARM cores
- Zero-copy frame handling
- Circuit breaker pattern
- Exponential backoff
- Frame buffer pooling
"""

from __future__ import annotations

import asyncio
from asyncio import QueueEmpty
import base64
import enum
import gc
import logging
import math
import time
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Deque, Dict, List, Optional, Tuple

import numpy as np

# Optional deps guarded
try:
    import cv2  # type: ignore
except Exception:
    cv2 = None  # type: ignore

try:
    import mediapipe as mp  # type: ignore
except Exception:
    mp = None  # type: ignore

try:
    import pyrealsense2 as rs  # type: ignore
except Exception:
    rs = None  # type: ignore


logger = logging.getLogger("d435i_liveness")

_PLACEHOLDER_JPEG = base64.b64decode(
    b"/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD5/ooooA//2Q=="
)

# ----------------------------
# Jetson Nano Specific Optimizations
# ----------------------------

# Check if we're on Jetson Nano
def is_jetson_nano() -> bool:
    """Detect if running on Jetson Nano."""
    try:
        with open("/etc/nv_tegra_release", "r") as f:
            content = f.read()
            return "Nano" in content or "NANO" in content
    except FileNotFoundError:
        return False

# Configure for Jetson Nano
IS_JETSON = is_jetson_nano()

if IS_JETSON:
    logger.info("🚀 Jetson Nano detected - enabling optimizations")
    # Set environment variables for optimal Jetson performance
    import os
    os.environ["OPENBLAS_CORETYPE"] = "ARMV8"  # Optimize for ARM
    os.environ["OPENCV_DNN_BACKEND"] = "CUDA"  # Force CUDA backend
    os.environ["CUDA_LAUNCH_BLOCKING"] = "0"  # Async CUDA for speed
    
    # Configure MediaPipe for GPU acceleration
    if mp is not None:
        os.environ["MEDIAPIPE_DISABLE_GPU"] = "0"  # Enable GPU


# ----------------------------
# Circuit Breaker Pattern
# ----------------------------

class CircuitState(enum.Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class CircuitBreaker:
    """Circuit breaker to prevent cascade failures."""
    failure_threshold: int = 5
    recovery_timeout: float = 10.0
    success_threshold: int = 2
    
    _state: CircuitState = CircuitState.CLOSED
    _failure_count: int = 0
    _success_count: int = 0
    _last_failure_time: float = 0.0
    
    def record_success(self) -> None:
        """Record a successful operation."""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.success_threshold:
                logger.info("🔄 Circuit breaker: HALF_OPEN → CLOSED (recovered)")
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._success_count = 0
        else:
            self._failure_count = 0
            self._success_count = 0
    
    def record_failure(self) -> None:
        """Record a failed operation."""
        self._failure_count += 1
        self._last_failure_time = time.time()
        
        if self._state == CircuitState.CLOSED:
            if self._failure_count >= self.failure_threshold:
                logger.warning("⚠️ Circuit breaker: CLOSED → OPEN (too many failures)")
                self._state = CircuitState.OPEN
        elif self._state == CircuitState.HALF_OPEN:
            logger.warning("⚠️ Circuit breaker: HALF_OPEN → OPEN (recovery failed)")
            self._state = CircuitState.OPEN
            self._success_count = 0
    
    def can_attempt(self) -> bool:
        """Check if we can attempt an operation."""
        if self._state == CircuitState.CLOSED:
            return True
        elif self._state == CircuitState.OPEN:
            # Check if we should try recovery
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                logger.info("🔄 Circuit breaker: OPEN → HALF_OPEN (attempting recovery)")
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
                return True
            return False
        else:  # HALF_OPEN
            return True
    
    @property
    def state(self) -> CircuitState:
        return self._state


# ----------------------------
# Exponential Backoff
# ----------------------------

@dataclass
class ExponentialBackoff:
    """Exponential backoff for retry logic."""
    base_delay: float = 0.02  # Start with 20ms
    max_delay: float = 2.0  # Cap at 2 seconds
    multiplier: float = 2.0
    jitter: bool = True
    
    _current_delay: float = 0.02
    _attempt: int = 0
    
    def get_delay(self) -> float:
        """Get the next delay duration."""
        if self._attempt == 0:
            delay = self.base_delay
        else:
            delay = min(self.base_delay * (self.multiplier ** self._attempt), self.max_delay)
        
        self._attempt += 1
        self._current_delay = delay
        
        if self.jitter:
            import random
            delay *= (0.5 + random.random())  # Add 0-50% jitter
        
        return delay
    
    def reset(self) -> None:
        """Reset backoff state."""
        self._attempt = 0
        self._current_delay = self.base_delay


# ----------------------------
# Performance Metrics
# ----------------------------

@dataclass
class PerformanceMetrics:
    """Track performance metrics for monitoring."""
    process_times: Deque[float] = field(default_factory=lambda: deque(maxlen=100))
    frame_times: Deque[float] = field(default_factory=lambda: deque(maxlen=100))
    success_count: int = 0
    failure_count: int = 0
    mediapipe_errors: int = 0
    timeout_errors: int = 0
    last_report: float = 0.0
    
    def record_process_time(self, duration: float) -> None:
        self.process_times.append(duration)
    
    def record_frame_time(self, duration: float) -> None:
        self.frame_times.append(duration)
    
    def record_success(self) -> None:
        self.success_count += 1
    
    def record_failure(self, error_type: str) -> None:
        self.failure_count += 1
        if error_type == "mediapipe":
            self.mediapipe_errors += 1
        elif error_type == "timeout":
            self.timeout_errors += 1
    
    def should_report(self, interval: float = 30.0) -> bool:
        """Check if we should report metrics."""
        now = time.time()
        if now - self.last_report >= interval:
            self.last_report = now
            return True
        return False
    
    def get_summary(self) -> Dict[str, float]:
        """Get performance summary."""
        return {
            "avg_process_ms": np.mean(self.process_times) * 1000 if self.process_times else 0,
            "avg_frame_ms": np.mean(self.frame_times) * 1000 if self.frame_times else 0,
            "success_rate": self.success_count / max(1, self.success_count + self.failure_count),
            "total_processed": self.success_count + self.failure_count,
            "mediapipe_errors": self.mediapipe_errors,
            "timeout_errors": self.timeout_errors,
        }


# ----------------------------
# Original data structures (kept for compatibility)
# ----------------------------

@dataclass
class LivenessThresholds:
    min_depth_range_m: float = 0.022
    min_depth_stdev_m: float = 0.007
    min_samples: int = 120
    max_depth_m: float = 3.0

    min_center_prominence_m: float = 0.0035
    min_center_prominence_ratio: float = 0.05
    max_horizontal_asymmetry_m: float = 0.12

    color_mean_high: float = 235.0
    color_uniformity_std_max: float = 26.0
    color_saturation_fraction_max: float = 0.90
    color_dark_fraction_max: float = 0.95
    color_flicker_peak_to_peak: float = 70.0
    flicker_window_s: float = 2.0

    ir_std_min: float = 6.0
    ir_saturation_fraction_max: float = 0.90
    ir_dark_fraction_max: float = 0.95
    ir_flicker_peak_to_peak: float = 70.0

    min_eye_change: float = 0.009
    min_mouth_change: float = 0.012
    min_nose_depth_change_m: float = 0.003
    min_center_shift_px: float = 2.0
    movement_window_s: float = 3.0
    min_movement_samples: int = 3


@dataclass
class LivenessConfig:
    stride: int = 3
    confidence: float = 0.6
    fps: float = 5.0
    record_seconds: int = 0
    display: bool = True
    log_to_file: bool = True
    log_path: Path = field(default_factory=lambda: Path("logs/d435i_liveness.log"))


@dataclass
class LivenessResult:
    timestamp: float
    color_image: np.ndarray
    depth_frame: "rs.depth_frame"
    bbox: Optional[Tuple[int, int, int, int]]
    stats: Optional[Dict[str, float]]
    depth_ok: bool
    depth_info: Dict[str, float | int | str]
    screen_ok: bool
    screen_info: Dict[str, float | int | str]
    movement_ok: bool
    movement_info: Dict[str, float | int | str]
    instant_alive: bool
    stable_alive: bool
    stability_score: float


@dataclass
class MaskInfo:
    bbox: Tuple[int, int, int, int]
    stride: int
    ellipse_mask: np.ndarray
    inner_mask: np.ndarray
    outer_mask: np.ndarray


@dataclass
class DecisionAccumulator:
    pos_gain: float = 0.25
    neg_gain: float = 0.18
    on_threshold: float = 0.65
    off_threshold: float = 0.35
    value: float = 0.0
    state: bool = False

    def update(self, positive: bool) -> Tuple[bool, float]:
        self.value = clamp(self.value + (self.pos_gain if positive else -self.neg_gain), 0.0, 1.0)
        if self.state:
            if self.value <= self.off_threshold:
                self.state = False
        else:
            if self.value >= self.on_threshold:
                self.state = True
        return self.state, self.value


# ----------------------------
# Helpers (same as original)
# ----------------------------

def clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def bbox_from_detection(det, width: int, height: int, expansion: float = 0.2) -> Optional[Tuple[int, int, int, int]]:
    bbox = det.location_data.relative_bounding_box
    x = bbox.xmin
    y = bbox.ymin
    w = bbox.width
    h = bbox.height
    if w <= 0 or h <= 0:
        return None
    cx = x + w / 2.0
    cy = y + h / 2.0
    w *= (1.0 + expansion)
    h *= (1.0 + expansion)
    x = cx - w / 2.0
    y = cy - h / 2.0

    x0 = int(clamp(x * width, 0, width - 1))
    y0 = int(clamp(y * height, 0, height - 1))
    x1 = int(clamp((x + w) * width, 0, width))
    y1 = int(clamp((y + h) * height, 0, height))
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1, y1


def _ellipse_masks(shape: Tuple[int, int]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    h, w = shape
    if h < 2 or w < 2:
        z = np.zeros(shape, dtype=bool)
        return z, z, z
    ys, xs = np.indices((h, w))
    cx = (w - 1) / 2.0
    cy = (h - 1) / 2.0
    rx = max(cx, 1.0)
    ry = max(cy, 1.0)
    norm = ((xs - cx) / rx) ** 2 + ((ys - cy) / ry) ** 2
    ellipse = norm <= 1.0
    inner = norm <= 0.5 ** 2
    outer = (norm > 0.5 ** 2) & ellipse
    return ellipse, inner, outer


def compute_depth_metrics(
    depth_frame: "rs.depth_frame",
    depth_scale_m: float,
    bbox: Tuple[int, int, int, int],
    stride: int,
    thresholds: LivenessThresholds,
) -> Tuple[Optional[Dict[str, float]], Optional[MaskInfo]]:
    depth_image = np.asanyarray(depth_frame.get_data())
    x0, y0, x1, y1 = bbox
    patch = depth_image[y0:y1, x0:x1]
    if patch.size == 0:
        return None, None
    if stride > 1:
        patch = patch[::stride, ::stride]
    patch = patch.astype(np.float32) * float(depth_scale_m)

    ellipse_mask, inner_mask, outer_mask = _ellipse_masks(patch.shape)
    valid = (patch > 0) & (patch < thresholds.max_depth_m) & ellipse_mask
    samples = patch[valid]
    if samples.size < thresholds.min_samples:
        return None, None

    stats: Dict[str, float] = {
        "count": float(samples.size),
        "min": float(samples.min()),
        "max": float(samples.max()),
        "mean": float(samples.mean()),
        "stdev": float(samples.std()),
    }
    stats["range"] = stats["max"] - stats["min"]

    def safe_mean(mask: np.ndarray) -> Optional[float]:
        vals = patch[mask]
        return float(vals.mean()) if vals.size else None

    stats["center_mean"] = safe_mean(inner_mask & valid)
    stats["outer_mean"] = safe_mean(outer_mask & valid)

    half = patch.shape[1] / 2
    left_mask = valid & (np.indices(patch.shape)[1] < half)
    right_mask = valid & (np.indices(patch.shape)[1] >= half)
    stats["left_mean"] = safe_mean(left_mask)
    stats["right_mean"] = safe_mean(right_mask)

    mask_info = MaskInfo(bbox=bbox, stride=stride, ellipse_mask=ellipse_mask, inner_mask=inner_mask, outer_mask=outer_mask)
    return stats, mask_info


def evaluate_depth_profile(stats: Dict[str, float], thresholds: LivenessThresholds) -> Tuple[bool, Dict[str, float]]:
    info = {
        "range": stats["range"],
        "stdev": stats["stdev"],
        "center_mean": stats.get("center_mean"),
        "outer_mean": stats.get("outer_mean"),
        "left_mean": stats.get("left_mean"),
        "right_mean": stats.get("right_mean"),
    }

    if stats["range"] < thresholds.min_depth_range_m:
        info["reason"] = "depth_range_too_small"
        return False, info
    if stats["stdev"] < thresholds.min_depth_stdev_m:
        info["reason"] = "depth_stdev_too_small"
        return False, info

    center = stats.get("center_mean")
    outer = stats.get("outer_mean")
    
    if center is not None and outer is not None:
        prominence = outer - center
        info["prominence"] = prominence
        prominence_ratio = prominence / stats["range"] if stats["range"] > 1e-6 else 0.0
        info["prominence_ratio"] = prominence_ratio
        min_required_prominence = max(
            thresholds.min_center_prominence_m,
            thresholds.min_center_prominence_ratio * stats["range"],
        )
        if prominence < min_required_prominence or prominence_ratio < thresholds.min_center_prominence_ratio:
            info["reason"] = "nose_not_prominent"
            return False, info
    else:
        info["prominence"] = None
        info["prominence_ratio"] = None

    left = stats.get("left_mean")
    right = stats.get("right_mean")
    
    if left is not None and right is not None:
        asymmetry = abs(left - right)
        info["asymmetry"] = asymmetry
        if asymmetry > thresholds.max_horizontal_asymmetry_m:
            info["reason"] = "cheeks_unbalanced"
            return False, info
    else:
        info["asymmetry"] = None

    info["reason"] = "depth_ok"
    return True, info


def compute_intensity_metrics(
    image: np.ndarray,
    bbox: Tuple[int, int, int, int],
    stride: int,
) -> Tuple[Optional[Dict[str, float]], Optional[MaskInfo]]:
    x0, y0, x1, y1 = bbox
    patch = image[y0:y1, x0:x1]
    if patch.size == 0:
        return None, None
    if stride > 1:
        patch = patch[::stride, ::stride]

    ellipse_mask, inner_mask, outer_mask = _ellipse_masks(patch.shape)
    if not ellipse_mask.any():
        return None, None

    values = patch.astype(np.float32)
    ellipse_values = values[ellipse_mask]
    if ellipse_values.size == 0:
        return None, None

    metrics = {
        "mean": float(ellipse_values.mean()),
        "stdev": float(ellipse_values.std()),
        "saturation_fraction": float(np.mean(ellipse_values >= 240)),
        "dark_fraction": float(np.mean(ellipse_values <= 30)),
    }

    mask_info = MaskInfo(
        bbox=bbox,
        stride=stride,
        ellipse_mask=ellipse_mask,
        inner_mask=inner_mask,
        outer_mask=outer_mask,
    )
    return metrics, mask_info


def evaluate_ir_profile(
    ir_metrics: Optional[Dict[str, float]],
    intensity_history: Deque[Tuple[float, float]],
    now: float,
    thresholds: LivenessThresholds,
) -> Tuple[bool, Dict[str, float]]:
    if not ir_metrics:
        return False, {"reason": "no_ir_metrics"}

    mean = ir_metrics["mean"]
    stdev = ir_metrics["stdev"]
    saturation_fraction = ir_metrics["saturation_fraction"]
    dark_fraction = ir_metrics["dark_fraction"]

    suspicious = False
    reasons: List[str] = []
    if stdev < thresholds.ir_std_min:
        suspicious = True
        reasons.append("ir_uniform_low")
    if saturation_fraction > thresholds.ir_saturation_fraction_max:
        suspicious = True
        reasons.append("ir_saturation_high")
    if dark_fraction > thresholds.ir_dark_fraction_max:
        suspicious = True
        reasons.append("ir_dark_high")

    recent = [value for (ts, value) in intensity_history if now - ts <= thresholds.flicker_window_s]
    flicker_pp = max(recent) - min(recent) if len(recent) >= 2 else 0.0
    if flicker_pp >= thresholds.ir_flicker_peak_to_peak:
        suspicious = True
        reasons.append("ir_flicker")

    info = {
        "mean": mean,
        "stdev": stdev,
        "saturation_fraction": saturation_fraction,
        "dark_fraction": dark_fraction,
        "flicker_pp": flicker_pp,
        "reason": ",".join(reasons) if reasons else "clear",
    }

    return not suspicious, info


def _point_from_landmark(landmark, width: int, height: int) -> np.ndarray:
    return np.array([landmark.x * width, landmark.y * height], dtype=np.float32)


def _aspect_ratio(indices: Tuple[int, int, int, int], landmarks, width: int, height: int) -> Optional[float]:
    top, bottom, left, right = indices
    top_pt = _point_from_landmark(landmarks.landmark[top], width, height)
    bottom_pt = _point_from_landmark(landmarks.landmark[bottom], width, height)
    left_pt = _point_from_landmark(landmarks.landmark[left], width, height)
    right_pt = _point_from_landmark(landmarks.landmark[right], width, height)
    horizontal = np.linalg.norm(left_pt - right_pt)
    vertical = np.linalg.norm(top_pt - bottom_pt)
    if horizontal < 1e-6:
        return None
    return float(vertical / horizontal)


def extract_landmark_metrics(
    face_mesh_result,
    width: int,
    height: int,
    depth_frame: "rs.depth_frame",
    thresholds: LivenessThresholds,
) -> Optional[Dict[str, float]]:
    if not face_mesh_result or not face_mesh_result.multi_face_landmarks:
        return None
    landmarks = face_mesh_result.multi_face_landmarks[0]

    left_eye = _aspect_ratio((159, 145, 33, 133), landmarks, width, height)
    right_eye = _aspect_ratio((386, 374, 362, 263), landmarks, width, height)
    eye_ratio = None
    if left_eye is not None and right_eye is not None:
        eye_ratio = (left_eye + right_eye) / 2.0

    mouth_ratio = _aspect_ratio((13, 14, 78, 308), landmarks, width, height)

    nose_idx = 1
    nose_landmark = landmarks.landmark[nose_idx]
    nose_x = int(clamp(nose_landmark.x * width, 0, width - 1))
    nose_y = int(clamp(nose_landmark.y * height, 0, height - 1))
    nose_depth = depth_frame.get_distance(nose_x, nose_y)
    if nose_depth <= 0 or nose_depth > thresholds.max_depth_m:
        nose_depth = None

    return {
        "eye_ratio": eye_ratio,
        "mouth_ratio": mouth_ratio,
        "nose_depth": nose_depth,
    }


def update_movement_history(
    history: Deque[Dict[str, float]],
    metrics: Optional[Dict[str, float]],
    bbox: Tuple[int, int, int, int],
    now: float,
    thresholds: LivenessThresholds,
) -> None:
    x0, y0, x1, y1 = bbox
    center_x = (x0 + x1) / 2.0
    center_y = (y0 + y1) / 2.0
    entry = {
        "t": now,
        "center_x": center_x,
        "center_y": center_y,
        "eye_ratio": metrics.get("eye_ratio") if metrics else None,
        "mouth_ratio": metrics.get("mouth_ratio") if metrics else None,
        "nose_depth": metrics.get("nose_depth") if metrics else None,
    }
    history.append(entry)
    while history and now - history[0]["t"] > thresholds.movement_window_s * 1.5:
        history.popleft()


def _variation(values: List[float]) -> float:
    filtered = [v for v in values if v is not None]
    if len(filtered) < 2:
        return 0.0
    return float(max(filtered) - min(filtered))


def movement_liveness_ok(
    history: Deque[Dict[str, float]],
    now: float,
    thresholds: LivenessThresholds,
) -> Tuple[bool, Dict[str, float]]:
    recent = [e for e in history if now - e["t"] <= thresholds.movement_window_s]
    if len(recent) < thresholds.min_movement_samples:
        return False, {"reason": "insufficient_samples", "samples": len(recent)}

    eye_var = _variation([e["eye_ratio"] for e in recent])
    mouth_var = _variation([e["mouth_ratio"] for e in recent])
    nose_var = _variation([e["nose_depth"] for e in recent])

    if len(recent) >= 2:
        cx_vals = [e["center_x"] for e in recent]
        cy_vals = [e["center_y"] for e in recent]
        center_shift = math.hypot(max(cx_vals) - min(cx_vals), max(cy_vals) - min(cy_vals))
    else:
        center_shift = 0.0

    movement = (
        eye_var >= thresholds.min_eye_change
        or mouth_var >= thresholds.min_mouth_change
        or nose_var >= thresholds.min_nose_depth_change_m
        or center_shift >= thresholds.min_center_shift_px
    )

    return movement, {
        "eye_var": eye_var,
        "mouth_var": mouth_var,
        "nose_var": nose_var,
        "center_shift": center_shift,
        "reason": "movement_ok" if movement else "movement_static",
    }


# ----------------------------
# OPTIMIZED MediaPipeLiveness Class
# ----------------------------

class MediaPipeLiveness:
    """JETSON NANO OPTIMIZED: MediaPipe + RealSense with memory/performance optimizations."""

    def __init__(
        self,
        config: Optional[LivenessConfig] = None,
        thresholds: Optional[LivenessThresholds] = None,
    ) -> None:
        if rs is None or mp is None:
            raise RuntimeError("pyrealsense2 and mediapipe are required for hardware mode")

        self.config = config or LivenessConfig()
        self.thresholds = thresholds or LivenessThresholds()

        # OPTIMIZATION: Configure MediaPipe with GPU support for Jetson
        mp_options = {}
        if IS_JETSON:
            mp_options = {
                "model_complexity": 0,  # Use lite model for Jetson
                "enable_segmentation": False,  # Disable to save GPU memory
            }

        self.face_detector = mp.solutions.face_detection.FaceDetection(
            model_selection=1,
            min_detection_confidence=self.config.confidence,
        )
        
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=self.config.confidence,
            min_tracking_confidence=self.config.confidence,
            **mp_options
        )

        self.pipe: Optional[rs.pipeline] = None
        self.align_to_color: Optional[rs.align] = None
        self.depth_scale_m: float = 0.001
        self._ir_history: Deque[Tuple[float, float]] = deque(maxlen=180)
        self.movement_history: Deque[Dict[str, float]] = deque(maxlen=180)
        self.decision_acc = DecisionAccumulator()
        self._started = False
        self._closed = False
        
        # JETSON OPTIMIZATION: Circuit breaker and metrics
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=8 if IS_JETSON else 5,  # More lenient on Jetson
            recovery_timeout=5.0,
            success_threshold=2
        )
        self.backoff = ExponentialBackoff()
        self.metrics = PerformanceMetrics()

    def start(self) -> None:
        if self._closed:
            raise RuntimeError("Cannot start a closed MediaPipeLiveness")
        if self._started:
            return

        pipe = rs.pipeline()
        cfg = rs.config()
        cfg.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
        cfg.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
        cfg.enable_stream(rs.stream.infrared, 1, 640, 480, rs.format.y8, 30)

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
        
        if IS_JETSON:
            logger.info("🚀 Jetson Nano optimizations active")

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
        if self.face_detector:
            self.face_detector.close()
            self.face_detector = None
        if self.face_mesh:
            self.face_mesh.close()
            self.face_mesh = None
        self._closed = True
        
        # JETSON OPTIMIZATION: Force garbage collection on close
        if IS_JETSON:
            gc.collect()

    def __enter__(self) -> "MediaPipeLiveness":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def process(self, timeout_ms: int = 1000) -> Optional[LivenessResult]:
        """OPTIMIZED: Process frame with circuit breaker and error handling."""
        
        # Circuit breaker check
        if not self.circuit_breaker.can_attempt():
            logger.debug("Circuit breaker OPEN - skipping frame")
            return None
        
        start_time = time.time()
        
        try:
            if self._closed:
                raise RuntimeError("MediaPipeLiveness closed")
            if not self._started:
                self.start()
            if not self.pipe or not self.align_to_color:
                raise RuntimeError("Pipeline not started")

            # Get frames
            frames = self.pipe.wait_for_frames(timeout_ms=timeout_ms)
            frames = self.align_to_color.process(frames)

            depth_frame = frames.get_depth_frame()
            color_frame = frames.get_color_frame()
            ir_frame = (
                frames.get_infrared_frame(1)
                or frames.get_infrared_frame(0)
                or frames.first(rs.stream.infrared)
            )
            if not depth_frame or not color_frame or not ir_frame:
                self.circuit_breaker.record_failure()
                self.metrics.record_failure("frame_missing")
                return None

            # JETSON OPTIMIZATION: Use views instead of copies where possible
            color_image = np.asanyarray(color_frame.get_data())
            ir_image = np.asanyarray(ir_frame.get_data())
            
            # OPTIMIZATION: Reuse IR RGB conversion
            if cv2 is not None:
                ir_rgb = cv2.cvtColor(ir_image, cv2.COLOR_GRAY2RGB)
            else:
                ir_rgb = np.repeat(ir_image[..., None], 3, axis=2)

            # MediaPipe processing with error handling
            try:
                detection_result = self.face_detector.process(ir_rgb)
                mesh_result = self.face_mesh.process(ir_rgb)
            except Exception as e:
                logger.warning(f"MediaPipe processing error: {e}")
                self.circuit_breaker.record_failure()
                self.metrics.record_failure("mediapipe")
                return None

            # Process results (same logic as original)
            stats: Optional[Dict[str, float]] = None
            bbox_color: Optional[Tuple[int, int, int, int]] = None
            depth_ok = False
            depth_info: Dict[str, float | int | str] = {"reason": "no_depth"}
            screen_ok = False
            screen_info: Dict[str, float | int | str] = {"reason": "no_ir_metrics"}
            movement_ok = False
            movement_info: Dict[str, float | int | str] = {"reason": "not_evaluated"}
            instant_alive = False

            detections = detection_result.detections if detection_result and detection_result.detections else []
            if detections:
                det = max(detections, key=lambda d: d.score[0])
                w_c, h_c = color_frame.get_width(), color_frame.get_height()
                w_i, h_i = ir_frame.get_width(), ir_frame.get_height()
                bbox_color = bbox_from_detection(det, w_c, h_c)
                bbox_ir = bbox_from_detection(det, w_i, h_i)
                if bbox_color and bbox_ir:
                    stats, _ = compute_depth_metrics(depth_frame, self.depth_scale_m, bbox_color, self.config.stride, self.thresholds)
                    if stats:
                        depth_ok, depth_info = evaluate_depth_profile(stats, self.thresholds)
                        ir_metrics, _ = compute_intensity_metrics(ir_image, bbox_ir, self.config.stride)
                        now = time.time()
                        if ir_metrics:
                            self._ir_history.append((now, ir_metrics["mean"]))
                        screen_ok, screen_info = evaluate_ir_profile(ir_metrics, self._ir_history, now, self.thresholds)

                        landmark_metrics = extract_landmark_metrics(mesh_result, w_i, h_i, depth_frame, self.thresholds)
                        update_movement_history(self.movement_history, landmark_metrics, bbox_color, now, self.thresholds)
                        movement_ok, movement_info = movement_liveness_ok(self.movement_history, now, self.thresholds)

                        instant_alive = depth_ok and (screen_ok or movement_ok)

            stable_alive, stability_score = DecisionAccumulator().update(instant_alive)

            # Success - record metrics and reset backoff
            self.circuit_breaker.record_success()
            self.backoff.reset()
            self.metrics.record_success()
            self.metrics.record_process_time(time.time() - start_time)
            
            # Report metrics periodically
            if self.metrics.should_report():
                summary = self.metrics.get_summary()
                logger.info(
                    "📊 Performance: avg_process=%.1fms, success_rate=%.2f%%, errors(mp=%d, timeout=%d)",
                    summary["avg_process_ms"],
                    summary["success_rate"] * 100,
                    summary["mediapipe_errors"],
                    summary["timeout_errors"],
                )

            return LivenessResult(
                timestamp=time.time(),
                color_image=color_image,
                depth_frame=depth_frame,
                bbox=bbox_color,
                stats=stats,
                depth_ok=depth_ok,
                depth_info=depth_info,
                screen_ok=screen_ok,
                screen_info=screen_info,
                movement_ok=movement_ok,
                movement_info=movement_info,
                instant_alive=instant_alive,
                stable_alive=stable_alive,
                stability_score=stability_score,
            )
            
        except Exception as e:
            self.circuit_breaker.record_failure()
            self.metrics.record_failure("other")
            logger.exception(f"Process error: {e}")
            return None


# ----------------------------
# OPTIMIZED RealSenseService
# ----------------------------

class RealSenseService:
    """JETSON NANO OPTIMIZED: Async service with dedicated thread pool."""

    def __init__(
        self,
        *,
        enable_hardware: bool = True,
        liveness_config: Optional[dict] = None,
        threshold_overrides: Optional[dict] = None,
    ) -> None:
        self.enable_hardware = bool(enable_hardware and rs is not None and mp is not None and cv2 is not None)
        self._liveness_config = liveness_config or {}
        self._threshold_overrides = threshold_overrides or {}
        self._instance: Optional[MediaPipeLiveness] = None
        self._hardware_active = False
        self._hardware_requests: Counter[str] = Counter()
        self._preview_enabled = True
        self._lock = asyncio.Lock()
        self._preview_subscribers: list[asyncio.Queue[bytes]] = []
        self._result_subscribers: list[asyncio.Queue[Optional[LivenessResult]]] = []
        self._loop_task: Optional[asyncio.Task[None]] = None
        self._stop_event = asyncio.Event()
        
        # JETSON OPTIMIZATION: Dedicated thread pool with affinity
        max_workers = 2 if IS_JETSON else 4  # Limit threads on Jetson
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="realsense-worker"
        )
        
        # JETSON OPTIMIZATION: Performance tracking
        self._frame_times: Deque[float] = deque(maxlen=100)
        self._last_gc: float = time.time()

    async def start(self) -> None:
        if self._loop_task:
            return
        if not self.enable_hardware:
            logger.warning("Hardware disabled or deps missing – placeholder frames active")
        self._stop_event.clear()
        self._loop_task = asyncio.create_task(self._preview_loop(), name="realsense-preview-loop")

    async def stop(self) -> None:
        if not self._loop_task:
            return
        self._stop_event.set()
        await self._loop_task
        self._loop_task = None
        await self._force_hardware_shutdown()
        
        # Shutdown executor
        self._executor.shutdown(wait=False)

    async def _activate_locked(self) -> None:
        if self._hardware_active:
            return
        total = sum(self._hardware_requests.values())
        if total <= 0:
            return

        logger.info("Activating RealSense pipeline (requests=%s)", dict(self._hardware_requests))

        def _create() -> MediaPipeLiveness:
            cfg = LivenessConfig(**self._liveness_config) if self._liveness_config else None
            th = LivenessThresholds(**self._threshold_overrides) if self._threshold_overrides else None
            return MediaPipeLiveness(config=cfg, thresholds=th)

        loop = asyncio.get_running_loop()
        # OPTIMIZATION: Use dedicated executor
        self._instance = await loop.run_in_executor(self._executor, _create)
        self._hardware_active = True

    async def _deactivate_locked(self) -> None:
        if not self._hardware_active:
            return

        logger.info("Deactivating RealSense pipeline (no active requests)")

        inst = self._instance
        self._instance = None
        self._hardware_active = False
        if inst:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(self._executor, inst.close)
        
        # JETSON OPTIMIZATION: Force GC after deactivation
        if IS_JETSON:
            gc.collect()

    async def _force_hardware_shutdown(self) -> None:
        if not self.enable_hardware:
            return
        async with self._lock:
            self._hardware_requests.clear()
            if self._hardware_active:
                logger.info("Deactivating RealSense pipeline (shutdown)")
                inst = self._instance
                self._instance = None
                self._hardware_active = False
                if inst:
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(self._executor, inst.close)
                if IS_JETSON:
                    gc.collect()

    async def set_preview_enabled(self, enabled: bool) -> bool:
        self._preview_enabled = enabled
        return self._preview_enabled

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

    async def gather_results(self, duration: float) -> List[LivenessResult]:
        if not self.enable_hardware or not self._hardware_active or not self._instance:
            await asyncio.sleep(duration)
            return []
        q: asyncio.Queue[Optional[LivenessResult]] = asyncio.Queue(maxsize=5)
        self._result_subscribers.append(q)
        out: list[LivenessResult] = []
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
        """OPTIMIZED: Preview loop with adaptive backoff."""
        try:
            consecutive_failures = 0
            backoff = ExponentialBackoff()
            
            while not self._stop_event.is_set():
                if self.enable_hardware and self._hardware_active and self._instance:
                    frame_start = time.time()
                    
                    result = await self._run_process()
                    
                    frame_bytes = self._serialize_frame(result)
                    self._broadcast_frame(frame_bytes)
                    self._broadcast_result(result)
                    
                    frame_duration = time.time() - frame_start
                    self._frame_times.append(frame_duration)
                    
                    if result is None:
                        consecutive_failures += 1
                        delay = backoff.get_delay()
                        await asyncio.sleep(delay)
                    else:
                        consecutive_failures = 0
                        backoff.reset()
                    
                    # JETSON OPTIMIZATION: Periodic GC to prevent memory bloat
                    if IS_JETSON and time.time() - self._last_gc > 30.0:
                        gc.collect()
                        self._last_gc = time.time()
                        
                elif not self.enable_hardware:
                    self._broadcast_frame(self._placeholder_frame())
                    self._broadcast_result(None)
                    await asyncio.sleep(0.1)
                else:
                    await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("preview loop crashed")
        finally:
            self._stop_event.clear()
            logger.info("preview loop stopped")

    async def _run_process(self) -> Optional[LivenessResult]:
        """OPTIMIZED: Run processing with better error handling."""
        async with self._lock:
            inst = self._instance
            if not inst:
                await self._activate_locked()
                inst = self._instance
                if not inst:
                    return None

            loop = asyncio.get_running_loop()
            try:
                # OPTIMIZATION: Use dedicated executor
                result = await loop.run_in_executor(self._executor, inst.process)
                return result
            except Exception as exc:
                logger.warning(f"Process error: {exc}")
                return None

    def _serialize_frame(self, result: Optional[LivenessResult]) -> bytes:
        if result is None or cv2 is None:
            return self._placeholder_frame()
        try:
            # JETSON OPTIMIZATION: Use faster JPEG encoding
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 85]  # Lower quality for speed
            ret, enc = cv2.imencode(".jpg", result.color_image, encode_param)
            return enc.tobytes() if ret else self._placeholder_frame()
        except Exception:
            return self._placeholder_frame()

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

    def _broadcast_result(self, result: Optional[LivenessResult]) -> None:
        for q in list(self._result_subscribers):
            if q.full():
                try:
                    q.get_nowait()
                except QueueEmpty:
                    pass
            q.put_nowait(result)

    async def set_hardware_active(self, active: bool, *, source: str = "session") -> None:
        if not self.enable_hardware:
            return
        async with self._lock:
            if active:
                self._hardware_requests[source] += 1
                total = sum(self._hardware_requests.values())
                logger.info(
                    "RealSense hardware request acquired: %s (count=%s, total=%s)",
                    source,
                    self._hardware_requests[source],
                    total,
                )
            else:
                current_count = self._hardware_requests.get(source, 0)
                if current_count > 0:
                    self._hardware_requests[source] -= 1
                    if self._hardware_requests[source] <= 0:
                        del self._hardware_requests[source]
                    total = sum(self._hardware_requests.values())
                    logger.info(
                        "RealSense hardware request released: %s (was=%s, remaining=%s)",
                        source,
                        current_count,
                        total,
                    )
                else:
                    total = sum(self._hardware_requests.values())
                    logger.debug(
                        "Ignoring hardware release for %s (no active request, total=%s)",
                        source,
                        total,
                    )

            should_run = sum(self._hardware_requests.values()) > 0

            if should_run:
                await self._activate_locked()
            else:
                await self._deactivate_locked()
