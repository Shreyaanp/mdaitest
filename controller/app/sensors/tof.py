"""Time-of-flight sensor abstraction with debounce logic."""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Optional

logger = logging.getLogger(__name__)

DistanceProvider = Callable[[], Awaitable[Optional[int]]]
TriggerCallback = Callable[[bool, int], Awaitable[None]]


class ToFSensor:
    """Async helper that polls a ToF sensor and emits trigger state changes."""

    def __init__(
        self,
        *,
        threshold_mm: int,
        debounce_ms: int = 150,
        poll_interval_ms: int = 50,
        distance_provider: DistanceProvider,
    ) -> None:
        self.threshold_mm = threshold_mm
        self.debounce_ms = debounce_ms
        self.poll_interval_ms = poll_interval_ms
        self.distance_provider = distance_provider

        self._task: Optional[asyncio.Task[None]] = None
        self._stop_event = asyncio.Event()
        self._callbacks: list[TriggerCallback] = []
        self._is_triggered = False
        self._last_toggle_ts = 0.0

    def register_callback(self, callback: TriggerCallback) -> None:
        self._callbacks.append(callback)

    async def start(self) -> None:
        if self._task:
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="tof-poller")

    async def stop(self) -> None:
        if not self._task:
            return
        self._stop_event.set()
        await self._task
        self._task = None

    async def _run_loop(self) -> None:
        logger.info("ToF sensor active (threshold=%dmm, debounce=%dms)", 
                   self.threshold_mm, self.debounce_ms)
        try:
            while not self._stop_event.is_set():
                distance = await self.distance_provider()
                if distance is None:
                    await asyncio.sleep(self.poll_interval_ms / 1000)
                    continue

                triggered = distance < self.threshold_mm
                now = time.monotonic() * 1000
                if triggered != self._is_triggered:
                    if now - self._last_toggle_ts >= self.debounce_ms:
                        self._is_triggered = triggered
                        self._last_toggle_ts = now
                        await self._emit(triggered, distance)
                await asyncio.sleep(self.poll_interval_ms / 1000)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("ToF sensor error: %s", exc)
            raise
        finally:
            self._stop_event.clear()

    async def _emit(self, triggered: bool, distance: int) -> None:
        """Emit trigger event to registered callbacks."""
        for callback in self._callbacks:
            try:
                await callback(triggered, distance)
            except Exception:
                logger.exception("ToF callback failed")

