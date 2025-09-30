"""ZeroMQ subscriber for C++ RGB frame grabber.

This replaces the blocking RealSense capture in Python with a fast async subscriber
that receives pre-encoded JPEG frames from the C++ grabber process.
"""
import asyncio
import logging
import struct
from typing import Optional, AsyncIterator
import numpy as np

try:
    import zmq
    import zmq.asyncio
except ImportError:
    zmq = None

try:
    import cv2
except ImportError:
    cv2 = None

logger = logging.getLogger(__name__)


class RGBFrame:
    """RGB frame from C++ grabber."""
    
    def __init__(self, jpeg_data: bytes, width: int, height: int, 
                 timestamp_ms: int, frame_number: int):
        self.jpeg_data = jpeg_data
        self.width = width
        self.height = height
        self.timestamp_ms = timestamp_ms
        self.frame_number = frame_number
        self._decoded_image: Optional[np.ndarray] = None
    
    def decode(self) -> Optional[np.ndarray]:
        """Decode JPEG to numpy array (lazy)."""
        if self._decoded_image is not None:
            return self._decoded_image
        
        if cv2 is None:
            return None
        
        try:
            # Decode JPEG bytes to numpy array
            nparr = np.frombuffer(self.jpeg_data, np.uint8)
            self._decoded_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return self._decoded_image
        except Exception as e:
            logger.error(f"Failed to decode JPEG: {e}")
            return None
    
    @property
    def image(self) -> Optional[np.ndarray]:
        """Get decoded image (BGR format)."""
        return self.decode()


class RGBSubscriber:
    """Async subscriber for RGB frames from C++ grabber.
    
    This is a lightweight, non-blocking way to get camera frames without
    running heavy RealSense/MediaPipe processing in the Python event loop.
    """
    
    def __init__(self, endpoint: str = "ipc:///tmp/mdai_rgb_frames"):
        if zmq is None:
            raise RuntimeError("pyzmq is required for RGBSubscriber")
        
        self.endpoint = endpoint
        self._context: Optional[zmq.asyncio.Context] = None
        self._socket: Optional[zmq.asyncio.Socket] = None
        self._running = False
        self._latest_frame: Optional[RGBFrame] = None
        self._frame_count = 0
        self._dropped_count = 0
    
    async def start(self):
        """Start subscribing to frames."""
        if self._running:
            return
        
        self._context = zmq.asyncio.Context()
        self._socket = self._context.socket(zmq.SUB)
        
        # Subscribe to all messages
        self._socket.setsockopt(zmq.SUBSCRIBE, b'')
        
        # Set high water mark (drop old frames if we're slow)
        self._socket.setsockopt(zmq.RCVHWM, 2)
        
        # Connect to publisher
        self._socket.connect(self.endpoint)
        
        self._running = True
        logger.info(f"RGB subscriber connected to {self.endpoint}")
    
    async def stop(self):
        """Stop subscribing."""
        if not self._running:
            return
        
        self._running = False
        
        if self._socket:
            self._socket.close()
            self._socket = None
        
        if self._context:
            self._context.term()
            self._context = None
        
        logger.info(f"RGB subscriber stopped. Received {self._frame_count} frames")
    
    async def receive_frame(self) -> Optional[RGBFrame]:
        """Receive next frame (non-blocking).
        
        Returns None if no frame available or on error.
        """
        if not self._running or not self._socket:
            return None
        
        try:
            # Non-blocking receive
            message = await self._socket.recv(flags=zmq.NOBLOCK)
            return self._parse_frame(message)
        
        except zmq.Again:
            # No message available
            return None
        
        except Exception as e:
            logger.error(f"Error receiving frame: {e}")
            return None
    
    def _parse_frame(self, message: bytes) -> Optional[RGBFrame]:
        """Parse frame from C++ format."""
        try:
            # Header: [4 bytes: width] [4 bytes: height] [8 bytes: timestamp] 
            #         [4 bytes: frame_number] [N bytes: JPEG data]
            
            if len(message) < 20:  # Minimum header size
                return None
            
            width, height, timestamp_ms, frame_number = struct.unpack(
                '<IIQi', message[:20]
            )
            
            jpeg_data = message[20:]
            
            self._frame_count += 1
            
            frame = RGBFrame(
                jpeg_data=jpeg_data,
                width=width,
                height=height,
                timestamp_ms=timestamp_ms,
                frame_number=frame_number
            )
            
            self._latest_frame = frame
            return frame
        
        except Exception as e:
            logger.error(f"Error parsing frame: {e}")
            return None
    
    async def stream_frames(self, max_fps: float = 30.0) -> AsyncIterator[RGBFrame]:
        """Stream frames as async iterator.
        
        Args:
            max_fps: Maximum frame rate to yield (throttle if needed)
        """
        if not self._running:
            await self.start()
        
        frame_interval = 1.0 / max_fps if max_fps > 0 else 0
        
        while self._running:
            frame = await self.receive_frame()
            
            if frame:
                yield frame
            
            # Small sleep to avoid busy-wait and throttle FPS
            await asyncio.sleep(frame_interval)
    
    def get_latest_frame(self) -> Optional[RGBFrame]:
        """Get most recent frame (synchronous)."""
        return self._latest_frame
    
    @property
    def frame_count(self) -> int:
        """Total frames received."""
        return self._frame_count
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()


# Example usage
async def example():
    """Example: stream and display frames."""
    subscriber = RGBSubscriber()
    
    async with subscriber:
        async for frame in subscriber.stream_frames(max_fps=10):
            print(f"Frame {frame.frame_number}: {frame.width}x{frame.height}, "
                  f"{len(frame.jpeg_data)} bytes")
            
            # Decode and display (optional)
            if cv2:
                image = frame.decode()
                if image is not None:
                    cv2.imshow("RGB Feed", image)
                    if cv2.waitKey(1) & 0xFF == 27:  # ESC
                        break


if __name__ == "__main__":
    asyncio.run(example())
