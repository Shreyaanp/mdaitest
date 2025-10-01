# 90s Retro Face Scanner - Identity of Soul 🎮

## Overview
Standalone test app using your laptop webcam with epic 90s-style scanning interface.

## Features

### 90s Retro Effects:
- ✅ **CRT Scanlines** - Green phosphor screen effect
- ✅ **Scanning Beam** - Horizontal line sweeping face
- ✅ **Soul Aura** - Pulsing concentric rings (breathing effect)
- ✅ **Face Grid** - Pixelated overlay (digital effect)
- ✅ **Glitch Artifacts** - Random displacement effects
- ✅ **Matrix Rain** - Falling characters in background
- ✅ **Progress Bar** - Classic 90s loading bar
- ✅ **Terminal Text** - Monospace phosphor green
- ✅ **ASCII Borders** - Box-drawing characters
- ✅ **Access Flash** - Final "GRANTED/DENIED" effect

### Animation Sequence (5 seconds):
1. **0-1s**: INITIALIZING - Border draws, scanlines appear
2. **1-3.5s**: SCANNING - Beam sweeps, aura pulses, grid overlay
3. **3.5-4.5s**: ANALYZING - Progress bar, glitch effects, matrix rain
4. **4.5-5s**: COMPLETE - Flash screen, "ACCESS GRANTED" or "DENIED"

## Installation

```bash
cd /home/ichiro/Desktop/mercleapp/mDai/mdaitest/test_camera

# Install dependencies (if needed)
pip install opencv-python mediapipe numpy
```

## Usage

```bash
python retro_scanner.py
```

### Controls:
- `q` - Quit
- `r` - Restart scan animation

## Configuration

Edit these values in the code:

```python
# Colors (Terminal Green Theme)
PRIMARY = (0, 255, 0)  # Phosphor green

# Or try Amber CRT:
PRIMARY = (0, 165, 255)  # Amber

# Or Cyan Matrix:
PRIMARY = (255, 255, 0)  # Cyan
```

## Display

**Screen Size**: 800×600 (classic 4:3 aspect ratio)  
**Camera Feed**: 640×480 scaled to 50% and centered  
**Font**: Monospace (retro terminal)

## How It Works

1. **Webcam** captures video (laptop camera)
2. **MediaPipe** detects face
3. **Canvas** renders 90s-style UI
4. **Effects** animate based on elapsed time
5. **Loop** restarts every 5 seconds

## Theme: "Identity of Soul"

The visual language expresses:
- **Soul as energy**: Pulsing aura rings
- **Digital spirituality**: Matrix rain + scanning beams  
- **Ancient tech**: Hieroglyph watermarks (𓅽)
- **90s nostalgia**: Green phosphor, ASCII borders
- **Biometric mysticism**: "Scanning your essence"

## Sample Output

```
╔════════════════════════════════════════╗
║ IDENTITY OF SOUL - BIOMETRIC SCAN v2.1 ║
╠════════════════════════════════════════╣
║     ·  ·  ·  ·  ·  ·  ·  ·  ·  ·      ║
║   ·  ·  ┌────────────┐  ·  ·  ·       ║
║  ·  ·  │    👤      │  ·  ·  ·      ║
║   ·  ·  │ ≋≋≋≋≋≋≋≋  │  ·  ·  ·       ║
║     ·  └────────────┘  ·  ·  ·  ·     ║
║  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·  ·     ║
║                                        ║
║  ANALYZING... ████████░░░░ 67%        ║
║                                        ║
║  DIST: 0.52M        CONF: 0.818       ║
║  STATUS: LIVE                          ║
║  SOUL PATTERN: AUTHENTIC               ║
╚════════════════════════════════════════╝
```

## Troubleshooting

**No camera detected:**
```bash
ls /dev/video*
```

**Wrong camera:**
Edit line 23: `self.cap = cv2.VideoCapture(1)`  # Try 1, 2, etc.

**Too slow:**
- Reduce SCREEN_WIDTH/HEIGHT
- Disable matrix rain
- Lower FPS

**Colors wrong:**
Your terminal might need BGR → RGB swap if colors look inverted.

## Next Steps

Once you like the design, we can:
1. Port this style to the main RealSense preview
2. Add it to the UI's camera preview component
3. Customize colors/text for production
4. Add sound effects (optional)

Enjoy the 90s vibes! 🎮✨

