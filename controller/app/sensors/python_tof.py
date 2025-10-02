"""Pure Python VL53L0X ToF sensor implementation."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import smbus2 as smbus
    SMBUS_AVAILABLE = True
except ImportError:
    SMBUS_AVAILABLE = False
    logger.warning("smbus2 not available - install with: pip install smbus2")


class PythonVL53L0X:
    """Pure Python VL53L0X ToF sensor driver with async interface."""
    
    def __init__(self, i2c_bus: int = 1, i2c_address: int = 0x29):
        self.i2c_bus = i2c_bus
        self.i2c_address = i2c_address
        self.bus = None
        self.initialized = False
        self._last_distance: Optional[int] = None
        self._init_lock = asyncio.Lock()
        
    async def start(self) -> None:
        """Initialize the ToF sensor (async interface matching ToFReaderProcess)."""
        if not SMBUS_AVAILABLE:
            raise RuntimeError("smbus library not available")
            
        async with self._init_lock:
            if self.initialized:
                return
                
            try:
                # Initialize SMBus in a thread to avoid blocking
                await asyncio.get_event_loop().run_in_executor(None, self._init_sensor)
                logger.info("Python ToF sensor initialized on I2C bus %d, address 0x%02x", 
                           self.i2c_bus, self.i2c_address)
                self.initialized = True
            except Exception as e:
                logger.error("Failed to initialize Python ToF sensor: %s", e)
                raise
    
    def _init_sensor(self) -> None:
        """Initialize the sensor (blocking I/O) with retry logic."""
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.info("Initializing VL53L0X (attempt %d/%d)...", attempt, max_retries)
                
                # Open I2C bus
                self.bus = smbus.SMBus(self.i2c_bus)
                
                # Try to clear any stuck state first
                try:
                    self.bus.write_byte_data(self.i2c_address, 0x00, 0x00)
                    time.sleep(0.05)
                except:
                    pass  # Ignore errors on initial clear
                
                # Check if sensor is present
                model_id = self.bus.read_byte_data(self.i2c_address, 0xC0)
                if model_id != 0xEE:
                    raise RuntimeError(f"VL53L0X not found. Expected model ID 0xEE, got 0x{model_id:02x}")
                
                revision_id = self.bus.read_byte_data(self.i2c_address, 0xC2)
                logger.info("VL53L0X found: Model ID 0x%02x, Revision ID 0x%02x", model_id, revision_id)
                
                # Basic initialization sequence
                self.bus.write_byte_data(self.i2c_address, 0x88, 0x00)
                self.bus.write_byte_data(self.i2c_address, 0x80, 0x01)
                self.bus.write_byte_data(self.i2c_address, 0xFF, 0x01)
                self.bus.write_byte_data(self.i2c_address, 0x00, 0x00)
                
                current_val = self.bus.read_byte_data(self.i2c_address, 0x91)
                self.bus.write_byte_data(self.i2c_address, 0x91, current_val | 0x3C)
                
                self.bus.write_byte_data(self.i2c_address, 0x00, 0x01)
                self.bus.write_byte_data(self.i2c_address, 0xFF, 0x00)
                self.bus.write_byte_data(self.i2c_address, 0x80, 0x00)
                
                # Set to continuous ranging mode
                self.bus.write_byte_data(self.i2c_address, 0x00, 0x02)
                
                time.sleep(0.1)  # 100ms delay for first measurement
                
                # Test read to verify it's working
                distance_high = self.bus.read_byte_data(self.i2c_address, 0x1E)
                distance_low = self.bus.read_byte_data(self.i2c_address, 0x1F)
                test_distance = (distance_high << 8) | distance_low
                
                if 0 < test_distance < 8000:
                    logger.info("✅ VL53L0X initialization successful (test reading: %dmm)", test_distance)
                    return  # Success!
                else:
                    logger.warning("Test reading out of range: %dmm, retrying...", test_distance)
                    raise RuntimeError(f"Test reading failed: {test_distance}mm")
                
            except Exception as e:
                logger.warning("Init attempt %d/%d failed: %s", attempt, max_retries, e)
                
                # Clean up before retry
                if self.bus:
                    try:
                        self.bus.close()
                    except:
                        pass
                    self.bus = None
                
                if attempt < max_retries:
                    logger.info("Retrying in %.1fs...", retry_delay)
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # Exponential backoff
                else:
                    # Final attempt failed
                    raise RuntimeError(f"Failed to initialize VL53L0X after {max_retries} attempts: {e}")
    
    async def stop(self) -> None:
        """Stop the ToF sensor (async interface matching ToFReaderProcess)."""
        if self.bus:
            try:
                # Stop continuous mode and close bus in executor
                await asyncio.get_event_loop().run_in_executor(None, self._stop_sensor)
            except Exception as e:
                logger.warning("Error stopping ToF sensor: %s", e)
        self.initialized = False
        logger.info("Python ToF sensor stopped")
    
    def _stop_sensor(self) -> None:
        """Stop the sensor (blocking I/O)."""
        try:
            self.bus.write_byte_data(self.i2c_address, 0x00, 0x00)  # Stop continuous mode
        except:
            pass
        self.bus.close()
        self.bus = None
    
    async def get_distance(self) -> Optional[int]:
        """Get distance measurement (async interface matching ToFReaderProcess)."""
        if not self.initialized or not self.bus:
            # Try to reinitialize if needed
            try:
                await self.start()
            except Exception as e:
                logger.warning("Failed to reinitialize ToF sensor: %s", e)
                return None
        
        try:
            # Read distance in executor to avoid blocking
            distance = await asyncio.get_event_loop().run_in_executor(None, self._read_distance_blocking)
            self._last_distance = distance
            return distance
        except Exception as e:
            logger.warning("Error reading ToF distance: %s", e)
            return None
    
    def _read_distance_blocking(self) -> Optional[int]:
        """Read distance measurement (blocking I/O) with noise filtering."""
        try:
            # In continuous mode, sensor continuously updates result registers
            # Add a small delay to ensure sensor has updated registers (VL53L0X measurement cycle ~33ms)
            time.sleep(0.04)  # 40ms delay to sync with sensor measurement cycle
            
            # Read the distance registers directly
            distance_high = self.bus.read_byte_data(self.i2c_address, 0x1E)
            distance_low = self.bus.read_byte_data(self.i2c_address, 0x1F)
            distance = (distance_high << 8) | distance_low
            
            # Filter out invalid readings
            if distance == 0 or distance > 8000:
                return None
            
            # Filter out obvious noise/glitches (sudden jumps to very low values)
            # VL53L0X commonly glitches to 20mm - filter these out
            if distance < 50 and self._last_distance and self._last_distance > 100:
                # Glitch detected: reading dropped from >100mm to <50mm
                return self._last_distance  # Return previous stable reading
            
            # Apply median filtering for stable readings (smooth out small variations)
            if self._last_distance:
                # If readings are within 100mm, apply light smoothing
                if abs(distance - self._last_distance) < 100:
                    distance = int((distance + self._last_distance) / 2)
                
            return distance
            
        except Exception as e:
            logger.debug("I2C read error: %s", e)
            return None


class PythonToFProvider:
    """Async ToF provider that matches the ToFReaderProcess interface."""
    
    def __init__(
        self,
        *,
        i2c_bus: str = "/dev/i2c-1",
        i2c_address: int = 0x29,
        output_hz: int = 10,
        **kwargs  # Accept other args for compatibility but ignore them
    ):
        # Parse bus number from path like "/dev/i2c-1"
        if i2c_bus.startswith("/dev/i2c-"):
            bus_number = int(i2c_bus.split("-")[-1])
        else:
            bus_number = 1
            
        self.output_hz = output_hz
        self._sensor = PythonVL53L0X(i2c_bus=bus_number, i2c_address=i2c_address)
        self._last_log_time = 0.0
        
    async def start(self) -> None:
        """Start the ToF sensor."""
        await self._sensor.start()
        logger.info("Python ToF provider started @ %dHz", self.output_hz)
    
    async def stop(self) -> None:
        """Stop the ToF sensor."""
        await self._sensor.stop()
        logger.info("Python ToF provider stopped")
    
    async def get_distance(self) -> Optional[int]:
        """Get distance measurement with optional debug logging."""
        distance = await self._sensor.get_distance()
        
        # Optional debug logging (similar to what we added to tof_process.py)
        current_time = time.time()
        if current_time - self._last_log_time > 1.0:  # Log at most once per second
            if distance is not None:
                threshold_status = "≤ 500mm (TRIGGER)" if distance <= 500 else "> 500mm (no trigger)"
                logger.info("📏 Python ToF reading: %dmm %s", distance, threshold_status)
            else:
                logger.debug("📏 Python ToF: No reading available")
            self._last_log_time = current_time
            
        return distance
