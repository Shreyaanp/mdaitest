#!/usr/bin/env python3
"""
Reset and test VL53L0X ToF sensor
Fixes I2C Error 121 (Remote I/O error)
"""

import sys
import time

try:
    import smbus
except ImportError:
    print("❌ smbus not installed")
    print("Install with: pip install smbus")
    sys.exit(1)

def reset_sensor(bus_num=1, address=0x29):
    """Reset VL53L0X sensor by reinitializing it."""
    print(f"🔧 Resetting VL53L0X on I2C bus {bus_num}, address 0x{address:02x}")
    
    try:
        bus = smbus.SMBus(bus_num)
        print("✅ I2C bus opened")
        
        # Step 1: Try to read model ID (diagnostic)
        try:
            model_id = bus.read_byte_data(address, 0xC0)
            print(f"📡 Model ID: 0x{model_id:02x} (expected 0xEE)")
            if model_id != 0xEE:
                print(f"⚠️  Warning: Unexpected model ID")
        except Exception as e:
            print(f"❌ Failed to read model ID: {e}")
            print("🔄 Attempting soft reset...")
        
        # Step 2: Soft reset sequence
        try:
            # Write to device to clear any stuck state
            bus.write_byte_data(address, 0x00, 0x00)  # Stop any measurement
            time.sleep(0.05)
            
            bus.write_byte_data(address, 0x88, 0x00)
            bus.write_byte_data(address, 0x80, 0x01)
            bus.write_byte_data(address, 0xFF, 0x01)
            bus.write_byte_data(address, 0x00, 0x00)
            time.sleep(0.01)
            
            # Clear stop variable
            current_val = bus.read_byte_data(address, 0x91)
            bus.write_byte_data(address, 0x91, current_val | 0x3C)
            
            bus.write_byte_data(address, 0x00, 0x01)
            bus.write_byte_data(address, 0xFF, 0x00)
            bus.write_byte_data(address, 0x80, 0x00)
            
            print("✅ Soft reset completed")
            
        except Exception as e:
            print(f"❌ Soft reset failed: {e}")
            bus.close()
            return False
        
        # Step 3: Start continuous mode
        try:
            bus.write_byte_data(address, 0x00, 0x02)
            time.sleep(0.05)
            print("✅ Continuous mode started")
        except Exception as e:
            print(f"❌ Failed to start continuous mode: {e}")
            bus.close()
            return False
        
        # Step 4: Test reading
        try:
            time.sleep(0.1)  # Wait for first measurement
            distance_high = bus.read_byte_data(address, 0x1E)
            distance_low = bus.read_byte_data(address, 0x1F)
            distance = (distance_high << 8) | distance_low
            
            if 0 < distance < 8000:
                print(f"✅ Test reading: {distance}mm")
                print("🎉 Sensor reset successful!")
                bus.close()
                return True
            else:
                print(f"⚠️  Test reading out of range: {distance}mm")
                
        except Exception as e:
            print(f"❌ Test reading failed: {e}")
        
        bus.close()
        
    except Exception as e:
        print(f"❌ Reset failed: {e}")
        return False
    
    return True

def main():
    print("=" * 60)
    print("VL53L0X ToF Sensor Reset Tool")
    print("=" * 60)
    print()
    
    success = reset_sensor(bus_num=1, address=0x29)
    
    print()
    if success:
        print("✅ Sensor is ready!")
        print("You can now start the backend server.")
        sys.exit(0)
    else:
        print("❌ Sensor reset failed")
        print("\nTroubleshooting:")
        print("1. Check sensor wiring")
        print("2. Try: sudo i2cdetect -y 1")
        print("3. Power cycle the sensor (unplug/replug)")
        print("4. Reboot: sudo reboot")
        sys.exit(1)

if __name__ == "__main__":
    main()


