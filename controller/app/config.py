"""Central configuration for the mdai controller service."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    """Environment-driven settings for controller subsystems."""

    backend_api_url: str = Field(..., description="Bridge REST base URL (e.g. https://mdai.mercle.ai)")
    backend_ws_url: str = Field(..., description="Bridge WebSocket base URL (e.g. wss://mdai.mercle.ai/ws)")
    hardware_api_key: str = Field(..., description="API key used to mint hardware session tokens")

    controller_host: str = Field("0.0.0.0", description="Host interface for local FastAPI server")
    controller_port: int = Field(5000, description="Port for FastAPI server")

    tof_threshold_mm: int = Field(500, description="Distance threshold that triggers workflow (increased for stability)")
    tof_debounce_ms: int = Field(1500, description="Debounce period before treating ToF trigger as valid (1.5s to avoid false triggers)")
    tof_reader_binary: Optional[str] = Field(
        None,
        description="Path to the compiled tof-reader executable (enables hardware polling when set)",
    )
    tof_i2c_bus: str = Field("/dev/i2c-1", description="I2C bus exposed by the ToF sensor")
    tof_i2c_address: int = Field(0x29, description="7-bit I2C address for the ToF sensor")
    tof_xshut_path: Optional[str] = Field(
        None,
        description="Optional sysfs GPIO value path to toggle the sensor XSHUT line",
    )
    tof_output_hz: int = Field(10, description="Polling rate (Hz) - reduced to 10Hz for less I2C traffic")
    tof_use_python: bool = Field(True, description="Use Python I2C implementation instead of C++ binary")

    preview_frame_width: int = Field(640, description="Preview width for MJPEG streaming")
    preview_frame_height: int = Field(480, description="Preview height for MJPEG streaming")
    preview_fps: int = Field(30, description="Target FPS for preview stream")

    mediapipe_stride: int = Field(3, description="Stride used by MediaPipe liveness worker")
    mediapipe_confidence: float = Field(0.6, description="Minimum face detector confidence")
    stability_seconds: float = Field(4.0, description="Duration the user must stay stable")
    mediapipe_max_horizontal_asymmetry_m: float = Field(
        0.12, description="Cheek asymmetry tolerance passed to the liveness worker"
    )

    realsense_enable_hardware: bool = Field(
        False, description="Enable RealSense hardware pipeline (set True on Jetson with camera attached)"
    )

    log_level: str = Field("INFO", description="Logging level for controller")
    log_directory: Path = Field(ROOT_DIR / "logs", description="Directory where controller logs are written")
    log_retention_days: int = Field(14, description="Number of rotated log files (days) to retain")

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
