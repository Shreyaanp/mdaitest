"""Shared controller state definitions for mdai kiosk."""
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any, Dict, Optional


class SessionPhase(str, enum.Enum):
    """
    Session phases in chronological order:
    
    1. IDLE              - Waiting for user (TV bars at 60%)
    2. PAIRING_REQUEST   - Requesting token (1.2s, exit animation)
    3. HELLO_HUMAN       - Welcome screen (2s)
    4. SCAN_PROMPT       - "Scan this to get started" (3s)
    5. QR_DISPLAY        - Show QR code (indefinite)
    6. HUMAN_DETECT      - Validate face (3.5s, need ≥10 passing frames)
    7. PROCESSING        - Upload + backend processing (3-15s)
    8. COMPLETE          - Success screen (3s) → IDLE
    9. ERROR             - Error screen (3s) → IDLE
    """
    IDLE = "idle"
    PAIRING_REQUEST = "pairing_request"
    HELLO_HUMAN = "hello_human"
    SCAN_PROMPT = "scan_prompt"
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
