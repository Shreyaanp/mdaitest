# 📊 Session Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         SESSION FLOW                                 │
└─────────────────────────────────────────────────────────────────────┘

╔═══════════════════════════════════════════════════════════════════╗
║ 1. IDLE - Waiting for User                                        ║
╠═══════════════════════════════════════════════════════════════════╣
║ ┌───────────────────────────────────────────────────────────────┐ ║
║ │ 📺 TV Bars (static at 60%)                                    │ ║
║ │ 🎵 Marquee scrolling continuously                             │ ║
║ │ ⏳ Duration: ∞ (until ToF trigger)                            │ ║
║ │ 📷 Camera: OFF                                                │ ║
║ └───────────────────────────────────────────────────────────────┘ ║
╚═══════════════════════════════════════════════════════════════════╝
                              │
                              │ 👆 ToF sensor triggered
                              ↓
╔═══════════════════════════════════════════════════════════════════╗
║ 2. PAIRING_REQUEST - Requesting Token                            ║
╠═══════════════════════════════════════════════════════════════════╣
║ ┌───────────────────────────────────────────────────────────────┐ ║
║ │ 📺 TV Bars falling animation (retracting up)                  │ ║
║ │ 🔄 Backend: POST /api/tokens → get pairing token             │ ║
║ │ ⏱️  Duration: 1.5s                                             │ ║
║ │ 📷 Camera: OFF                                                │ ║
║ └───────────────────────────────────────────────────────────────┘ ║
╚═══════════════════════════════════════════════════════════════════╝
                              │
                              ↓
╔═══════════════════════════════════════════════════════════════════╗
║ 3. HELLO_HUMAN - Welcome Screen                                  ║
╠═══════════════════════════════════════════════════════════════════╣
║ ┌───────────────────────────────────────────────────────────────┐ ║
║ │ 👋 "Hello Human" message                                      │ ║
║ │ 🎨 Hero animation                                             │ ║
║ │ ⏱️  Duration: 2s                                               │ ║
║ │ 📷 Camera: OFF                                                │ ║
║ └───────────────────────────────────────────────────────────────┘ ║
╚═══════════════════════════════════════════════════════════════════╝
                              │
                              ↓
╔═══════════════════════════════════════════════════════════════════╗
║ 4. QR_DISPLAY - Scan Prompt                                      ║
╠═══════════════════════════════════════════════════════════════════╣
║ ┌───────────────────────────────────────────────────────────────┐ ║
║ │ 📱 QR Code displayed                                          │ ║
║ │ 💬 "Scan this to get started"                                 │ ║
║ │ 🔌 WebSocket connected to bridge                              │ ║
║ │ ⏳ Duration: ∞ (until mobile app connects)                    │ ║
║ │ 📷 Camera: OFF                                                │ ║
║ │                                                               │ ║
║ │ Waiting for:                                                  │ ║
║ │   • Mobile app scans QR                                       │ ║
║ │   • WS message: { type: 'from_app', data: { platform_id }}   │ ║
║ └───────────────────────────────────────────────────────────────┘ ║
╚═══════════════════════════════════════════════════════════════════╝
                              │
                              │ ✅ platform_id received
                              ↓
╔═══════════════════════════════════════════════════════════════════╗
║ 5. HUMAN_DETECT - Face Validation                                ║
╠═══════════════════════════════════════════════════════════════════╣
║ ┌───────────────────────────────────────────────────────────────┐ ║
║ │ 📹 Live camera preview (MJPEG stream)                         │ ║
║ │ 🎥 RealSense D435i + MediaPipe                                │ ║
║ │ ⏱️  Duration: EXACTLY 3.5 seconds                              │ ║
║ │ 📷 Camera: ON                                                 │ ║
║ │                                                               │ ║
║ │ Processing:                                                   │ ║
║ │   • Collect frames continuously (~35 frames @ 10fps)          │ ║
║ │   • Check each frame: depth_ok? (3D profile = real human)     │ ║
║ │   • Track passing frames (need ≥10)                           │ ║
║ │   • Calculate quality score: stability*0.7 + focus*0.3        │ ║
║ │   • Keep best frame                                           │ ║
║ │                                                               │ ║
║ │ At 3.5s:                                                      │ ║
║ │   ✅ if passing_frames ≥ 10 → SUCCESS (use best frame)        │ ║
║ │   ❌ if passing_frames < 10 → FAIL ("Position your face")     │ ║
║ │                                                               │ ║
║ │ Saves:                                                        │ ║
║ │   • ONLY best frame to captures/                              │ ║
║ │   • No debug frames saved                                     │ ║
║ └───────────────────────────────────────────────────────────────┘ ║
╚═══════════════════════════════════════════════════════════════════╝
                              │
                              │ ✅ Validation passed
                              ↓
