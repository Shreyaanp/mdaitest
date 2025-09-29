"""RealSense capture + MediaPipe liveness bridge."""
from __future__ import annotations

import asyncio
from asyncio import QueueEmpty
import base64
import logging
from typing import AsyncIterator, List, Optional

logger = logging.getLogger(__name__)


_PLACEHOLDER_JPEG = base64.b64decode(
    b"/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD5/ooooA//2Q=="
)

try:  # pragma: no cover - optional dependency
    from d435i.mediapipe_liveness import LivenessConfig, LivenessResult, LivenessThresholds, MediaPipeLiveness
except Exception:  # noqa: BLE001 - broad to avoid hardware import failures during dev
    MediaPipeLiveness = None
    LivenessConfig = None
    LivenessResult = None
    LivenessThresholds = None


class RealSenseService:
    """Coordinates preview streaming and liveness evaluation."""

    def __init__(
        self,
        *,
        enable_hardware: bool = True,
        liveness_config: Optional[dict] = None,
        threshold_overrides: Optional[dict] = None,
    ) -> None:
        self.enable_hardware = enable_hardware and MediaPipeLiveness is not None
        self._liveness_config = liveness_config or {}
        self._threshold_overrides = threshold_overrides or {}
        self._instance: Optional[MediaPipeLiveness] = None
        self._hardware_active = False
        self._lock = asyncio.Lock()
        self._preview_subscribers: list[asyncio.Queue[bytes]] = []
        self._result_subscribers: list[asyncio.Queue[Optional[LivenessResult]]] = []
        self._loop_task: Optional[asyncio.Task[None]] = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        if self._loop_task:
            return
        if not self.enable_hardware:
            logger.warning("RealSense hardware disabled – using placeholder frames")
        else:
            logger.info("RealSense hardware idle until session start")
        self._stop_event.clear()
        self._loop_task = asyncio.create_task(self._preview_loop(), name="realsense-preview-loop")

    async def stop(self) -> None:
        if not self._loop_task:
            return
        self._stop_event.set()
        await self._loop_task
        self._loop_task = None
        await self.set_hardware_active(False)

    async def preview_stream(self) -> AsyncIterator[bytes]:
        queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=2)
        self._preview_subscribers.append(queue)
        try:
            while True:
                frame = await queue.get()
                yield frame
        finally:
            self._preview_subscribers.remove(queue)

    async def gather_results(self, duration: float) -> List[LivenessResult]:
        """Collect liveness results produced by the preview loop for a duration."""

        if not self.enable_hardware or not self._hardware_active or not self._instance:
            logger.warning("RealSense hardware inactive – gather_results will return empty list")
            await asyncio.sleep(duration)
            return []

        queue: asyncio.Queue[Optional[LivenessResult]] = asyncio.Queue(maxsize=5)
        self._result_subscribers.append(queue)
        collected: list[LivenessResult] = []
        loop = asyncio.get_running_loop()
        start = loop.time()
        try:
            while True:
                remaining = duration - (loop.time() - start)
                if remaining <= 0:
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=remaining)
                except asyncio.TimeoutError:
                    break
                if item is not None:
                    collected.append(item)
        finally:
            self._result_subscribers.remove(queue)
        return collected

    async def _preview_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                if self.enable_hardware and self._hardware_active and self._instance:
                    result = await self._run_process()
                    frame_bytes = self._serialize_frame(result)
                    self._broadcast_frame(frame_bytes)
                    self._broadcast_result(result)
                elif not self.enable_hardware:
                    frame_bytes = self._placeholder_frame()
                    self._broadcast_frame(frame_bytes)
                    self._broadcast_result(None)
                    await asyncio.sleep(0.1)
                else:
                    await asyncio.sleep(0.05)
        except asyncio.CancelledError:  # pragma: no cover - cooperative cancel
            raise
        except Exception:  # pragma: no cover - defensive guard
            logger.exception("RealSense preview loop crashed")
        finally:
            self._stop_event.clear()
            logger.info("RealSense preview loop stopped")

    async def _run_process(self) -> Optional[LivenessResult]:
        instance = self._instance
        if not instance:
            return None
        async with self._lock:
            loop = asyncio.get_running_loop()
            try:
                return await loop.run_in_executor(None, instance.process)
            except RuntimeError as exc:
                # RealSense occasionally fails to deliver a frame inside the default
                # 1s timeout. Rather than crash the preview loop we treat this as a
                # transient condition and retry on the next iteration.
                if "Frame didn't arrive" in str(exc):
                    logger.warning("RealSense frame timeout; retrying")
                    return None
                raise

    def _serialize_frame(self, result: Optional[LivenessResult]) -> bytes:
        if not result:
            return self._placeholder_frame()
        try:
            import cv2

            image = result.color_image
            ret, encoded = cv2.imencode(".jpg", image)
            if not ret:
                return self._placeholder_frame()
            payload = encoded.tobytes()
        except Exception:  # pragma: no cover - fallback path
            logger.exception("Failed to encode RealSense frame; falling back to placeholder")
            payload = self._placeholder_frame()
        return payload

    def _placeholder_frame(self) -> bytes:
        return _PLACEHOLDER_JPEG

    def _broadcast_frame(self, frame: bytes) -> None:
        for queue in list(self._preview_subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                except QueueEmpty:
                    pass
            queue.put_nowait(frame)

    def _broadcast_result(self, result: Optional[LivenessResult]) -> None:
        for queue in list(self._result_subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                except QueueEmpty:
                    pass
            queue.put_nowait(result)

    async def set_hardware_active(self, active: bool) -> None:
        if not self.enable_hardware:
            return

        async with self._lock:
            if active and not self._hardware_active:
                logger.info("Activating RealSense hardware pipeline")

                def _create() -> MediaPipeLiveness:
                    config = LivenessConfig(**self._liveness_config) if self._liveness_config else None
                    thresholds = (
                        LivenessThresholds(**self._threshold_overrides)
                        if self._threshold_overrides and LivenessThresholds is not None
                        else None
                    )
                    return MediaPipeLiveness(config=config, thresholds=thresholds)

                loop = asyncio.get_running_loop()
                self._instance = await loop.run_in_executor(None, _create)
                self._hardware_active = True
            elif not active and self._hardware_active:
                logger.info("Deactivating RealSense hardware pipeline")
                instance = self._instance
                self._instance = None
                self._hardware_active = False
                if instance:
                    loop = asyncio.get_running_loop()

                    def _close() -> None:
                        instance.close()

                    await loop.run_in_executor(None, _close)
