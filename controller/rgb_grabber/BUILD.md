# Building RGB Grabber for Jetson Nano (Ubuntu 18.04 Bionic)

## Prerequisites

### Install dependencies on Jetson Nano

```bash
# Update package list
sudo apt-get update

# Install build tools
sudo apt-get install -y \
    build-essential \
    cmake \
    pkg-config \
    git

# Install libjpeg-turbo (faster JPEG encoding)
sudo apt-get install -y libjpeg-turbo8-dev

# Install ZeroMQ
sudo apt-get install -y libzmq3-dev

# Install RealSense SDK (if not already installed)
# Follow: https://github.com/IntelRealSense/librealsense/blob/master/doc/distribution_linux.md
sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-key F6E65AC044F831AC80A06380C8B3A55A6F3EFCDE
sudo add-apt-repository "deb https://librealsense.intel.com/Debian/apt-repo $(lsb_release -cs) main"
sudo apt-get update
sudo apt-get install -y librealsense2-dev
```

## Build Instructions

### Option 1: Standard Build (Host)

```bash
cd /home/ichiro/Desktop/mercleapp/mDai/mdaitest/controller/rgb_grabber

# Create build directory
mkdir -p build
cd build

# Configure with CMake
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CXX_FLAGS="-march=armv8-a -mtune=cortex-a57"

# Build
make -j4

# Install (optional)
sudo make install

# Test
./rgb-grabber --help
```

### Option 2: Docker Build (Python 12 Container)

```bash
# Build inside Docker container
docker run --rm \
    --device=/dev/video0 \
    --device=/dev/video1 \
    -v $(pwd):/workspace \
    -w /workspace \
    ubuntu:20.04 \
    bash -c "
        apt-get update && \
        apt-get install -y build-essential cmake libjpeg-turbo8-dev libzmq3-dev librealsense2-dev && \
        mkdir -p build && cd build && \
        cmake .. -DCMAKE_BUILD_TYPE=Release && \
        make -j4
    "
```

## Running

### Start RGB Grabber (runs continuously)

```bash
# Basic usage
./rgb-grabber

# Custom resolution and FPS
./rgb-grabber --width 640 --height 480 --fps 30 --quality 85

# Custom ZMQ endpoint
./rgb-grabber --endpoint ipc:///tmp/mdai_rgb_frames
```

### Run as systemd service (auto-start on boot)

```bash
# Create service file
sudo tee /etc/systemd/system/mdai-rgb-grabber.service << EOF
[Unit]
Description=mDAI RGB Frame Grabber
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/home/ichiro/Desktop/mercleapp/mDai/mdaitest/controller/rgb_grabber/build
ExecStart=/home/ichiro/Desktop/mercleapp/mDai/mdaitest/controller/rgb_grabber/build/rgb-grabber
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable mdai-rgb-grabber
sudo systemctl start mdai-rgb-grabber

# Check status
sudo systemctl status mdai-rgb-grabber

# View logs
journalctl -u mdai-rgb-grabber -f
```

## Testing ZMQ Connection

```bash
# Install ZMQ tools
sudo apt-get install -y libzmq3-dev

# Test subscriber (Python)
python3 << EOF
import zmq
import struct

context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.setsockopt(zmq.SUBSCRIBE, b'')
socket.connect('ipc:///tmp/mdai_rgb_frames')

print("Waiting for frames...")
while True:
    message = socket.recv()
    width, height, timestamp, frame_num = struct.unpack('<IIQi', message[:20])
    jpeg_size = len(message) - 20
    print(f"Frame {frame_num}: {width}x{height}, {jpeg_size} bytes, ts={timestamp}")
EOF
```

## Performance Tuning for Jetson Nano

### Enable maximum performance mode

```bash
# Set to max performance (10W mode)
sudo nvpmodel -m 0

# Set CPU/GPU to max frequency
sudo jetson_clocks
```

### Optimize JPEG encoding

The code uses `JDCT_FASTEST` for real-time encoding. If you need better quality:

Edit `src/rgb_grabber.cpp` line 102:
```cpp
cinfo.dct_method = JDCT_ISLOW;  // Better quality, slower
```

### Monitor Performance

```bash
# Watch CPU/GPU usage
sudo tegrastats

# Monitor frame grabber
watch -n 1 'journalctl -u mdai-rgb-grabber -n 20 --no-pager'
```

## Troubleshooting

### Issue: "RealSense error: No device connected"

```bash
# Check USB connection
lsusb | grep Intel

# Check RealSense firmware
rs-enumerate-devices

# Update firmware if needed
realsense-viewer
```

### Issue: "Failed to bind ZMQ socket"

```bash
# Remove stale socket
rm -f /tmp/mdai_rgb_frames

# Check if another process is using it
lsof /tmp/mdai_rgb_frames
```

### Issue: Low FPS / dropped frames

```bash
# Reduce resolution
./rgb-grabber --width 424 --height 240 --fps 15

# Lower JPEG quality
./rgb-grabber --quality 70

# Check USB bandwidth
dmesg | grep usb
# Ensure using USB 3.0 port
```

## Integration with Python Controller

See `INTEGRATION.md` for connecting this C++ grabber with the Python liveness processor.
