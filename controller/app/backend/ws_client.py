"""Backend WebSocket client used during active sessions."""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Optional
from urllib.parse import urlencode

import websockets

from ..config import Settings

logger = logging.getLogger(__name__)

IncomingHandler = Callable[[dict[str, Any]], Awaitable[None]]


class BackendWebSocketClient:
    """Maintains bridge websocket connection for the hardware role."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._conn: Optional[websockets.client.WebSocketClientProtocol] = None
        self._listener_task: Optional[asyncio.Task[None]] = None
        self._stop_event = asyncio.Event()
        self._handler: Optional[IncomingHandler] = None

    async def connect(self, token: str, handler: IncomingHandler) -> None:
        try:
            await self.disconnect()
            uri = self._build_uri(token)
            logger.info("Connecting to bridge websocket %s", uri)
            self._stop_event.clear()
            self._handler = handler
            self._conn = await websockets.connect(uri, ping_interval=None, ping_timeout=None)
            self._listener_task = asyncio.create_task(self._listen(), name="bridge-ws-listener")
        except Exception as e:
            logger.error("Failed to connect to bridge websocket: %s", e)
            raise

    async def disconnect(self) -> None:
        try:
            self._stop_event.set()
            if self._listener_task:
                self._listener_task.cancel()
                try:
                    await self._listener_task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.warning("Error during listener task cleanup: %s", e)
            self._listener_task = None
            if self._conn:
                try:
                    await self._conn.close()
                except Exception as e:
                    logger.warning("Error closing websocket connection: %s", e)
                self._conn = None
            self._handler = None
        except Exception as e:
            logger.warning("Error during disconnect: %s", e)

    async def send(self, message: dict[str, Any]) -> None:
        if not self._conn:
            logger.warning("Cannot send message - bridge websocket not connected")
            return
        try:
            await self._conn.send(json.dumps(message))
        except websockets.ConnectionClosed:
            logger.warning("Cannot send message - websocket connection closed")
        except Exception as e:
            logger.error("Failed to send websocket message: %s", e)

    async def _listen(self) -> None:
        assert self._conn is not None
        try:
            async for message in self._conn:
                try:
                    payload = json.loads(message)
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON from bridge: %s", message)
                    continue

                if payload.get("type") == "ping":
                    await self.send({"type": "pong"})
                    continue

                if self._handler:
                    try:
                        await self._handler(payload)
                    except Exception as e:
                        logger.exception("Error in websocket message handler: %s", e)
        except asyncio.CancelledError:  # cooperative cancel
            raise
        except websockets.ConnectionClosedOK:
            logger.info("Bridge websocket closed cleanly")
        except websockets.ConnectionClosedError as exc:
            logger.warning("Bridge websocket closed: %s", exc)
        except Exception:  # pragma: no cover - defensive guard
            logger.exception("Bridge websocket listener crashed")
        finally:
            self._stop_event.set()
            self._listener_task = None
            if self._conn:
                await self._conn.close()
                self._conn = None

    def _build_uri(self, token: str) -> str:
        base = self.settings.backend_ws_url.rstrip('/')
        query = urlencode({"token": token})
        return f"{base}/hardware?{query}"
