"""Session orchestration for the mdai kiosk using the websocket bridge."""
from __future__ import annotations

import asyncio
from asyncio import QueueEmpty
import base64
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional
from urllib.parse import urlparse

from .backend.http_client import BridgeHttpClient
from .backend.ws_client import BackendWebSocketClient
from .config import Settings, get_settings
from .sensors.realsense import RealSenseService
from .sensors.tof import DistanceProvider, ToFSensor
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


class SessionFlowError(RuntimeError):
    """Raised when a recoverable session step fails."""

    def __init__(self, user_message: str, *, log_message: Optional[str] = None) -> None:
        super().__init__(log_message or user_message)
        self.user_message = user_message


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
        self._phase_started_at: float = time.time()
        self._ui_subscribers: List[asyncio.Queue[ControllerEvent]] = []
        self._current_session = SessionContext()

        # ToF sensor is required for production
        self._tof_process: Optional[ToFReaderProcess] = None
        if tof_distance_provider is None:
            if not self.settings.tof_reader_binary:
                raise RuntimeError("ToF reader binary path not configured. Set TOF_READER_BINARY in .env")
            
            self._tof_process = ToFReaderProcess(
                binary_path=self.settings.tof_reader_binary,
                i2c_bus=self.settings.tof_i2c_bus,
                i2c_address=self.settings.tof_i2c_address,
                xshut_path=self.settings.tof_xshut_path,
                output_hz=self.settings.tof_output_hz,
            )
            tof_distance_provider = self._tof_process.get_distance

        self._tof = ToFSensor(
            threshold_mm=self.settings.tof_threshold_mm,
            debounce_ms=self.settings.tof_debounce_ms,
            distance_provider=tof_distance_provider,
        )
        self._tof.register_callback(self._handle_tof_trigger)

        liveness_config = {
            "confidence": self.settings.mediapipe_confidence,
            "stride": self.settings.mediapipe_stride,
            "display": False,
        }
        # Relaxed thresholds to reduce false negatives
        threshold_overrides = {
            "max_horizontal_asymmetry_m": 0.15,  # Increased from 0.12 to allow more facial asymmetry
            "min_depth_range_m": 0.015,  # Reduced from 0.022 to accept flatter depth profiles
            "min_depth_stdev_m": 0.005,  # Reduced from 0.007 to accept less depth variation
            "min_center_prominence_m": 0.002,  # Reduced from 0.0035 to be less strict on nose prominence
            "min_center_prominence_ratio": 0.03,  # Reduced from 0.05 for better tolerance
            "min_samples": 80,  # Reduced from 120 to need fewer valid depth points
            "ir_std_min": 4.0,  # Reduced from 6.0 to allow more uniform IR patterns
            "min_eye_change": 0.005,  # Reduced from 0.009 for micro-movements
            "min_mouth_change": 0.008,  # Reduced from 0.012 for subtle expressions
            "min_nose_depth_change_m": 0.002,  # Reduced from 0.003 for small head movements
            "min_center_shift_px": 1.0,  # Reduced from 2.0 for small position changes
            "movement_window_s": 2.5,  # Reduced from 3.0 for faster detection
            "min_movement_samples": 2,  # Reduced from 3 to detect movement faster
        }
        self._realsense = RealSenseService(
            enable_hardware=self.settings.realsense_enable_hardware,
            liveness_config=liveness_config,
            threshold_overrides=threshold_overrides,
        )
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
        try:
            if self._tof_process:
                await self._tof_process.start()
            await self._tof.start()
        except Exception as e:
            logger.error("Failed to start ToF sensor: %s", e)
            logger.error("ToF sensor is required. Check hardware connection and configuration.")
            raise
        
        try:
            await self._realsense.start()
        except Exception as e:
            logger.exception("Failed to start RealSense service: %s", e)
            # Continue anyway - RealSense might not be available yet
        
        self._background_tasks.append(asyncio.create_task(self._heartbeat_loop(), name="controller-heartbeat"))
        logger.info("Session manager started in IDLE state (camera inactive)")

    async def stop(self) -> None:
        logger.info("Stopping session manager")
        
        # Stop ToF sensor
        try:
            await self._tof.stop()
            if self._tof_process:
                await self._tof_process.stop()
        except Exception as e:
            logger.warning("Error stopping ToF sensor: %s", e)
        
        # Stop RealSense
        try:
            await self._realsense.stop()
        except Exception as e:
            logger.warning("Error stopping RealSense service: %s", e)
        
        # Cancel background tasks
        for task in self._background_tasks:
            task.cancel()
        for task in self._background_tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.warning("Error stopping background task: %s", e)
        self._background_tasks.clear()
        
        # Disconnect clients
        try:
            await self._ws_client.disconnect()
        except Exception as e:
            logger.warning("Error disconnecting websocket client: %s", e)
        
        try:
            await self._http_client.aclose()
        except Exception as e:
            logger.warning("Error closing HTTP client: %s", e)
        
        logger.info("Session manager stopped")

    def register_ui(self) -> asyncio.Queue[ControllerEvent]:
        queue: asyncio.Queue[ControllerEvent] = asyncio.Queue(maxsize=4)
        self._ui_subscribers.append(queue)
        return queue

    def unregister_ui(self, queue: asyncio.Queue[ControllerEvent]) -> None:
        if queue in self._ui_subscribers:
            self._ui_subscribers.remove(queue)

    async def trigger_debug_session(self) -> None:
        """Manual session trigger for testing (bypasses ToF sensor)."""
        logger.info("Debug session trigger invoked")
        self._schedule_session()
    
    async def simulate_tof_trigger(self, *, triggered: bool, distance_mm: Optional[int] = None) -> None:
        """Simulate ToF sensor trigger for backend testing only."""
        if distance_mm is None:
            distance_mm = self.settings.tof_threshold_mm - 50 if triggered else self.settings.tof_threshold_mm + 50
        
        logger.info("Simulating ToF trigger (backend testing): triggered=%s, distance=%dmm", 
                   triggered, distance_mm)
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

    async def set_preview_enabled(self, enabled: bool) -> bool:
        result = await self._realsense.set_preview_enabled(enabled)
        if enabled:
            logger.info("Preview stream enabled")
        else:
            logger.info("Preview stream disabled")
        return result

    async def preview_frames(self) -> AsyncIterator[bytes]:
        """Stream preview frames with error handling."""
        try:
            async for frame in self._realsense.preview_stream():
                yield frame
        except Exception as e:
            logger.error("Preview stream error: %s", e)
            # Stream ends gracefully

    async def _broadcast(self, event: ControllerEvent) -> None:
        """Broadcast event to all UI subscribers with error handling."""
        for queue in list(self._ui_subscribers):
            try:
                if queue.full():
                    try:
                        queue.get_nowait()
                    except QueueEmpty:
                        pass
                queue.put_nowait(event)
            except Exception as e:
                logger.warning("Failed to broadcast event to subscriber: %s", e)

    async def _advance_phase(
        self,
        phase: SessionPhase,
        *,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        min_duration: float = 0.0,
    ) -> None:
        if min_duration > 0:
            elapsed = time.time() - self._phase_started_at
            if elapsed < min_duration:
                await asyncio.sleep(min_duration - elapsed)

        self._phase = phase
        self._phase_started_at = time.time()
        await self._broadcast(ControllerEvent(type="state", data=data or {}, phase=phase, error=error))

    async def _ensure_current_phase_duration(self, minimum_seconds: float) -> None:
        if minimum_seconds <= 0:
            return
        elapsed = time.time() - self._phase_started_at
        if elapsed < minimum_seconds:
            await asyncio.sleep(minimum_seconds - elapsed)

    async def _handle_tof_trigger(self, triggered: bool, distance: int) -> None:
        """Handle ToF sensor trigger events with error protection."""
        try:
            logger.info("ToF %s (distance=%dmm, phase=%s)", 
                       "TRIGGERED" if triggered else "released", distance, self.phase.value)
            self._current_session.latest_distance_mm = distance
            
            if triggered and self.phase == SessionPhase.IDLE:
                logger.info("Starting session from ToF trigger")
                self._schedule_session()
            elif not triggered and self.phase not in {SessionPhase.IDLE, SessionPhase.COMPLETE}:
                logger.warning("ToF sensor released mid-session - cancelling")
                if self._session_task:
                    self._session_task.cancel()
        except Exception as e:
            logger.exception("Error handling ToF trigger: %s", e)

    def _schedule_session(self) -> None:
        if self._session_task and not self._session_task.done():
            logger.info("Session already in progress; ignoring trigger")
            return
        self._session_task = asyncio.create_task(self._run_session(), name="controller-session")

    async def _run_session(self) -> None:
        """Run the full kiosk workflow with structured error handling."""
        try:
            token = await self._initialize_session()
            await self._connect_bridge(token)
            await self._await_app_ready()

            async with self._camera_session():
                await self._advance_phase(SessionPhase.HUMAN_DETECT)
                await self._collect_best_frame()

            await self._upload_frame()
            await self._wait_for_ack()
            logger.info("Session completed successfully")

        except asyncio.CancelledError:
            logger.info("Session cancelled by user or ToF reset")
            raise
        except SessionFlowError as exc:
            logger.error("Session failed: %s", exc)
            await self._advance_phase(SessionPhase.ERROR, error=exc.user_message, min_duration=5.0)
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.exception("Unexpected session error: %s", exc)
            await self._advance_phase(SessionPhase.ERROR, error=f"Unexpected error: {exc}", min_duration=5.0)
        finally:
            await self._cleanup_after_session()

    async def _initialize_session(self) -> str:
        await self._advance_phase(SessionPhase.PAIRING_REQUEST)
        token_info = await self._http_client.issue_token()
        if not token_info:
            raise SessionFlowError("Failed to get pairing token")

        token = token_info.get("token")
        if not token:
            raise SessionFlowError("Invalid token response from backend")

        expires_in = token_info.get("expires_in")
        qr_payload = self._build_qr_payload(token)
        self._current_session = SessionContext(
            token=token,
            expires_in=expires_in,
            issued_at=time.time(),
            metadata={"qr_payload": qr_payload},
        )
        self._last_metrics_ts = 0.0

        await self._advance_phase(
            SessionPhase.QR_DISPLAY,
            min_duration=3.0,
            data={
                "token": token,
                "expires_in": expires_in,
                "qr_payload": qr_payload,
            },
        )
        return token

    async def _connect_bridge(self, token: str) -> None:
        self._app_ready_event = asyncio.Event()
        self._ack_event = asyncio.Event()
        try:
            await self._ws_client.connect(token, self._handle_bridge_message)
        except Exception as exc:  # pragma: no cover - depends on network
            raise SessionFlowError("Bridge connection failed") from exc

        await self._advance_phase(SessionPhase.WAITING_ACTIVATION, min_duration=3.0)

    async def _await_app_ready(self) -> None:
        if not self._app_ready_event:
            raise RuntimeError("app_ready_event_not_initialized")
        timeout = self._token_timeout()
        logger.info("Waiting for app connection with timeout=%ss", timeout)
        try:
            await asyncio.wait_for(self._app_ready_event.wait(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise SessionFlowError("Mobile app connection timeout") from exc

    def _token_timeout(self) -> float:
        expires_in = self._current_session.expires_in
        if not expires_in:
            return 90.0
        return max(10.0, expires_in - 5.0)

    async def _collect_best_frame(self) -> None:
        await self._advance_phase(SessionPhase.STABILIZING, min_duration=3.0)

        max_attempts = 3
        attempt = 0
        frame_offset = 0
        best_bytes: Optional[bytes] = None
        best_score = -1.0
        best_result = None
        frame_count = 0
        alive_count = 0
        save_tasks = []

        while attempt < max_attempts and not best_bytes:
            attempt += 1
            results = await self._realsense.gather_results(self.settings.stability_seconds)
            if not results:
                logger.warning(
                    "RealSense gather_results returned no samples during stabilization (attempt=%s/%s)",
                    attempt,
                    max_attempts,
                )
                if attempt < max_attempts:
                    await asyncio.sleep(0.5)
                    continue
                raise RuntimeError("liveness_capture_failed")

            for idx, result in enumerate(results):
                frame_count += 1

                encoded = self._encode_jpeg(result.color_image)
                if encoded:
                    save_tasks.append(self._save_debug_frame(encoded, frame_offset + idx, result))

                if result.instant_alive or result.stable_alive:
                    alive_count += 1

                focus_score = self._compute_focus(result.color_image)
                normalized_focus = min(focus_score / 800.0, 1.0)
                stability = result.stability_score
                composite = (stability * 0.7) + (normalized_focus * 0.3)
                if result.stable_alive:
                    composite += 0.05

                if composite > best_score:
                    candidate = encoded or self._encode_jpeg(result.color_image)
                    if candidate:
                        best_bytes = candidate
                        best_score = composite
                        best_result = result

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
                                "instant_alive": result.instant_alive,
                                "stable_alive": result.stable_alive,
                                "depth_ok": result.depth_ok,
                                "screen_ok": result.screen_ok,
                                "movement_ok": result.movement_ok,
                            },
                        )
                    )

            frame_offset += len(results)

        logger.info(
            "Frame collection complete after %s attempt(s): %s total, %s passed liveness, best_score=%.3f",
            attempt,
            frame_count,
            alive_count,
            best_score,
        )

        if not best_bytes:
            raise RuntimeError("no_frames_captured")

        # Use best frame even if no frames passed liveness (relaxed requirement)
        if alive_count == 0:
            logger.warning(f"No frames passed liveness checks. Using best frame anyway (score={best_score:.3f})")

        self._current_session.best_frame_b64 = base64.b64encode(best_bytes).decode()

        # Save best frame and wait for all debug frames to complete
        await self._save_best_frame_to_captures(best_bytes, best_result)

        # Wait for all debug frame saves to complete (parallel)
        if save_tasks:
            await asyncio.gather(*save_tasks, return_exceptions=True)
            logger.info(f"Saved {len(save_tasks)} debug frames")

        await self._ensure_current_phase_duration(3.0)

    async def _upload_frame(self) -> None:
        await self._advance_phase(SessionPhase.UPLOADING, min_duration=3.0)
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
        await self._advance_phase(SessionPhase.WAITING_ACK, min_duration=3.0)

    async def _wait_for_ack(self) -> None:
        if not self._ack_event:
            raise RuntimeError("ack_event_not_initialized")
        try:
            await asyncio.wait_for(self._ack_event.wait(), timeout=120.0)
        except asyncio.TimeoutError as exc:
            raise SessionFlowError("Backend acknowledgment timeout") from exc
        await self._advance_phase(SessionPhase.COMPLETE, min_duration=3.0)

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat to UI clients."""
        try:
            while True:
                await asyncio.sleep(30)
                try:
                    await self._broadcast(ControllerEvent(type="heartbeat", data={}, phase=self.phase))
                except Exception as e:
                    logger.warning("Failed to send heartbeat: %s", e)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("Heartbeat loop crashed: %s", e)

    async def _handle_bridge_message(self, message: dict[str, Any]) -> None:
        """Handle messages from bridge websocket with full error protection."""
        try:
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
        
        except Exception as e:
            logger.exception("Error handling bridge message: %s", e)
            # Don't re-raise - keep session running if possible

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

    async def _save_debug_frame(self, frame_bytes: bytes, frame_idx: int, result) -> None:
        """Save debug frame with full liveness diagnostics."""
        try:
            from pathlib import Path
            import datetime
            import json
            
            platform_id = self._current_session.platform_id or "unknown"
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            
            # Create debug captures directory
            captures_dir = Path(__file__).resolve().parents[2] / "captures" / "debug" / platform_id
            
            # Run file I/O in executor to avoid blocking
            loop = asyncio.get_running_loop()
            
            def _write_files():
                captures_dir.mkdir(parents=True, exist_ok=True)
                
                base_filename = f"{timestamp}_frame{frame_idx:03d}"
                image_filepath = captures_dir / f"{base_filename}.jpg"
                metadata_filepath = captures_dir / f"{base_filename}.json"
                
                # Write frame
                with open(image_filepath, "wb") as f:
                    f.write(frame_bytes)
                
                # Save detailed metadata
                metadata = {
                    "frame_index": frame_idx,
                    "timestamp": timestamp,
                    "instant_alive": result.instant_alive,
                    "stable_alive": result.stable_alive,
                    "stability_score": result.stability_score,
                    "depth_ok": result.depth_ok,
                    "depth_info": result.depth_info,
                    "screen_ok": result.screen_ok,
                    "screen_info": result.screen_info,
                    "movement_ok": result.movement_ok,
                    "movement_info": result.movement_info,
                    "bbox": result.bbox,
                    "stats": result.stats,
                }
                
                with open(metadata_filepath, "w") as f:
                    json.dump(metadata, f, indent=2)
            
            await loop.run_in_executor(None, _write_files)
                
        except Exception:
            logger.exception("Failed to save debug frame")
    
    async def _save_best_frame_to_captures(self, frame_bytes: bytes, result=None) -> None:
        """Save the best frame to captures directory with platform ID filename."""
        try:
            from pathlib import Path
            import datetime
            import json
            
            # Get platform ID, fallback to timestamp if not available
            platform_id = self._current_session.platform_id or f"unknown_{int(time.time())}"
            captures_dir = Path(__file__).resolve().parents[2] / "captures"
            
            # Run file I/O in executor to avoid blocking
            loop = asyncio.get_running_loop()
            
            def _write_files():
                captures_dir.mkdir(parents=True, exist_ok=True)
                
                # Generate filename with timestamp and platform ID
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                base_filename = f"{timestamp}_{platform_id}_BEST"
                image_filepath = captures_dir / f"{base_filename}.jpg"
                metadata_filepath = captures_dir / f"{base_filename}.json"
                
                # Write the frame bytes to file
                with open(image_filepath, "wb") as f:
                    f.write(frame_bytes)
                
                # Save metadata alongside the image
                metadata = {
                    "timestamp": timestamp,
                    "platform_id": platform_id,
                    "session_token": self._current_session.token,
                    "capture_time": datetime.datetime.now().isoformat(),
                    "file_size_bytes": len(frame_bytes),
                    "is_best_frame": True,
                }
                
                if result:
                    metadata.update({
                        "instant_alive": result.instant_alive,
                        "stable_alive": result.stable_alive,
                        "stability_score": result.stability_score,
                        "depth_ok": result.depth_ok,
                        "screen_ok": result.screen_ok,
                        "movement_ok": result.movement_ok,
                    })
                
                with open(metadata_filepath, "w") as f:
                    json.dump(metadata, f, indent=2)
                
                return str(image_filepath)
            
            filepath = await loop.run_in_executor(None, _write_files)
            logger.info(f"Saved best frame to {filepath}")
            
        except Exception:
            logger.exception("Failed to save best frame to captures directory")
    @asynccontextmanager
    async def _camera_session(self) -> AsyncIterator[None]:
        try:
            await self._realsense.set_hardware_active(True, source="session")
            logger.info("Camera activated for biometric capture")
        except Exception as exc:
            raise SessionFlowError("Camera activation failed") from exc
        try:
            yield
        finally:
            try:
                await self._realsense.set_hardware_active(False, source="session")
                logger.info("Camera deactivated after session")
            except Exception as exc:
                logger.warning("Error deactivating camera: %s", exc)

    async def _cleanup_after_session(self) -> None:
        try:
            await self._ws_client.disconnect()
        except Exception as exc:
            logger.warning("Error disconnecting websocket: %s", exc)

        try:
            if self._phase == SessionPhase.ERROR:
                await self._ensure_current_phase_duration(5.0)
            elif self._phase == SessionPhase.COMPLETE:
                await self._ensure_current_phase_duration(3.0)

            await self._advance_phase(SessionPhase.IDLE)
        except Exception as exc:
            logger.warning("Error setting IDLE phase: %s", exc)
            self._phase = SessionPhase.IDLE
            self._phase_started_at = time.time()

        self._session_task = None
        self._app_ready_event = None
        self._ack_event = None
        self._current_session = SessionContext()
