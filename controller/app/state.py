"""Shared controller state definitions for mdai kiosk."""
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any, Dict, Optional


class SessionPhase(str, enum.Enum):
    """
    Session phases in chronological order:
    
    1. IDLE              - Waiting for user (TV bars at 60%)
    2. PAIRING_REQUEST   - Requesting token (1.5s, fall animation)
    3. HELLO_HUMAN       - Welcome screen (2s)
    4. QR_DISPLAY        - Show QR + "Scan to get started" (indefinite)
    5. HUMAN_DETECT      - Validate face (3.5s, need ≥10 passing frames)
    6. PROCESSING        - Upload + backend processing (3-15s)
    7. COMPLETE          - Success screen (3s) → IDLE
    8. ERROR             - Error screen (3s) → IDLE
    """
    IDLE = "idle"
    PAIRING_REQUEST = "pairing_request"
    HELLO_HUMAN = "hello_human"
    QR_DISPLAY = "qr_display"
    HUMAN_DETECT = "human_detect"
    PROCESSING = "processing"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class ControllerEvent:
    """Event payload distributed to UI clients over the local WebSocket."""

    type: str
    data: Dict[str, Any]
    phase: SessionPhase
    error: Optional[str] = None


__all__ = ["SessionPhase", "ControllerEvent"]
