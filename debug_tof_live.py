#!/usr/bin/env python3
"""
Live ToF debugging tool - reads distance continuously
Use this to verify sensor is working properly
"""

import sys
import time
import signal

try:
    import smbus
except ImportError:
    print("❌ smbus not installed")
    sys.exit(1)

class ToFDebugger:
    def __init__(self, bus_num=1, address=0x29):
        self.bus_num = bus_num
        self.address = address
        self.bus = None
        self.running = True
        
        # Setup signal handler for clean exit
        signal.signal(signal.SIGINT, self.signal_handler)
        
    def signal_handler(self, sig, frame):
        print("\n\n🛑 Stopping...")
        self.running = False
    
    def init_sensor(self):
        """Initialize VL53L0X sensor."""
        print(f"🔧 Initializing VL53L0X on I2C bus {self.bus_num}, address 0x{self.address:02x}")
        
        try:
            self.bus = smbus.SMBus(self.bus_num)
            
            # Clear any stuck state
            try:
                self.bus.write_byte_data(self.address, 0x00, 0x00)
                time.sleep(0.05)
            except:
                pass
            
            # Check model ID
            model_id = self.bus.read_byte_data(self.address, 0xC0)
            if model_id != 0xEE:
                print(f"❌ Wrong model ID: 0x{model_id:02x} (expected 0xEE)")
                return False
            
            revision_id = self.bus.read_byte_data(self.address, 0xC2)
            print(f"✅ VL53L0X found: Model 0x{model_id:02x}, Revision 0x{revision_id:02x}")
            
            # Initialize sensor
            self.bus.write_byte_data(self.address, 0x88, 0x00)
            self.bus.write_byte_data(self.address, 0x80, 0x01)
            self.bus.write_byte_data(self.address, 0xFF, 0x01)
            self.bus.write_byte_data(self.address, 0x00, 0x00)
            
            current_val = self.bus.read_byte_data(self.address, 0x91)
            self.bus.write_byte_data(self.address, 0x91, current_val | 0x3C)
            
            self.bus.write_byte_data(self.address, 0x00, 0x01)
            self.bus.write_byte_data(self.address, 0xFF, 0x00)
            self.bus.write_byte_data(self.address, 0x80, 0x00)
            
            # Start continuous mode
            self.bus.write_byte_data(self.address, 0x00, 0x02)
            time.sleep(0.1)
            
            print("✅ Sensor initialized in continuous mode")
            return True
            
        except Exception as e:
            print(f"❌ Initialization failed: {e}")
            return False
    
    def read_distance(self):
        """Read distance from sensor."""
        try:
            distance_high = self.bus.read_byte_data(self.address, 0x1E)
            distance_low = self.bus.read_byte_data(self.address, 0x1F)
            distance = (distance_high << 8) | distance_low
            
            if distance == 0 or distance > 8000:
                return None
            
            return distance
            
        except Exception as e:
            print(f"❌ Read error: {e}")
            return None
    
    def run(self):
        """Main loop - continuously read and display distance."""
        print("\n" + "=" * 70)
        print("📏 Live ToF Distance Readings")
        print("=" * 70)
        print("Press Ctrl+C to stop\n")
        
        if not self.init_sensor():
            return
        
        print(f"{'Time':<12} {'Distance':<12} {'Status':<30} {'Trigger?':<10}")
        print("-" * 70)
        
        threshold = 500  # Same as backend
        read_count = 0
        error_count = 0
        last_distance = None
        
        try:
            while self.running:
                timestamp = time.strftime("%H:%M:%S")
                distance = self.read_distance()
                
                if distance is not None:
                    read_count += 1
                    
                    # Determine status
                    if distance < threshold:
                        status = "🚨 WOULD TRIGGER SESSION"
                        trigger = "YES"
                    else:
                        status = "✅ Normal (idle)"
                        trigger = "No"
                    
                    # Show distance change
                    if last_distance is not None:
                        delta = distance - last_distance
                        if abs(delta) > 50:
                            status += f" (Δ{delta:+d}mm)"
                    
                    print(f"{timestamp:<12} {distance:>5}mm      {status:<30} {trigger:<10}")
                    last_distance = distance
                    
                else:
                    error_count += 1
                    print(f"{timestamp:<12} {'---':>5}       ❌ No reading                    {'---':<10}")
                
                time.sleep(0.1)  # 10Hz like backend
                
        except KeyboardInterrupt:
            pass
        
        finally:
            print("\n" + "=" * 70)
            print(f"📊 Statistics:")
            print(f"   Total reads: {read_count}")
            print(f"   Errors: {error_count}")
            if read_count > 0:
                success_rate = (read_count / (read_count + error_count)) * 100
                print(f"   Success rate: {success_rate:.1f}%")
            print("=" * 70)
            
            if self.bus:
                try:
                    self.bus.write_byte_data(self.address, 0x00, 0x00)  # Stop continuous mode
                    self.bus.close()
                    print("✅ Sensor stopped cleanly")
                except:
                    pass

def main():
    debugger = ToFDebugger(bus_num=1, address=0x29)
    debugger.run()

if __name__ == "__main__":
    main()


