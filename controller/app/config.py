"""Central configuration for the mdai controller service."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = ROOT_DIR / ".env"


# ============================================================
# Nested Configuration Classes
# ============================================================

class ValidationSettings(BaseModel):
    """Face validation configuration."""
    duration_seconds: float = Field(10.0, description="Duration to collect validation frames")
    min_passing_frames: int = Field(10, description="Minimum valid frames required to pass validation")
    camera_warmup_cold_ms: int = Field(2000, description="Camera warmup time when not pre-warmed (ms)")
    camera_warmup_warm_ms: int = Field(500, description="Camera stabilization time when pre-warmed (ms)")
    focus_normalization_threshold: float = Field(800.0, description="Focus score normalization divisor")
    stability_weight: float = Field(0.7, description="Weight for stability in composite score (0-1)")
    focus_weight: float = Field(0.3, description="Weight for focus in composite score (0-1)")


class PhaseDurations(BaseModel):
    """UI phase duration configuration (seconds)."""
    pairing_request: float = Field(1.2, description="Pairing request exit animation duration")
    hello_human: float = Field(3.0, description="Welcome screen duration")
    scan_prompt: float = Field(1.5, description="Scan prompt duration")
    complete: float = Field(3.0, description="Success screen duration")
    error: float = Field(3.0, description="Error screen duration")
    backend_ack_timeout: float = Field(3.0, description="Max wait for backend acknowledgment")


class CameraSettings(BaseModel):
    """RealSense camera hardware configuration."""
    resolution_width: int = Field(640, description="Camera stream width (pixels)")
    resolution_height: int = Field(480, description="Camera stream height (pixels)")
    fps: int = Field(30, description="Hardware capture frame rate")
    distance_min_m: float = Field(0.25, description="Minimum acceptable face distance (meters)")
    distance_max_m: float = Field(1.2, description="Maximum acceptable face distance (meters)")
    face_confidence: float = Field(0.5, description="MediaPipe face detection confidence threshold (0-1)")
    preview_frame_skip: int = Field(4, description="Encode preview every Nth frame (higher = less CPU)")
    
    
class PerformanceSettings(BaseModel):
    """Performance and queue tuning."""
    result_queue_size: int = Field(50, description="Max buffered validation results")
    preview_queue_size: int = Field(2, description="Max buffered preview JPEG frames")
    ui_event_queue_size: int = Field(4, description="Max buffered UI events")
    metrics_queue_size: int = Field(2, description="Max buffered metrics for debug")
    preview_fps_limit: float = Field(0.033, description="Minimum time between preview frames (seconds, 30 FPS)")
    garbage_collection_interval: int = Field(30, description="Garbage collection interval (seconds)")


class EyeOfHorusSettings(BaseModel):
    """Eye of Horus visualization configuration."""
    width: int = Field(640, description="Visualization canvas width")
    height: int = Field(480, description="Visualization canvas height")
    eye_spacing: int = Field(180, description="Fixed distance between eyes")
    eye_size: int = Field(130, description="Size of each eye")
    animation_speed: float = Field(0.05, description="Breathing animation speed")
    breath_amplitude: float = Field(0.12, description="Scale modulation for breathing effect")
    smoothing_factor: float = Field(0.6, description="Movement smoothing (lower = smoother)")
    state_change_threshold: int = Field(3, description="Consecutive frames needed to change state")


class Settings(BaseSettings):
    """Environment-driven settings for controller subsystems."""

    # Backend & API
    backend_api_url: str = Field(..., description="Bridge REST base URL (e.g. https://mdai.mercle.ai)")
    backend_ws_url: str = Field(..., description="Bridge WebSocket base URL (e.g. wss://mdai.mercle.ai/ws)")
    hardware_api_key: str = Field(..., description="API key used to mint hardware session tokens")

    # Controller HTTP Server
    controller_host: str = Field("0.0.0.0", description="Host interface for local FastAPI server")
    controller_port: int = Field(5000, description="Port for FastAPI server")

    # ToF Sensor
    tof_threshold_mm: int = Field(500, description="Distance threshold that triggers workflow")
    tof_debounce_ms: int = Field(1500, description="Debounce period before treating ToF trigger as valid")
    tof_i2c_bus: str = Field("/dev/i2c-1", description="I2C bus for ToF sensor")
    tof_i2c_address: int = Field(0x29, description="7-bit I2C address for ToF sensor")
    tof_output_hz: int = Field(10, description="ToF polling rate (Hz)")

    # RealSense Hardware
    realsense_enable_hardware: bool = Field(True, description="Enable RealSense hardware pipeline")

    # Logging
    log_level: str = Field("INFO", description="Logging level")
    log_directory: Path = Field(ROOT_DIR / "logs", description="Log directory path")
    log_retention_days: int = Field(14, description="Number of log files to retain")

    # Nested Configuration Objects
    validation: ValidationSettings = Field(default_factory=ValidationSettings, description="Validation phase settings")
    phases: PhaseDurations = Field(default_factory=PhaseDurations, description="UI phase durations")
    camera: CameraSettings = Field(default_factory=CameraSettings, description="Camera hardware settings")
    performance: PerformanceSettings = Field(default_factory=PerformanceSettings, description="Performance tuning")
    eye_of_horus: EyeOfHorusSettings = Field(default_factory=EyeOfHorusSettings, description="Eye of Horus visualization")

    # Legacy fields (deprecated but kept for backward compatibility)
    preview_frame_width: int = Field(640, description="DEPRECATED: Use camera.resolution_width")
    preview_frame_height: int = Field(480, description="DEPRECATED: Use camera.resolution_height")
    preview_fps: int = Field(30, description="DEPRECATED: Use camera.fps")
    mediapipe_stride: int = Field(3, description="DEPRECATED: No longer used")
    mediapipe_confidence: float = Field(0.6, description="DEPRECATED: Use camera.face_confidence")
    stability_seconds: float = Field(4.0, description="DEPRECATED: No longer used")
    mediapipe_max_horizontal_asymmetry_m: float = Field(0.12, description="DEPRECATED: No longer used")

    @field_validator("tof_i2c_address", mode="before")
    @classmethod
    def _parse_i2c_address(cls, value: object) -> object:
        if isinstance(value, str):
            parsed = value.strip()
            if not parsed:
                return parsed
            try:
                base = 16 if parsed.lower().startswith("0x") else 10
                return int(parsed, base)
            except ValueError as exc:  # pragma: no cover - defensive guardrail
                raise ValueError("TOF_I2C_ADDRESS must be an integer or hex string") from exc
        return value

    model_config = SettingsConfigDict(
        env_file=str(DEFAULT_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache()
def get_settings(override_env_file: Optional[Path] = None) -> Settings:
    """Cached Settings instance; accepts optional env override for tests."""

    if override_env_file:
        return Settings(_env_file=str(override_env_file))
    return Settings()
