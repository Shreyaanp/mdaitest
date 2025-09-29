"""Logging bootstrap for the controller service."""
from __future__ import annotations

import logging
from logging.config import dictConfig
from pathlib import Path
from typing import Optional


def configure_logging(level: str = "INFO", log_dir: Optional[Path] = None, retention_days: int = 14) -> None:
    """Apply opinionated logging defaults for kiosk deployment."""

    if log_dir is None:
        log_dir = Path(__file__).resolve().parents[2] / "logs"
    log_dir = Path(log_dir).expanduser()
    log_dir.mkdir(parents=True, exist_ok=True)

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "level": level,
                },
                "runtime_file": {
                    "class": "logging.handlers.TimedRotatingFileHandler",
                    "formatter": "default",
                    "level": level,
                    "filename": str(log_dir / "controller-runtime.log"),
                    "when": "midnight",
                    "backupCount": max(int(retention_days), 1),
                    "utc": True,
                    "delay": True,
                    "encoding": "utf-8",
                },
            },
            "root": {"level": level, "handlers": ["console", "runtime_file"]},
        }
    )


__all__ = ["configure_logging"]