╔═══════════════════════════════════════════════════════════════════╗
║ 6. PROCESSING - Upload & Backend Processing                      ║
╠═══════════════════════════════════════════════════════════════════╣
║ ┌───────────────────────────────────────────────────────────────┐ ║
║ │ 🎬 Processing animation (ProcessingScreen component)          │ ║
║ │ 💬 "processing scan, please wait"                             │ ║
║ │ 📷 Camera: OFF (deactivated)                                  │ ║
║ │                                                               │ ║
║ │ Actions:                                                      │ ║
║ │   1. Encode best frame → base64                               │ ║
║ │   2. Send via WS: { type: 'to_backend', data: { image... }}  │ ║
║ │   3. Wait for backend acknowledgment                          │ ║
║ │                                                               │ ║
║ │ ⏱️  Duration: 3s min, 15s max                                  │ ║
║ │   • Min 3s: Ensure user sees animation                        │ ║
║ │   • Max 15s: Timeout if backend doesn't respond               │ ║
║ │   • If backend responds in <3s: wait until 3s                 │ ║
║ │   • If backend takes >15s: ERROR timeout                      │ ║
║ └───────────────────────────────────────────────────────────────┘ ║
╚═══════════════════════════════════════════════════════════════════╝
                              │
                              │ ✅ Backend ACK received
                              ↓
╔═══════════════════════════════════════════════════════════════════╗
║ 7. COMPLETE - Success                                             ║
╠═══════════════════════════════════════════════════════════════════╣
║ ┌───────────────────────────────────────────────────────────────┐ ║
║ │ 🎉 "Complete!"                                                │ ║
║ │ 💬 "Thank you"                                                │ ║
║ │ ⏱️  Duration: 3s                                               │ ║
║ │ 📷 Camera: OFF                                                │ ║
║ └───────────────────────────────────────────────────────────────┘ ║
╚═══════════════════════════════════════════════════════════════════╝
                              │
                              │ Auto transition after 3s
                              ↓
                        ┌──────────┐
                        │  → IDLE  │
                        └──────────┘


╔═══════════════════════════════════════════════════════════════════╗
║ ERROR PATH (any phase can fail)                                   ║
╠═══════════════════════════════════════════════════════════════════╣
║ ┌───────────────────────────────────────────────────────────────┐ ║
║ │ ❌ "Please try again"                                          │ ║
║ │ 💬 User-friendly error message                                │ ║
║ │ ⏱️  Duration: 3s                                               │ ║
║ │ 📷 Camera: OFF                                                │ ║
║ │                                                               │ ║
║ │ Common errors:                                                │ ║
║ │   • "Please position your face in frame" (<10 passing frames) │ ║
║ │   • "Mobile app did not connect in time" (QR timeout)         │ ║
║ │   • "Backend processing timeout (15s)" (no ACK)               │ ║
║ │   • "Please try again" (generic error)                        │ ║
║ └───────────────────────────────────────────────────────────────┘ ║
╚═══════════════════════════════════════════════════════════════════╝
                              │
                              │ Auto transition after 3s
                              ↓
                        ┌──────────┐
                        │  → IDLE  │
                        └──────────┘


┌─────────────────────────────────────────────────────────────────────┐
│                         CAMERA LIFECYCLE                             │
└─────────────────────────────────────────────────────────────────────┘

Phase               │ Camera State │ Preview Visible │ Liveness Active
────────────────────┼──────────────┼─────────────────┼────────────────
idle                │ ❌ OFF        │ ❌ NO            │ ❌ NO
pairing_request     │ ❌ OFF        │ ❌ NO            │ ❌ NO
hello_human         │ ❌ OFF        │ ❌ NO            │ ❌ NO
qr_display          │ ❌ OFF        │ ❌ NO            │ ❌ NO
human_detect        │ ✅ ON         │ ✅ YES           │ ✅ YES
processing          │ ❌ OFF        │ ❌ NO            │ ❌ NO
complete            │ ❌ OFF        │ ❌ NO            │ ❌ NO
error               │ ❌ OFF        │ ❌ NO            │ ❌ NO


┌─────────────────────────────────────────────────────────────────────┐
│                         TIMING SUMMARY                               │
└─────────────────────────────────────────────────────────────────────┘

Total session time (happy path):
  1.5s  (pairing)
+ 2.0s  (hello human)
+ 0-90s (QR wait - depends on user)
+ 3.5s  (validation)
+ 3-15s (processing)
+ 3.0s  (complete)
────────
≈ 13-115 seconds (not counting QR wait)

Typical user experience: ~20-30 seconds total
```
