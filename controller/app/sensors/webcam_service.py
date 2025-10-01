"""
Simple Webcam Service for Debug Preview
Uses laptop camera instead of RealSense hardware
"""

from __future__ import annotations

import asyncio
from asyncio import QueueEmpty
import base64
import logging
import time
from typing import AsyncIterator, Optional
from dataclasses import dataclass

import numpy as np

# Optional deps
try:
    import cv2  # type: ignore
except Exception:
    cv2 = None

try:
    import mediapipe as mp  # type: ignore
except Exception:
    mp = None


logger = logging.getLogger("webcam_service")

_PLACEHOLDER_JPEG = base64.b64decode(
    b"/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD5/ooooA//2Q=="
)


@dataclass
class WebcamFrame:
    """Simple frame data from webcam."""
    timestamp: float
    color_image: np.ndarray
    face_detected: bool
    # Simulate liveness for testing (no real depth sensor)
    depth_ok: bool = True  # Always pass depth check in test mode
    stability_score: float = 0.8  # Mock stability


class WebcamService:
    """Simple webcam service using laptop camera."""
    
    def __init__(self, camera_id: int = 0):
        self.camera_id = camera_id
        self.enable_hardware = bool(cv2 is not None and mp is not None)
        self._cap: Optional[cv2.VideoCapture] = None
        self._face_detector = None
        self._face_mesh = None
        self._active = False
        self._preview_mode: str = "eye_tracking"  # Eye of Horus by default (matches realsense.py)
        self._validation_progress: float = 0.0  # For progress bar
        self._lock = asyncio.Lock()
        self._preview_subscribers: list[asyncio.Queue[bytes]] = []
        self._loop_task: Optional[asyncio.Task[None]] = None
        self._stop_event = asyncio.Event()
        
        # Eye tracking visualization renderer (lazy init)
        self._eye_renderer = None
    
    async def start(self) -> None:
        """Start the webcam service."""
        if self._loop_task:
            return
        if not self.enable_hardware:
            logger.warning("OpenCV or MediaPipe not available - webcam disabled")
            return
        
        self._stop_event.clear()
        self._loop_task = asyncio.create_task(self._preview_loop(), name="webcam-preview-loop")
        logger.info("Webcam service started")
    
    async def stop(self) -> None:
        """Stop the webcam service."""
        if not self._loop_task:
            return
        
        self._stop_event.set()
        await self._loop_task
        self._loop_task = None
        
        async with self._lock:
            await self._deactivate_locked()
        
        logger.info("Webcam service stopped")
    
    async def _activate_locked(self) -> None:
        """Activate webcam (must be called with lock held)."""
        if self._active:
            return
        
        logger.info(f"Opening webcam (camera_id={self.camera_id})")
        
        # Open webcam
        self._cap = cv2.VideoCapture(self.camera_id)
        if not self._cap.isOpened():
            logger.error(f"Failed to open webcam {self.camera_id}")
            self._cap = None
            return
        
        # Set resolution
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self._cap.set(cv2.CAP_PROP_FPS, 30)
        
        # Initialize MediaPipe
        self._face_detector = mp.solutions.face_detection.FaceDetection(
            model_selection=0,
            min_detection_confidence=0.5
        )
        
        self._face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        self._active = True
        logger.info("Webcam activated successfully")
    
    async def _deactivate_locked(self) -> None:
        """Deactivate webcam (must be called with lock held)."""
        if not self._active:
            return
        
        logger.info("Closing webcam")
        
        if self._cap:
            self._cap.release()
            self._cap = None
        
        if self._face_detector:
            self._face_detector.close()
            self._face_detector = None
        
        if self._face_mesh:
            self._face_mesh.close()
            self._face_mesh = None
        
        self._active = False
        logger.info("Webcam deactivated")
    
    async def set_active(self, active: bool) -> None:
        """Activate or deactivate webcam."""
        async with self._lock:
            if active:
                await self._activate_locked()
            else:
                await self._deactivate_locked()
    
    def _capture_frame(self) -> Optional[WebcamFrame]:
        """Capture a frame from webcam with simulated RealSense depth processing load."""
        if not self._cap or not self._cap.isOpened():
            return None
        
        ret, frame = self._cap.read()
        if not ret or frame is None:
            return None
        
        # SIMULATE REALSENSE DEPTH PROCESSING LOAD
        # This mimics the computational cost of:
        # - Depth frame alignment
        # - Depth statistics computation
        # - IR anti-spoofing checks
        # - Movement detection
        self._simulate_depth_processing(frame)
        
        # Convert BGR to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Detect face
        face_detected = False
        if self._face_detector:
            try:
                result = self._face_detector.process(rgb_frame)
                face_detected = bool(result and result.detections)
            except Exception as e:
                logger.warning(f"Face detection error: {e}")
        
        return WebcamFrame(
            timestamp=time.time(),
            color_image=frame,  # Keep as BGR for display
            face_detected=face_detected
        )
    
    def _simulate_depth_processing(self, frame: np.ndarray):
        """
        Simulate computational load of RealSense depth processing.
        This adds ~10-15ms of CPU work per frame to match real hardware.
        """
        h, w = frame.shape[:2]
        
        # Simulate depth alignment (matrix operations)
        _ = cv2.GaussianBlur(frame, (5, 5), 0)
        
        # Simulate depth statistics computation (mean, std, median)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _ = np.mean(gray)
        _ = np.std(gray)
        _ = np.median(gray[h//4:3*h//4, w//4:3*w//4])
        
        # Simulate movement detection (optical flow-like computation)
        edges = cv2.Canny(gray, 50, 150)
        _ = np.sum(edges) / (h * w)
        
        # Simulate IR variance check (Sobel operations)
        _ = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        _ = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    
    async def _preview_loop(self) -> None:
        """Main preview loop."""
        try:
            while not self._stop_event.is_set():
                if self._active and self._cap:
                    # Capture frame
                    loop = asyncio.get_running_loop()
                    frame_data = await loop.run_in_executor(None, self._capture_frame)
                    
                    # Serialize and broadcast
                    frame_bytes = self._serialize_frame(frame_data)
                    self._broadcast_frame(frame_bytes)
                    
                    # Small delay to control frame rate
                    await asyncio.sleep(0.033)  # ~30 FPS
                else:
                    # Inactive - send placeholder
                    self._broadcast_frame(self._placeholder_frame())
                    await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Webcam preview loop crashed")
        finally:
            self._stop_event.clear()
            logger.info("Webcam preview loop stopped")
    
    def _serialize_frame(self, frame_data: Optional[WebcamFrame]) -> bytes:
        """Serialize frame to JPEG."""
        if frame_data is None or cv2 is None:
            return self._placeholder_frame()
        
        try:
            # Check preview mode
            if self._preview_mode == "eye_tracking":
                frame = self._create_eye_tracking_frame(frame_data)
            else:
                frame = self._create_normal_frame(frame_data)
            
            # Encode as JPEG
            ret, enc = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            return enc.tobytes() if ret else self._placeholder_frame()
        except Exception as e:
            logger.warning(f"Frame serialization error: {e}")
            return self._placeholder_frame()
    
    def _create_normal_frame(self, frame_data: WebcamFrame) -> np.ndarray:
        """Create normal preview frame (actual camera feed with overlay)."""
        frame = frame_data.color_image.copy()
        
        # Add face detection indicator
        if frame_data.face_detected:
            text = "Face Detected"
            color = (0, 255, 0)  # Green
        else:
            text = "No Face"
            color = (0, 0, 255)  # Red
        
        # Draw status text
        cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                   1.0, color, 2, cv2.LINE_AA)
        
        # Draw webcam indicator
        cv2.putText(frame, "Laptop Camera", (10, frame.shape[0] - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        
        return frame
    
    def _create_eye_tracking_frame(self, frame_data: WebcamFrame) -> np.ndarray:
        """Create Eye of Horus tracking visualization."""
        try:
            # Lazy init eye renderer
            if self._eye_renderer is None:
                from .eye_tracking_viz import EyeOfHorusRenderer
                self._eye_renderer = EyeOfHorusRenderer(width=640, height=480)
            
            # Run face mesh if face detected
            if not frame_data.face_detected:
                return self._eye_renderer.render(None, progress=self._validation_progress)
            
            # Convert BGR to RGB for MediaPipe
            rgb_image = cv2.cvtColor(frame_data.color_image, cv2.COLOR_BGR2RGB)
            mesh_result = self._face_mesh.process(rgb_image)
            
            # Render using the mesh result with progress
            return self._eye_renderer.render_from_mesh_result(mesh_result, 640, 480, self._validation_progress)
            
        except Exception as e:
            logger.warning(f"Eye tracking visualization error: {e}")
            # Fallback to normal frame
            return self._create_normal_frame(frame_data)
    
    def _placeholder_frame(self) -> bytes:
        """Return placeholder frame."""
        return _PLACEHOLDER_JPEG
    
    def _broadcast_frame(self, frame: bytes) -> None:
        """Broadcast frame to all subscribers."""
        for q in list(self._preview_subscribers):
            if q.full():
                try:
                    q.get_nowait()
                except QueueEmpty:
                    pass
            q.put_nowait(frame)
    
    async def preview_stream(self) -> AsyncIterator[bytes]:
        """Stream preview frames."""
        q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=2)
        self._preview_subscribers.append(q)
        try:
            while True:
                frame = await q.get()
                yield frame
        finally:
            self._preview_subscribers.remove(q)
    
    async def set_preview_mode(self, mode: str) -> str:
        """Set preview rendering mode: 'normal' or 'eye_tracking'."""
        if mode not in ("normal", "eye_tracking"):
            logger.warning(f"Invalid preview mode: {mode}, using 'normal'")
            mode = "normal"
        self._preview_mode = mode
        logger.info(f"Webcam preview mode set to: {mode}")
        return self._preview_mode
    
    def get_preview_mode(self) -> str:
        """Get current preview rendering mode."""
        return self._preview_mode
    
    def set_validation_progress(self, progress: float) -> None:
        """Set validation progress for progress bar display (0.0 to 1.0)."""
        self._validation_progress = max(0.0, min(1.0, progress))

