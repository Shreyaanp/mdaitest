"""Logging bootstrap for the controller service."""
from __future__ import annotations

import logging
from logging.config import dictConfig
from pathlib import Path


LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def configure_logging(level: str = "INFO") -> None:
    """Apply opinionated logging defaults for kiosk deployment."""

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
                    "class": "logging.handlers.RotatingFileHandler",
                    "formatter": "default",
                    "level": level,
                    "filename": str(LOG_DIR / "controller-runtime.log"),
                    "maxBytes": 2 * 1024 * 1024,
                    "backupCount": 5,
                    "encoding": "utf-8",
                },
            },
            "root": {"level": level, "handlers": ["console", "runtime_file"]},
        }
    )


__all__ = ["configure_logging"]
