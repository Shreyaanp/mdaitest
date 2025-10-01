"""Session orchestration for the mdai kiosk using the websocket bridge."""
from __future__ import annotations

import asyncio
from asyncio import QueueEmpty
import base64
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional
from urllib.parse import urlparse

import numpy as np

try:
    import cv2  # type: ignore
except ImportError:
    cv2 = None

from .backend.http_client import BridgeHttpClient
from .backend.ws_client import BackendWebSocketClient
from .config import Settings, get_settings
from .sensors.realsense import RealSenseService
from .sensors.tof import DistanceProvider, ToFSensor
from .sensors.tof_process import ToFReaderProcess
from .sensors.python_tof import PythonToFProvider
from .sensors.webcam_service import WebcamService
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


@dataclass
class WatchdogState:
    """Tracks watchdog actions within the current phase."""

    phase: SessionPhase = SessionPhase.IDLE
    soft_actions: int = 0
    bridge_attempted: bool = False
    reset_attempted: bool = False


class SessionFlowError(RuntimeError):
    """Raised when a recoverable session step fails."""

    def __init__(self, user_message: str, *, log_message: Optional[str] = None) -> None:
        super().__init__(log_message or user_message)
        self.user_message = user_message


class SessionManager:
    """Coordinates sensors, bridge comms, and UI state updates."""

    _WATCHDOG_LIMITS: Dict[SessionPhase, float] = {
        SessionPhase.PAIRING_REQUEST: 20.0,
        SessionPhase.HELLO_HUMAN: 10.0,
        SessionPhase.SCAN_PROMPT: 20.0,
        SessionPhase.QR_DISPLAY: 180.0,
        SessionPhase.HUMAN_DETECT: 25.0,
        SessionPhase.PROCESSING: 60.0,
        SessionPhase.COMPLETE: 15.0,
        SessionPhase.ERROR: 15.0,
    }
    _WATCHDOG_TICK_SECONDS: float = 2.0
    _WATCHDOG_SOFT_LIMIT: int = 2
    _WATCHDOG_BACKEND_TIMEOUT: float = 30.0

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

        # ToF sensor setup
        self._tof_process: Optional[ToFReaderProcess] = None
        self._python_tof: Optional[PythonToFProvider] = None
        
        if tof_distance_provider is None:
            # Check if we should use Python implementation
            use_python_tof = getattr(self.settings, 'tof_use_python', True)
            
            if use_python_tof:
                # Use Python I2C implementation
                logger.info("🐍 Using Python ToF implementation")
                self._python_tof = PythonToFProvider(
                    i2c_bus=self.settings.tof_i2c_bus,
                    i2c_address=self.settings.tof_i2c_address,
                    output_hz=self.settings.tof_output_hz,
                )
                tof_distance_provider = self._python_tof.get_distance
            elif not self.settings.tof_reader_binary:
                logger.warning("🧪 TEST MODE: ToF binary not configured - using mock ToF")
                tof_distance_provider = self._mock_tof_distance
            elif not Path(self.settings.tof_reader_binary).exists():
                logger.warning(f"🧪 TEST MODE: ToF binary not found at {self.settings.tof_reader_binary} - using mock ToF")
                tof_distance_provider = self._mock_tof_distance
            else:
                # Use C++ binary implementation (fallback)
                logger.info("⚙️ Using C++ ToF implementation")
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
        # Production-ready thresholds - VERY lenient for real-world use
        threshold_overrides = {
            # DEPTH CHECKS - Ultra-lenient to accept most real faces
            "max_horizontal_asymmetry_m": 0.30,  # Allow high facial asymmetry
            "min_depth_range_m": 0.005,  # Accept very flat profiles (60% reduction from original)
            "min_depth_stdev_m": 0.002,  # Accept minimal variation (67% reduction)
            "min_center_prominence_m": 0.0005,  # Barely any nose prominence needed (75% reduction)
            "min_center_prominence_ratio": 0.01,  # Ultra-low ratio (was 0.02, values are ~0.012-0.019)
            "min_samples": 40,  # Accept fewer depth points (50% reduction)
            
            # IR CHECKS - Relaxed for different skin tones/lighting
            "ir_std_min": 2.5,  # Very lenient IR variance (was 4.0, 38% reduction)
            "ir_saturation_fraction_max": 0.4,  # Allow more bright areas (was 0.25, 60% increase)
            "ir_dark_fraction_max": 0.4,  # Allow more dark areas (was 0.25, 60% increase)
            
            # MOVEMENT CHECKS - Minimal movement required
            "min_eye_change": 0.003,  # Tiny eye movements (was 0.005, 40% reduction)
            "min_mouth_change": 0.005,  # Tiny mouth movements (was 0.008, 38% reduction)
            "min_nose_depth_change_m": 0.001,  # Minimal head tilt (was 0.002, 50% reduction)
            "min_center_shift_px": 0.5,  # Half-pixel shift (was 1.0, 50% reduction)
            "movement_window_s": 2.0,  # Faster detection window (was 2.5, 20% reduction)
            "min_movement_samples": 2,  # Only 2 samples needed (was 2, unchanged)
            
            # GENERAL
            "max_depth_m": 4,  # Allow people farther away (was 2.0, 25% increase)
        }
        # Preserve RealSense enablement even if ToF binary missing (test mode still allowed)
        force_test_mode = not self.settings.tof_reader_binary or not Path(self.settings.tof_reader_binary).exists()
        enable_realsense = self.settings.realsense_enable_hardware

        if force_test_mode and enable_realsense:
            logger.warning("🧪 TEST MODE: ToF binary missing - continuing with RealSense enabled")
        
        self._realsense = RealSenseService(
            enable_hardware=enable_realsense,
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
        self._debug_metrics_task: Optional[asyncio.Task[None]] = None
        self._watchdog_task: Optional[asyncio.Task[None]] = None
        self._watchdog_state = WatchdogState()
        self._last_backend_message_ts: float = time.time()
        self._last_phase_payload: Dict[str, Any] | None = None
        self._last_phase_error: Optional[str] = None

    @property
    def phase(self) -> SessionPhase:
        return self._phase

    async def start(self) -> None:
        logger.info("Starting session manager")
        try:
            if self._tof_process:
                await self._tof_process.start()
            if self._python_tof:
                await self._python_tof.start()
            await self._tof.start()
        except Exception as e:
            logger.error("Failed to start ToF sensor: %s", e)
            logger.warning("ToF sensor not available - use debug endpoints for testing")
            # Continue anyway - ToF can be simulated via debug endpoints
        
        try:
            await self._realsense.start()
        except Exception as e:
            logger.exception("Failed to start RealSense service: %s", e)
            # Continue anyway - RealSense might not be available yet

        self._background_tasks.append(asyncio.create_task(self._heartbeat_loop(), name="controller-heartbeat"))
        if not self._watchdog_task or self._watchdog_task.done():
            self._watchdog_task = asyncio.create_task(self._watchdog_loop(), name="controller-watchdog")
        logger.info("Session manager started in IDLE state (camera inactive)")

    async def stop(self) -> None:
        logger.info("Stopping session manager")

        # Stop ToF sensor
        try:
            await self._tof.stop()
            if self._tof_process:
                await self._tof_process.stop()
            if self._python_tof:
                await self._python_tof.stop()
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

        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.warning("Error stopping watchdog task: %s", e)
        self._watchdog_task = None

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
            # Start continuous metrics broadcasting for debug mode
            if not self._debug_metrics_task or self._debug_metrics_task.done():
                self._debug_metrics_task = asyncio.create_task(
                    self._debug_metrics_loop(), 
                    name="debug-metrics-broadcaster"
                )
        else:
            logger.info("Preview stream disabled")
            # Stop metrics broadcasting
            if self._debug_metrics_task and not self._debug_metrics_task.done():
                self._debug_metrics_task.cancel()
                try:
                    await self._debug_metrics_task
                except asyncio.CancelledError:
                    pass
                self._debug_metrics_task = None
        return result
    
    async def _debug_metrics_loop(self) -> None:
        """Continuously broadcast liveness metrics for debug preview."""
        try:
            logger.info("🔍 Debug metrics broadcaster started")
            result_queue: asyncio.Queue = asyncio.Queue(maxsize=2)
            self._realsense._result_subscribers.append(result_queue)
            
            metrics_count = 0
            try:
                while True:
                    try:
                        result = await asyncio.wait_for(result_queue.get(), timeout=1.0)
                        
                        if result:
                            metrics_count += 1
                            # Broadcast metrics to UI
                            await self._broadcast(
                                ControllerEvent(
                                    type="metrics",
                                    phase=self._phase,
                                    data={
                                        "stability": result.stability_score,
                                        "focus": 0.0,  # Can add focus calculation if needed
                                        "composite": result.stability_score,
                                        "instant_alive": result.instant_alive,
                                        "stable_alive": result.stable_alive,
                                        "depth_ok": result.depth_ok,
                                        "screen_ok": result.screen_ok,
                                        "movement_ok": result.movement_ok,
                                    },
                                )
                            )
                            
                            if metrics_count % 30 == 0:  # Log every 30 metrics (~2 seconds)
                                logger.info(f"🔍 Broadcast {metrics_count} metrics: stability={result.stability_score:.3f}, alive={result.instant_alive}")
                    except asyncio.TimeoutError:
                        if metrics_count == 0:
                            logger.warning("🔍 No liveness results received (camera may not be active)")
                        continue
                        
            finally:
                self._realsense._result_subscribers.remove(result_queue)
                logger.info("🔍 Debug metrics broadcaster stopped")
                
        except asyncio.CancelledError:
            logger.info("🔍 Debug metrics broadcaster cancelled")
            raise
        except Exception as e:
            logger.exception("🔍 Debug metrics broadcaster error: %s", e)

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
        self._last_phase_payload = data or {}
        self._last_phase_error = error
        self._reset_watchdog_state(phase)
        await self._broadcast(ControllerEvent(type="state", data=data or {}, phase=phase, error=error))

    async def _ensure_current_phase_duration(self, minimum_seconds: float) -> None:
        if minimum_seconds <= 0:
            return
        elapsed = time.time() - self._phase_started_at
        if elapsed < minimum_seconds:
            await asyncio.sleep(minimum_seconds - elapsed)

    def _reset_watchdog_state(self, phase: SessionPhase) -> None:
        """Reset watchdog tracking when phase changes or session completes."""
        self._watchdog_state = WatchdogState(phase=phase)

    async def _mock_tof_distance(self) -> Optional[int]:
        """Mock ToF distance provider for testing without hardware."""
        # Returns very far distance (idle) - actual triggers come from /debug/mock-tof endpoint
        return 1000
    
    async def _handle_tof_trigger(self, triggered: bool, distance: int) -> None:
        """
        Handle ToF sensor trigger events.
        
        Logic:
        - Distance ≤ threshold in IDLE → Start session
        - Distance > threshold for debounce duration in active session → Cancel (user walked away)
        - Monitoring applies to ALL phases except IDLE, COMPLETE, ERROR
        """
        try:
            threshold = self.settings.tof_threshold_mm
            debounce_seconds = self.settings.tof_debounce_ms / 1000.0
            
            logger.debug(f"ToF: distance={distance}mm, phase={self.phase.value}, threshold={threshold}mm")
            self._current_session.latest_distance_mm = distance
            
            # Behavior depends on current phase
            current_phase = self.phase
            
            # IDLE state: Start session if user is close
            if current_phase == SessionPhase.IDLE:
                if distance <= threshold:
                    logger.info(f"👆 ToF triggered (distance={distance}mm ≤ {threshold}mm) - starting session")
                    self._schedule_session()
                return
            
            # COMPLETE/ERROR states: Don't monitor distance (session ending anyway)
            if current_phase in {SessionPhase.COMPLETE, SessionPhase.ERROR}:
                return
            
            # Active session states: Monitor distance and cancel if user walks away
            # Applies to: PAIRING_REQUEST, HELLO_HUMAN, SCAN_PROMPT, QR_DISPLAY, HUMAN_DETECT, PROCESSING
            if distance > threshold:
                # User is too far - check if they've been away for debounce duration
                if not hasattr(self, '_tof_far_since'):
                    self._tof_far_since = time.time()
                    logger.info(f"⚠️ User moved away (distance={distance}mm > {threshold}mm) - will cancel in {debounce_seconds}s...")
                    
                    # Schedule delayed check (for mock ToF that doesn't poll continuously)
                    async def delayed_cancel():
                        await asyncio.sleep(debounce_seconds)
                        if hasattr(self, '_tof_far_since'):
                            time_away = time.time() - self._tof_far_since
                            if time_away >= debounce_seconds:
                                logger.warning(f"🚶 User walked away for {time_away:.1f}s - cancelling session")
                                if self._session_task and not self._session_task.done():
                                    self._session_task.cancel()
                                delattr(self, '_tof_far_since')
                    
                    asyncio.create_task(delayed_cancel())
                else:
                    time_away = time.time() - self._tof_far_since
                    if time_away >= debounce_seconds:
                        logger.warning(f"🚶 User walked away for {time_away:.1f}s - cancelling session")
                        if self._session_task and not self._session_task.done():
                            self._session_task.cancel()
                        delattr(self, '_tof_far_since')
            else:
                # User is close - reset away timer
                if hasattr(self, '_tof_far_since'):
                    logger.info(f"✅ User returned (distance={distance}mm) - cancel aborted")
                    delattr(self, '_tof_far_since')
                    
        except Exception as e:
            logger.exception(f"Error handling ToF trigger: {e}")

    def _schedule_session(self) -> None:
        if self._session_task and not self._session_task.done():
            logger.info("Session already in progress; ignoring trigger")
            return
        self._session_task = asyncio.create_task(self._run_session(), name="controller-session")

    async def _run_session(self) -> None:
        """
        Main session flow - clean and easy to follow.
        
        Flow:
        1. Request pairing token (1.2s with exit animation)
        2. Show "Hello Human" welcome screen (2s)
        3. Show "Scan this to get started" prompt (3s)
        4. Show QR code and wait for mobile app (indefinite)
        5. Validate human with camera (3.5s, need ≥10 passing frames)
        6. Process and upload best frame (3-15s)
        7. Show complete screen (3s)
        8. Return to idle
        """
        try:
            # Step 1: Request token from backend (PAIRING_REQUEST - 1.2s)
            token = await self._request_pairing_token()
            
            # Step 2: Show welcome screen (HELLO_HUMAN - 2s)
            await self._show_hello_human()
            
            # Step 3: Show scan prompt (SCAN_PROMPT - 3s)
            await self._show_scan_prompt()
            
            # Step 3: Show QR and wait for mobile connection (QR_DISPLAY - indefinite)
            await self._show_qr_and_connect(token)
            await self._wait_for_mobile_app()
            
            # Step 4: Validate human face (HUMAN_DETECT - 3.5s exactly)
            best_frame = await self._validate_human_presence()
            
            # Step 5: Process and upload (PROCESSING - 3-15s)
            await self._process_and_upload(best_frame)
            
            # Step 6: Show success (COMPLETE - 3s)
            await self._show_complete()
            
            logger.info("✅ Session completed successfully")

        except asyncio.CancelledError:
            logger.info("⚠️ Session cancelled (user walked away)")
            # Go directly to IDLE with entry animation (no error screen)
            await self._advance_phase(SessionPhase.IDLE)
            # Don't re-raise - handled gracefully
            
        except SessionFlowError as exc:
            logger.error("❌ Session failed: %s", exc)
            await self._show_error(exc.user_message)
            
        except Exception as exc:
            logger.exception("❌ Unexpected session error: %s", exc)
            await self._show_error("Please try again")
            
        finally:
            await self._cleanup_session()

    # ============================================================
    # SESSION FLOW METHODS - Clean & Easy to Understand
    # ============================================================
    
    async def _request_pairing_token(self) -> str:
        """
        Step 1: Request pairing token from backend.
        Duration: 1.2s (matches TV bars exit animation)
        """
        await self._advance_phase(SessionPhase.PAIRING_REQUEST, min_duration=1.2)
        
        # Request token from backend
        token_info = await self._http_client.issue_token()
        if not token_info or not token_info.get("token"):
            raise SessionFlowError("Failed to get pairing token")
        
        # Store session info
        token = token_info["token"]
        expires_in = token_info.get("expires_in")
        self._current_session = SessionContext(
            token=token,
            expires_in=expires_in,
            issued_at=time.time(),
        )
        
        logger.info(f"📱 Token issued: {token[:12]}... (expires in {expires_in}s)")
        return token
    
    async def _show_hello_human(self) -> None:
        """
        Step 2: Show "Hello Human" welcome screen.
        Duration: 3s
        """
        await self._advance_phase(SessionPhase.HELLO_HUMAN, min_duration=3.0)
        logger.info("👋 Showing hello human screen (3s)")
    
    async def _show_scan_prompt(self) -> None:
        """
        Step 3: Show "Scan this to get started" prompt.
        Duration: 1.5s
        Uses HandjetMessage component with text message.
        """
        await self._advance_phase(
            SessionPhase.SCAN_PROMPT, 
            min_duration=1.5,
            data={"message": "Scan this to get started"}
        )
        logger.info("📱 Showing scan prompt screen")
    
    async def _show_qr_and_connect(self, token: str) -> None:
        """
        Step 3: Show QR code and connect websocket bridge.
        Duration: Indefinite (waits for mobile app)
        """
        # Build QR payload
        qr_payload = self._build_qr_payload(token)
        self._current_session.metadata = {"qr_payload": qr_payload}
        
        # Initialize events for mobile app connection
        self._app_ready_event = asyncio.Event()
        self._ack_event = asyncio.Event()
        
        # Connect to websocket bridge
        try:
            await self._ws_client.connect(token, self._handle_bridge_message)
            self._last_backend_message_ts = time.time()
        except Exception as exc:
            raise SessionFlowError("Failed to connect to bridge") from exc
        
        # Show QR code
        await self._advance_phase(
            SessionPhase.QR_DISPLAY,
            data={
                "token": token,
                "expires_in": self._current_session.expires_in,
                "qr_payload": qr_payload,
            },
        )
        logger.info("📱 QR code displayed - waiting for mobile app")
    
    async def _wait_for_mobile_app(self) -> None:
        """
        Wait for mobile app to connect and send platform_id.
        Timeout based on token expiry.
        """
        if not self._app_ready_event:
            raise RuntimeError("App ready event not initialized")
        
        timeout = self._token_timeout()
        logger.info(f"⏳ Waiting for mobile app connection (timeout={timeout}s)")
        
        try:
            await asyncio.wait_for(self._app_ready_event.wait(), timeout=timeout)
            logger.info(f"✅ Mobile app connected: {self._current_session.platform_id}")
        except asyncio.TimeoutError as exc:
            raise SessionFlowError("Mobile app did not connect in time") from exc
    
    async def _validate_human_presence(self) -> bytes:
        """
        Step 4: Validate human face with camera.
        Duration: Exactly 3.5 seconds
        Requirements: Need at least 10 passing frames (depth check only)
        
        Returns: Best frame as JPEG bytes
        """
        VALIDATION_DURATION = 3.5  # Strict 3.5 seconds
        MIN_PASSING_FRAMES = 10    # Need at least 10 good frames
        
        await self._advance_phase(SessionPhase.HUMAN_DETECT)
        logger.info(f"📸 Starting human validation ({VALIDATION_DURATION}s, need ≥{MIN_PASSING_FRAMES} frames)")
        
        # Production mode requires RealSense hardware
        if not self._realsense.enable_hardware:
            logger.error("RealSense hardware disabled - cannot perform production validation")
            raise SessionFlowError(
                user_message="camera unavailable, please contact support",
                log_message="RealSense hardware disabled"
            )

        # Activate RealSense camera for production use
        try:
            await self._realsense.set_hardware_active(True, source="validation")
        except Exception as exc:
            logger.exception("RealSense activation failed: %s", exc)
            try:
                await self._realsense.set_hardware_active(False, source="validation")
            except Exception as release_exc:
                logger.warning("Failed to release RealSense after activation error: %s", release_exc)
            raise SessionFlowError(
                user_message="camera unavailable, please contact support",
                log_message="RealSense activation failed"
            )
        
        try:
            # Collect frames for exactly 3.5 seconds
            start_time = time.time()
            passing_frames = []
            best_frame = None
            best_score = -1.0
            total_frames = 0
            face_detected_count = 0  # Track frames with face detected
            
            while time.time() - start_time < VALIDATION_DURATION:
                # Get a single result from the camera
                results = await self._realsense.gather_results(0.1)  # 100ms window
                
                for result in results:
                    total_frames += 1
                    
                    # Track face detection
                    if result.face_detected:
                        face_detected_count += 1
                    
                    # Check if frame passes liveness (depth-only check = hybrid approach)
                    if result.depth_ok:
                        passing_frames.append(result)
                        
                        # Update progress for Eye of Horus progress bar
                        progress = min(1.0, len(passing_frames) / MIN_PASSING_FRAMES)
                        self._realsense.set_validation_progress(progress)
                        
                        # Also update webcam service if available (for debug testing)
                        if hasattr(self, '_webcam_service'):
                            self._webcam_service.set_validation_progress(progress)
                        
                        # Calculate quality score
                        focus_score = self._compute_focus(result.color_image)
                        normalized_focus = min(focus_score / 800.0, 1.0)
                        composite_score = (result.stability_score * 0.7) + (normalized_focus * 0.3)
                        
                        # Track best frame
                        if composite_score > best_score:
                            best_score = composite_score
                            best_frame = result
                            
                        logger.debug(f"✅ Frame {total_frames}: PASS (depth_ok=True, score={composite_score:.3f})")
                    else:
                        logger.debug(f"❌ Frame {total_frames}: FAIL (depth_ok=False)")
            
            # Reset progress after validation
            self._realsense.set_validation_progress(0.0)
            if hasattr(self, '_webcam_service'):
                self._webcam_service.set_validation_progress(0.0)
            
            # Validation complete - check results
            logger.info(
                f"📊 Validation complete: {len(passing_frames)}/{total_frames} frames passed, "
                f"faces_detected={face_detected_count}/{total_frames}, best_score={best_score:.3f}"
            )
            
            # Specific error messages based on what went wrong
            
            # Scenario A: Never detected a face (entire 3.5s)
            if face_detected_count == 0:
                raise SessionFlowError(
                    user_message="sorry I am confused, you dont seem to have facial features"
                )
            
            # Scenario C: Face detected briefly but lost
            if face_detected_count > 0 and face_detected_count < total_frames * 0.3:
                raise SessionFlowError(
                    user_message="lost tracking, please stay in frame"
                )
            
            # Scenario B: Face detected but failed liveness checks
            if len(passing_frames) < MIN_PASSING_FRAMES:
                raise SessionFlowError(
                    user_message="validation failed, please try again"
                )
            
            # Check if we have a best frame
            if not best_frame:
                raise SessionFlowError(user_message="please try again")
            
            # Encode best frame as JPEG
            best_bytes = self._encode_jpeg(best_frame.color_image)
            if not best_bytes:
                raise SessionFlowError("Failed to encode frame", user_message="Please try again")
            
            # Save best frame to captures folder (ONLY the best one)
            await self._save_best_frame_to_captures(best_bytes, best_frame)
            
            logger.info(f"✅ Human validation SUCCESS: {len(passing_frames)} passing frames, score={best_score:.3f}")
            return best_bytes
            
        finally:
            # Always deactivate camera
            try:
                await self._realsense.set_hardware_active(False, source="validation")
            except Exception as exc:
                logger.warning(f"Error deactivating camera: {exc}")
    
    async def _process_and_upload(self, best_frame_bytes: bytes) -> None:
        """
        Step 5: Upload best frame and wait for backend processing.
        Duration: Exactly 3 seconds (for kiosk UX consistency)
        """
        await self._advance_phase(SessionPhase.PROCESSING)
        logger.info("🚀 Starting processing phase")
        
        # Encode frame as base64
        frame_b64 = base64.b64encode(best_frame_bytes).decode()
        
        # Upload to backend via websocket
        if not self._current_session.platform_id:
            raise SessionFlowError("Platform ID missing", user_message="Please try again")
        
        payload = {
            "type": "to_backend",
            "data": {
                "platform_id": self._current_session.platform_id,
                "image_base64": frame_b64,
            },
        }
        
        # Try to upload (non-blocking for test mode)
        try:
            await self._ws_client.send(payload)
            logger.info(f"📤 Frame uploaded ({len(frame_b64)} chars base64)")
        except Exception as e:
            logger.warning(f"Upload failed (test mode OK): {e}")
        
        # Wait for backend acknowledgment OR timeout after 3s (kiosk needs predictable timing)
        if not self._ack_event:
            # Test mode: just wait 3s
            logger.info("⚠️ Test mode: No ACK event, waiting 3s...")
            await asyncio.sleep(3.0)
        else:
            try:
                # Production: wait for ACK but timeout after 3s for UX
                await asyncio.wait_for(self._ack_event.wait(), timeout=3.0)
                logger.info("✅ Backend acknowledgment received")
            except asyncio.TimeoutError:
                # Timeout is OK - continue after 3s for consistent UX
                logger.warning("⚠️ Backend ACK timeout (3s) - continuing anyway")
                
        # Processing phase shown for exactly 3s total
        await self._ensure_current_phase_duration(3.0)
    
    async def _mock_validate_with_webcam(self) -> bytes:
        """
        TEST MODE: Mock validation using webcam (no RealSense depth).
        Simulates the validation process for testing UI flow.
        Can be controlled via scenario parameters.
        """
        VALIDATION_DURATION = 3.5
        MIN_PASSING_FRAMES = 10
        TARGET_FPS = 30
        EXPECTED_TOTAL_FRAMES = int(VALIDATION_DURATION * TARGET_FPS)  # ~105 frames
        
        # Check if scenario parameters exist
        simulate_no_face = self._current_session.metadata.get('simulate_no_face', False)
        simulate_lost_tracking = self._current_session.metadata.get('simulate_lost_tracking', False)
        
        start_time = time.time()
        face_detected_count = 0
        passing_frames_count = 0
        total_frames = 0
        
        logger.info(f"🧪 Mock validation: duration={VALIDATION_DURATION}s, expected_frames={EXPECTED_TOTAL_FRAMES}")
        if simulate_no_face:
            logger.warning("🧪 Simulating: NO FACE scenario")
        if simulate_lost_tracking:
            logger.warning("🧪 Simulating: LOST TRACKING scenario")
        
        # Simulate frame collection matching real timing
        while time.time() - start_time < VALIDATION_DURATION:
            total_frames += 1
            elapsed = time.time() - start_time
            
            # Simulate different scenarios
            if simulate_no_face:
                # Never detect face
                face_detected = False
            elif simulate_lost_tracking:
                # Detect face briefly then lose it (only first 30% of frames)
                face_detected = total_frames < (EXPECTED_TOTAL_FRAMES * 0.3)
            else:
                # Normal: detect face after initial frames
                face_detected = total_frames > 5
            
            if face_detected:
                face_detected_count += 1
                passing_frames_count += 1
            
            # Update progress based on TIME elapsed (fills over full 3.5s)
            # This ensures progress bar takes entire duration regardless of frame count
            time_progress = elapsed / VALIDATION_DURATION
            frame_progress = passing_frames_count / MIN_PASSING_FRAMES if face_detected_count > 0 else 0
            
            # Use minimum of time and frame progress (whichever is slower)
            # This ensures progress never exceeds actual validation time
            progress = min(time_progress, frame_progress, 1.0)
            
            if hasattr(self, '_webcam_service'):
                self._webcam_service.set_validation_progress(progress)
            
            # Log progress every 30 frames (~1 second)
            if total_frames % 30 == 0:
                logger.debug(f"🧪 Progress: {int(progress*100)}% | Time: {elapsed:.1f}s/{VALIDATION_DURATION}s | Frames: {passing_frames_count}/{MIN_PASSING_FRAMES}")
            
            # Sleep to maintain ~30 FPS (realistic timing)
            await asyncio.sleep(1.0 / TARGET_FPS)
        
        # Reset progress
        if hasattr(self, '_webcam_service'):
            self._webcam_service.set_validation_progress(0.0)
        
        logger.info(f"🧪 Mock validation complete: {passing_frames_count}/{total_frames} frames passed, {face_detected_count} with face")
        
        # Apply same error logic as real validation
        if face_detected_count == 0:
            raise SessionFlowError(
                user_message="sorry I am confused, you dont seem to have facial features"
            )
        
        if face_detected_count > 0 and face_detected_count < total_frames * 0.3:
            raise SessionFlowError(
                user_message="lost tracking, please stay in frame"
            )
        
        if passing_frames_count < MIN_PASSING_FRAMES:
            raise SessionFlowError(
                user_message="validation failed, please try again"
            )
        
        # Create a mock JPEG frame (black frame with success text)
        mock_image = np.zeros((480, 640, 3), dtype=np.uint8)
        if cv2:
            cv2.putText(mock_image, "MOCK VALIDATION SUCCESS", (150, 240),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
            ret, enc = cv2.imencode(".jpg", mock_image, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if ret:
                return enc.tobytes()
        
        # Minimal fallback JPEG (1x1 black pixel)
        return base64.b64decode(
            b"/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD5/ooooA//2Q=="
        )
    
    async def _show_complete(self) -> None:
        """
        Step 6: Show success screen.
        Duration: 3s
        """
        await self._advance_phase(SessionPhase.COMPLETE, min_duration=3.0)
        logger.info("🎉 Session complete")
    
    async def _show_error(self, message: str) -> None:
        """
        Show error screen and return to idle.
        Duration: 3s
        """
        await self._advance_phase(SessionPhase.ERROR, error=message, min_duration=3.0)
        logger.error(f"❌ Error: {message}")
    
    async def _cleanup_session(self) -> None:
        """
        Clean up after session (success or failure).
        Returns to IDLE with entry animation (TV bars falling).
        """
        # Close camera if still active
        try:
            if self._realsense.enable_hardware:
                await self._realsense.set_hardware_active(False, source="validation")
                logger.info("📷 Camera deactivated in cleanup")
        except Exception as exc:
            logger.warning(f"Error deactivating camera: {exc}")
        
        try:
            # Disconnect websocket
            await self._ws_client.disconnect()
        except Exception as exc:
            logger.warning(f"Error disconnecting websocket: {exc}")
        
        # Ensure we're in idle state with entry animation
        try:
            # Only wait for error/complete duration if we're in those phases
            if self._phase in {SessionPhase.ERROR, SessionPhase.COMPLETE}:
                await self._ensure_current_phase_duration(3.0)
            
            # Return to idle (UI will show entry animation) - only if not already IDLE
            if self._phase != SessionPhase.IDLE:
                await self._advance_phase(SessionPhase.IDLE)
            
        except Exception as exc:
            logger.warning(f"Error setting idle phase: {exc}")
            self._phase = SessionPhase.IDLE
            self._phase_started_at = time.time()
        
        # Reset session state
        self._session_task = None
        self._app_ready_event = None
        self._ack_event = None
        self._current_session = SessionContext()
        
        # Reset ToF distance tracking
        if hasattr(self, '_tof_far_since'):
            delattr(self, '_tof_far_since')
        
        logger.info("🔄 Session cleaned up, returning to idle")

    async def _connect_bridge(self, token: str) -> None:
        self._app_ready_event = asyncio.Event()
        self._ack_event = asyncio.Event()
        try:
            await self._ws_client.connect(token, self._handle_bridge_message)
            self._last_backend_message_ts = time.time()
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

    async def _watchdog_loop(self) -> None:
        """Monitor session flow and recover from stuck states."""
        logger.info("Watchdog loop started")
        try:
            while True:
                await asyncio.sleep(self._WATCHDOG_TICK_SECONDS)
                try:
                    await self._watchdog_tick()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.exception("Watchdog tick error: %s", exc)
        except asyncio.CancelledError:
            logger.info("Watchdog loop cancelled")
            raise
        except Exception as exc:
            logger.exception("Watchdog loop crashed: %s", exc)

    async def _watchdog_tick(self) -> None:
        phase = self._phase
        if phase == SessionPhase.IDLE:
            if self._watchdog_state.phase != SessionPhase.IDLE:
                self._reset_watchdog_state(SessionPhase.IDLE)
            return

        limit = self._WATCHDOG_LIMITS.get(phase)
        if limit is None:
            return

        elapsed = time.time() - self._phase_started_at
        if elapsed < limit:
            return

        if self._watchdog_state.phase != phase:
            self._reset_watchdog_state(phase)

        backend_stale = (time.time() - self._last_backend_message_ts) > self._WATCHDOG_BACKEND_TIMEOUT
        if backend_stale and not self._watchdog_state.bridge_attempted:
            self._watchdog_state.bridge_attempted = True
            success = await self._attempt_bridge_reconnect()
            await self._broadcast_watchdog(
                "bridge_reconnect",
                status="success" if success else "failed",
                elapsed=round(elapsed, 1),
            )
            if success:
                self._watchdog_state.soft_actions += 1
                return

        if self._watchdog_state.soft_actions < self._WATCHDOG_SOFT_LIMIT:
            self._watchdog_state.soft_actions += 1
            await self._broadcast_watchdog("resync", elapsed=round(elapsed, 1))
            await self._rebroadcast_phase_state()
            return

        if not self._watchdog_state.reset_attempted:
            self._watchdog_state.reset_attempted = True
            await self._broadcast_watchdog("reset_session", elapsed=round(elapsed, 1))
            await self._reset_stuck_session(reason=f"watchdog_{phase.value}")
            return

        if phase != SessionPhase.IDLE:
            await self._force_idle("watchdog_fallback")

    async def _broadcast_watchdog(
        self,
        action: str,
        *,
        phase: SessionPhase | None = None,
        **data: Any,
    ) -> None:
        await self._broadcast(
            ControllerEvent(
                type="watchdog",
                phase=phase or self._phase,
                data={"action": action, **data},
            )
        )

    async def _rebroadcast_phase_state(self) -> None:
        await self._broadcast(
            ControllerEvent(
                type="state",
                phase=self._phase,
                data=self._last_phase_payload or {},
                error=self._last_phase_error,
            )
        )

    async def _attempt_bridge_reconnect(self) -> bool:
        token = self._current_session.token
        if not token:
            logger.debug("Watchdog skip bridge reconnect: no token available")
            return False

        try:
            await self._ws_client.disconnect()
        except Exception as exc:
            logger.debug("Watchdog bridge disconnect warning: %s", exc)

        try:
            await self._ws_client.connect(token, self._handle_bridge_message)
            self._last_backend_message_ts = time.time()
            logger.info("Watchdog reconnected bridge websocket")
            return True
        except Exception as exc:
            logger.warning("Watchdog failed to reconnect bridge websocket: %s", exc)
            return False

    async def _reset_stuck_session(self, *, reason: str) -> None:
        task = self._session_task
        if task and not task.done():
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Watchdog session cancel timeout")
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.warning("Watchdog session cancel error: %s", exc)

        if self._phase != SessionPhase.IDLE:
            await self._force_idle(reason)

    async def _force_idle(self, reason: str) -> None:
        self._phase = SessionPhase.IDLE
        self._phase_started_at = time.time()
        self._current_session = SessionContext()
        self._last_phase_payload = {}
        self._last_phase_error = None
        self._reset_watchdog_state(SessionPhase.IDLE)
        await self._broadcast_watchdog("forced_idle", reason=reason, phase=self._phase)
        await self._broadcast(ControllerEvent(type="state", data={}, phase=self._phase))

    async def _handle_bridge_message(self, message: dict[str, Any]) -> None:
        """Handle messages from bridge websocket with full error protection."""
        try:
            self._last_backend_message_ts = time.time()
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

        self._session_task = None
        self._app_ready_event = None
        self._ack_event = None
        self._current_session = SessionContext()
