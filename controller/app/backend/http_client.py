"""HTTP client helpers for the websocket bridge REST endpoints."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from ..config import Settings

logger = logging.getLogger(__name__)


class BridgeHttpClient:
    """Thin wrapper around the bridge REST API."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = httpx.AsyncClient(base_url=self.settings.backend_api_url, timeout=15.0)

    async def issue_token(self) -> Optional[Dict[str, Any]]:
        """Exchange the hardware API key for a short-lived session token."""
        payload = {"api_key": self.settings.hardware_api_key}
        logger.info("bridge.issue_token: requesting new hardware token")
        response = await self._client.post("/auth", json=payload)
        response.raise_for_status()
        data = response.json()
        token = data.get("token")
        if not token:
            logger.error("bridge.issue_token: response missing token %s", data)
            return None
        return data

    async def aclose(self) -> None:
        await self._client.aclose()
