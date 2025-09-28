"""Session orchestration for the mdai kiosk using the websocket bridge."""
from __future__ import annotations

import asyncio
from asyncio import QueueEmpty
import base64
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional
from urllib.parse import urlparse

from .backend.http_client import BridgeHttpClient
from .backend.ws_client import BackendWebSocketClient
from .config import Settings, get_settings
from .sensors.realsense import RealSenseService
from .sensors.tof import DistanceProvider, ToFSensor, mock_distance_provider
from .sensors.tof_process import ToFReaderProcess
from .state import ControllerEvent, SessionPhase

logger = logging.getLogger(__name__)


@dataclass
class SessionContext:
    token: Optional[str] = None
    expires_in: Optional[int] = None
    issued_at: Optional[float] = None
    platform_id: Optional[str] = None
    latest_distance_mm: Optional[int] = None
    best_frame_b64: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class SessionManager:
    """Coordinates sensors, bridge comms, and UI state updates."""

    def __init__(
        self,
        *,
        settings: Optional[Settings] = None,
        tof_distance_provider: Optional[DistanceProvider] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._lock = asyncio.Lock()
        self._phase: SessionPhase = SessionPhase.IDLE
        self._ui_subscribers: List[asyncio.Queue[ControllerEvent]] = []
        self._current_session = SessionContext()

        self._tof_process: Optional[ToFReaderProcess] = None
        if tof_distance_provider is None:
            if self.settings.tof_reader_binary:
                self._tof_process = ToFReaderProcess(
                    binary_path=self.settings.tof_reader_binary,
                    i2c_bus=self.settings.tof_i2c_bus,
                    i2c_address=self.settings.tof_i2c_address,
                    xshut_path=self.settings.tof_xshut_path,
                    output_hz=self.settings.tof_output_hz,
                )
                tof_distance_provider = self._tof_process.get_distance
            else:
                tof_distance_provider = mock_distance_provider

        self._tof = ToFSensor(
            threshold_mm=self.settings.tof_threshold_mm,
            debounce_ms=self.settings.tof_debounce_ms,
            distance_provider=tof_distance_provider,
        )
        self._tof.register_callback(self._handle_tof_trigger)

        self._realsense = RealSenseService(enable_hardware=self.settings.realsense_enable_hardware)
        self._http_client = BridgeHttpClient(self.settings)
        self._ws_client = BackendWebSocketClient(self.settings)

        self._session_task: Optional[asyncio.Task[None]] = None
        self._background_tasks: list[asyncio.Task[Any]] = []
        self._app_ready_event: Optional[asyncio.Event] = None
        self._ack_event: Optional[asyncio.Event] = None
        self._last_metrics_ts: float = 0.0

    @property
    def phase(self) -> SessionPhase:
        return self._phase

    async def start(self) -> None:
        logger.info("Starting session manager")
        if self._tof_process:
            await self._tof_process.start()
        await self._realsense.start()
        await self._tof.start()
        self._background_tasks.append(asyncio.create_task(self._heartbeat_loop(), name="controller-heartbeat"))

    async def stop(self) -> None:
        logger.info("Stopping session manager")
        await self._tof.stop()
        if self._tof_process:
            await self._tof_process.stop()
        await self._realsense.stop()
        for task in self._background_tasks:
            task.cancel()
        for task in self._background_tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._background_tasks.clear()
        await self._ws_client.disconnect()
        await self._http_client.aclose()

    def register_ui(self) -> asyncio.Queue[ControllerEvent]:
        queue: asyncio.Queue[ControllerEvent] = asyncio.Queue(maxsize=4)
        self._ui_subscribers.append(queue)
        return queue

    def unregister_ui(self, queue: asyncio.Queue[ControllerEvent]) -> None:
        if queue in self._ui_subscribers:
            self._ui_subscribers.remove(queue)

    async def trigger_debug_session(self) -> None:
        logger.info("Debug session trigger invoked")
        self._schedule_session()

    async def simulate_tof_trigger(self, *, triggered: bool, distance_mm: Optional[int] = None) -> None:
        """Public hook to emulate ToF sensor transitions for debugging."""

        if distance_mm is None:
            distance_mm = max(0, self.settings.tof_threshold_mm - 50)
        await self._handle_tof_trigger(triggered, distance_mm)

    async def mark_app_ready(self, *, platform_id: Optional[str] = None) -> bool:
        """Manually shortcut the app-ready handshake for local testing."""

        if platform_id:
            self._current_session.platform_id = platform_id

        if self._app_ready_event and not self._app_ready_event.is_set():
            self._app_ready_event.set()
            await self._broadcast(
                ControllerEvent(
                    type="backend",
                    phase=self._phase,
                    data={"event": "app_ready_override", "platform_id": platform_id},
                )
            )
            return True
        return False

    async def preview_frames(self) -> AsyncIterator[bytes]:
        async for frame in self._realsense.preview_stream():
            yield frame

    async def _broadcast(self, event: ControllerEvent) -> None:
        logger.debug("Broadcasting event: %s", event)
        for queue in list(self._ui_subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                except QueueEmpty:
                    pass
            queue.put_nowait(event)

    async def _set_phase(self, phase: SessionPhase, *, data: Optional[Dict[str, Any]] = None, error: Optional[str] = None) -> None:
        self._phase = phase
        await self._broadcast(ControllerEvent(type="state", data=data or {}, phase=phase, error=error))

    async def _handle_tof_trigger(self, triggered: bool, distance: int) -> None:
        logger.info("ToF trigger=%s distance=%s phase=%s", triggered, distance, self.phase)
        self._current_session.latest_distance_mm = distance
        if triggered and self.phase == SessionPhase.IDLE:
            self._schedule_session()
        elif not triggered and self.phase not in {SessionPhase.IDLE, SessionPhase.COMPLETE}:
            logger.info("ToF reset detected mid-session; cancelling active session")
            if self._session_task:
                self._session_task.cancel()

    def _schedule_session(self) -> None:
        if self._session_task and not self._session_task.done():
            logger.info("Session already in progress; ignoring trigger")
            return
        self._session_task = asyncio.create_task(self._run_session(), name="controller-session")

    async def _run_session(self) -> None:
        try:
            await self._set_phase(SessionPhase.PAIRING_REQUEST)
            token_info = await self._http_client.issue_token()
            if not token_info:
                await self._set_phase(SessionPhase.ERROR, error="token_issue_failed")
                return

            token = token_info.get("token")
            expires_in = token_info.get("expires_in")
            if not token:
                await self._set_phase(SessionPhase.ERROR, error="token_missing")
                return

            qr_payload = self._build_qr_payload(token)
            self._current_session = SessionContext(
                token=token,
                expires_in=expires_in,
                issued_at=time.time(),
                metadata={"qr_payload": qr_payload},
            )
            self._last_metrics_ts = 0.0

            await self._set_phase(
                SessionPhase.QR_DISPLAY,
                data={
                    "token": token,
                    "expires_in": expires_in,
                    "qr_payload": qr_payload,
                },
            )

            self._app_ready_event = asyncio.Event()
            self._ack_event = asyncio.Event()
            await self._ws_client.connect(token, self._handle_bridge_message)

            await self._await_app_ready()
            await self._set_phase(SessionPhase.HUMAN_DETECT)
            await self._realsense.set_hardware_active(True)
            await self._collect_best_frame()
            await self._upload_frame()
            await self._wait_for_ack()
            await self._set_phase(SessionPhase.COMPLETE)
        except asyncio.CancelledError:
            logger.info("Session cancelled")
            await self._set_phase(SessionPhase.IDLE)
            raise
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.exception("Session failed: %s", exc)
            await self._set_phase(SessionPhase.ERROR, error=str(exc))
        finally:
            await self._realsense.set_hardware_active(False)
            await self._ws_client.disconnect()
            await asyncio.sleep(1.0)
            await self._set_phase(SessionPhase.IDLE)
            self._session_task = None
            self._app_ready_event = None
            self._ack_event = None
            self._current_session = SessionContext()

    async def _await_app_ready(self) -> None:
        await self._set_phase(SessionPhase.WAITING_ACTIVATION)
        if not self._app_ready_event:
            raise RuntimeError("app_ready_event_not_initialized")
        timeout = self._token_timeout()
        logger.info("Waiting for app connection with timeout=%ss", timeout)
        await asyncio.wait_for(self._app_ready_event.wait(), timeout=timeout)

    def _token_timeout(self) -> float:
        expires_in = self._current_session.expires_in
        if not expires_in:
            return 90.0
        return max(10.0, expires_in - 5.0)

    async def _collect_best_frame(self) -> None:
        await self._set_phase(SessionPhase.STABILIZING)
        results = await self._realsense.gather_results(self.settings.stability_seconds)
        if not results:
            raise RuntimeError("liveness_capture_failed")

        best_bytes: Optional[bytes] = None
        best_score = -1.0

        for result in results:
            if not (result.instant_alive or result.stable_alive):
                continue
            focus_score = self._compute_focus(result.color_image)
            normalized_focus = min(focus_score / 800.0, 1.0)
            stability = result.stability_score
            composite = (stability * 0.7) + (normalized_focus * 0.3)
            if result.stable_alive:
                composite += 0.05
            if composite > best_score:
                encoded = self._encode_jpeg(result.color_image)
                if encoded is None:
                    continue
                best_bytes = encoded
                best_score = composite
            now = time.time()
            if now - self._last_metrics_ts >= 0.2:
                self._last_metrics_ts = now
                await self._broadcast(
                    ControllerEvent(
                        type="metrics",
                        phase=self._phase,
                        data={
                            "stability": stability,
                            "focus": focus_score,
                            "composite": composite,
                        },
                    )
                )

        if not best_bytes:
            raise RuntimeError("no_viable_frame")

        self._current_session.best_frame_b64 = base64.b64encode(best_bytes).decode()

    async def _upload_frame(self) -> None:
        await self._set_phase(SessionPhase.UPLOADING)
        if not self._current_session.best_frame_b64:
            raise RuntimeError("no_frame_to_upload")
        if not self._current_session.platform_id:
            raise RuntimeError("platform_id_missing")

        payload = {
            "type": "to_backend",
            "data": {
                "platform_id": self._current_session.platform_id,
                "image_base64": self._current_session.best_frame_b64,
            },
        }
        await self._ws_client.send(payload)

    async def _wait_for_ack(self) -> None:
        await self._set_phase(SessionPhase.WAITING_ACK)
        if not self._ack_event:
            raise RuntimeError("ack_event_not_initialized")
        await asyncio.wait_for(self._ack_event.wait(), timeout=120.0)

    async def _heartbeat_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(30)
                await self._broadcast(ControllerEvent(type="heartbeat", data={}, phase=self.phase))
        except asyncio.CancelledError:  # pragma: no cover - cooperative cancel
            raise

    async def _handle_bridge_message(self, message: dict[str, Any]) -> None:
        message_type = message.get("type")
        logger.info("Bridge message received: %s", message_type)

        if message_type == "joined":
            await self._broadcast(
                ControllerEvent(
                    type="backend",
                    phase=self._phase,
                    data={"event": "joined", "role": message.get("role")},
                )
            )
            return

        if message_type == "from_app":
            data = message.get("data") or {}
            await self._broadcast(
                ControllerEvent(
                    type="backend",
                    phase=self._phase,
                    data={"event": "from_app", "data": data},
                )
            )

            if data.get("message") == "hello":
                await self._ws_client.send({"type": "to_app", "data": {"message": "hello"}})
            platform_id = data.get("platform_id")
            if platform_id:
                self._current_session.platform_id = platform_id
                if self._app_ready_event and not self._app_ready_event.is_set():
                    self._app_ready_event.set()
            return

        if message_type == "backend_response":
            if self._ack_event and not self._ack_event.is_set():
                self._ack_event.set()
            await self._broadcast(
                ControllerEvent(
                    type="backend",
                    phase=self._phase,
                    data={
                        "event": "backend_response",
                        "status_code": message.get("status_code"),
                        "data": message.get("data"),
                        "latency_ms": message.get("latency_ms"),
                    },
                )
            )
            return

        if message_type == "status":
            await self._broadcast(
                ControllerEvent(
                    type="backend",
                    phase=self._phase,
                    data={"event": "status", "message": message.get("msg")},
                )
            )
            return

        if message_type == "error":
            detail = message.get("message", "unknown_error")
            await self._broadcast(
                ControllerEvent(
                    type="backend",
                    phase=self._phase,
                    data={"event": "error", "code": message.get("code"), "message": detail},
                )
            )
            raise RuntimeError(detail)

    def _build_qr_payload(self, token: str) -> Dict[str, Any]:
        ws_base = self.settings.backend_ws_url.rstrip('/')
        app_ws = f"{ws_base}/app"
        hardware_ws = f"{ws_base}/hardware"
        server_host = urlparse(self.settings.backend_api_url).netloc or self.settings.backend_api_url
        return {
            "token": token,
            "ws_app_url": app_ws,
            "ws_hardware_url": hardware_ws,
            "server_host": server_host,
        }

    @staticmethod
    def _compute_focus(image) -> float:
        try:
            import cv2

            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            return float(cv2.Laplacian(gray, cv2.CV_64F).var())
        except Exception:  # pragma: no cover - focus metric is best effort
            logger.exception("Failed to compute focus metric")
            return 0.0

    @staticmethod
    def _encode_jpeg(image) -> Optional[bytes]:
        try:
            import cv2

            success, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            if not success:
                return None
            return encoded.tobytes()
        except Exception:
            logger.exception("Failed to encode JPEG frame")
            return None
