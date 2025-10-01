#!/usr/bin/env python3
"""
90s Retro Face Scanner - Identity of Soul
Uses laptop webcam + MediaPipe for face detection
Displays epic 90s-style scanning interface
"""

import cv2
import numpy as np
import time
import mediapipe as mp
from dataclasses import dataclass
from typing import Optional, Tuple

# Colors - Terminal Green Theme
BG_COLOR = (0, 0, 0)  # Black
PRIMARY = (0, 255, 0)  # Phosphor green
SECONDARY = (0, 128, 0)  # Dark green
ACCENT = (0, 255, 128)  # Bright cyan-green
RED = (0, 0, 255)  # BGR format
AMBER = (0, 165, 255)  # Orange/amber

# Screen dimensions
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600


@dataclass
class ScanState:
    """Tracks the scanning animation state."""
    scan_line_y: int = 0
    scan_direction: int = 1  # 1 = down, -1 = up
    progress: float = 0.0
    phase: str = "INITIALIZING"  # INITIALIZING, SCANNING, ANALYZING, COMPLETE
    start_time: float = 0.0
    glitch_frame: int = 0


class RetroFaceScanner:
    """90s-style face scanner with soul theme."""
    
    def __init__(self):
        # Initialize webcam (0 = default laptop camera)
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        
        # MediaPipe face detection
        self.face_detector = mp.solutions.face_detection.FaceDetection(
            model_selection=0,
            min_detection_confidence=0.5
        )
        
        # MediaPipe face mesh for keypoints
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        self.state = ScanState()
        if hasattr(cv2, "FONT_HERSHEY_MONOSPACE"):
            self.font = cv2.FONT_HERSHEY_MONOSPACE
        else:
            # Fallback for OpenCV builds that omit the monospace constant
            self.font = cv2.FONT_HERSHEY_SIMPLEX
        
    def create_canvas(self) -> np.ndarray:
        """Create black canvas with CRT scanlines."""
        canvas = np.zeros((SCREEN_HEIGHT, SCREEN_WIDTH, 3), dtype=np.uint8)
        
        # CRT scanlines effect
        for y in range(0, SCREEN_HEIGHT, 3):
            canvas[y:y+1, :] = (0, 10, 0)  # Subtle green tint
        
        return canvas
    
    def draw_border(self, canvas: np.ndarray, color: Tuple[int, int, int]):
        """Draw 90s-style ASCII border."""
        # Outer border
        cv2.rectangle(canvas, (20, 20), (SCREEN_WIDTH-20, SCREEN_HEIGHT-20), color, 2)
        
        # Inner decorative border
        cv2.rectangle(canvas, (25, 25), (SCREEN_WIDTH-25, SCREEN_HEIGHT-25), SECONDARY, 1)
        
        # Corner brackets (90s style)
        bracket_size = 15
        thickness = 2
        
        # Top-left
        cv2.line(canvas, (20, 20), (20+bracket_size, 20), color, thickness)
        cv2.line(canvas, (20, 20), (20, 20+bracket_size), color, thickness)
        
        # Top-right
        cv2.line(canvas, (SCREEN_WIDTH-20, 20), (SCREEN_WIDTH-20-bracket_size, 20), color, thickness)
        cv2.line(canvas, (SCREEN_WIDTH-20, 20), (SCREEN_WIDTH-20, 20+bracket_size), color, thickness)
        
        # Bottom-left
        cv2.line(canvas, (20, SCREEN_HEIGHT-20), (20+bracket_size, SCREEN_HEIGHT-20), color, thickness)
        cv2.line(canvas, (20, SCREEN_HEIGHT-20), (20, SCREEN_HEIGHT-20-bracket_size), color, thickness)
        
        # Bottom-right
        cv2.line(canvas, (SCREEN_WIDTH-20, SCREEN_HEIGHT-20), (SCREEN_WIDTH-20-bracket_size, SCREEN_HEIGHT-20), color, thickness)
        cv2.line(canvas, (SCREEN_WIDTH-20, SCREEN_HEIGHT-20), (SCREEN_WIDTH-20, SCREEN_HEIGHT-20-bracket_size), color, thickness)
    
    def draw_header(self, canvas: np.ndarray):
        """Draw retro header bar."""
        # Header background
        cv2.rectangle(canvas, (25, 25), (SCREEN_WIDTH-25, 60), SECONDARY, -1)
        cv2.rectangle(canvas, (25, 25), (SCREEN_WIDTH-25, 60), PRIMARY, 1)
        
        # Title text
        cv2.putText(canvas, "IDENTITY OF SOUL - BIOMETRIC SCAN v2.1", 
                   (40, 50), self.font, 0.5, PRIMARY, 1, cv2.LINE_AA)
    
    def draw_scanning_beam(self, canvas: np.ndarray, face_bbox: Optional[Tuple], elapsed: float):
        """Draw horizontal scanning beam that sweeps the face."""
        if not face_bbox:
            return
        
        x, y, w, h = face_bbox
        
        # Update scan line position
        self.state.scan_line_y += self.state.scan_direction * 5
        
        if self.state.scan_line_y > y + h:
            self.state.scan_direction = -1
        elif self.state.scan_line_y < y:
            self.state.scan_direction = 1
            self.state.progress = min(1.0, self.state.progress + 0.05)
        
        # Draw scanning beam
        beam_y = self.state.scan_line_y
        beam_height = 3
        
        # Main beam (bright)
        cv2.rectangle(canvas, (x-20, beam_y-beam_height), (x+w+20, beam_y+beam_height), 
                     ACCENT, -1)
        
        # Glow above/below
        for offset in range(1, 6):
            alpha = 1.0 - (offset / 6.0)
            color_alpha = tuple(int(c * alpha) for c in ACCENT)
            cv2.line(canvas, (x-20, beam_y-offset*2), (x+w+20, beam_y-offset*2), color_alpha, 1)
            cv2.line(canvas, (x-20, beam_y+offset*2), (x+w+20, beam_y+offset*2), color_alpha, 1)
    
    def draw_soul_aura(self, canvas: np.ndarray, face_bbox: Tuple, elapsed: float, is_live: bool):
        """Draw pulsing concentric rings around face (soul aura)."""
        x, y, w, h = face_bbox
        center_x = x + w // 2
        center_y = y + h // 2
        
        # Pulse effect (breathing)
        pulse = 0.8 + 0.2 * np.sin(elapsed * 3)  # 3 Hz pulse
        
        # Draw multiple concentric circles
        max_radius = int(max(w, h) * 1.5)
        
        for i in range(5):
            radius = int((max_radius / 5) * (i + 1) * pulse)
            alpha = 1.0 - (i / 5.0)
            
            if is_live:
                color = tuple(int(c * alpha) for c in ACCENT)
            else:
                color = tuple(int(c * alpha) for c in AMBER)
            
            cv2.circle(canvas, (center_x, center_y), radius, color, 2)
    
    def draw_face_grid(self, canvas: np.ndarray, face_bbox: Tuple):
        """Draw pixelated grid overlay on face (90s digital effect)."""
        x, y, w, h = face_bbox
        
        grid_size = 20
        
        # Draw grid lines
        for gx in range(x, x + w, grid_size):
            cv2.line(canvas, (gx, y), (gx, y + h), SECONDARY, 1)
        
        for gy in range(y, y + h, grid_size):
            cv2.line(canvas, (x, gy), (x + w, gy), SECONDARY, 1)
        
        # Corner markers
        corner_size = 10
        cv2.line(canvas, (x, y), (x+corner_size, y), PRIMARY, 2)
        cv2.line(canvas, (x, y), (x, y+corner_size), PRIMARY, 2)
        
        cv2.line(canvas, (x+w, y), (x+w-corner_size, y), PRIMARY, 2)
        cv2.line(canvas, (x+w, y), (x+w, y+corner_size), PRIMARY, 2)
        
        cv2.line(canvas, (x, y+h), (x+corner_size, y+h), PRIMARY, 2)
        cv2.line(canvas, (x, y+h), (x, y+h-corner_size), PRIMARY, 2)
        
        cv2.line(canvas, (x+w, y+h), (x+w-corner_size, y+h), PRIMARY, 2)
        cv2.line(canvas, (x+w, y+h), (x+w, y+h-corner_size), PRIMARY, 2)
    
    def draw_glitch_effect(self, canvas: np.ndarray):
        """Random glitch displacement (90s digital artifacts)."""
        if np.random.random() < 0.1:  # 10% chance per frame
            # Random horizontal displacement
            for _ in range(3):
                y_start = np.random.randint(0, SCREEN_HEIGHT - 20)
                height = np.random.randint(5, 20)
                shift = np.random.randint(-10, 10)
                
                section = canvas[y_start:y_start+height, :].copy()
                canvas[y_start:y_start+height, :] = 0
                
                if shift > 0:
                    canvas[y_start:y_start+height, shift:] = section[:, :-shift] if shift < canvas.shape[1] else section
                elif shift < 0:
                    canvas[y_start:y_start+height, :shift] = section[:, -shift:] if -shift < canvas.shape[1] else section
    
    def draw_progress_bar(self, canvas: np.ndarray, progress: float):
        """Draw 90s-style progress bar."""
        bar_x = 100
        bar_y = SCREEN_HEIGHT - 80
        bar_width = SCREEN_WIDTH - 200
        bar_height = 30
        
        # Border
        cv2.rectangle(canvas, (bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height), PRIMARY, 2)
        
        # Fill
        fill_width = int(bar_width * progress)
        if fill_width > 0:
            cv2.rectangle(canvas, (bar_x+2, bar_y+2), 
                         (bar_x + fill_width-2, bar_y + bar_height-2), ACCENT, -1)
        
        # Text
        percent_text = f"ANALYZING... {int(progress * 100)}%"
        cv2.putText(canvas, percent_text, (bar_x, bar_y - 10), 
                   self.font, 0.6, PRIMARY, 1, cv2.LINE_AA)
    
    def draw_status_panel(self, canvas: np.ndarray, distance: float, is_live: bool, confidence: float):
        """Draw retro status information panel."""
        panel_x = 40
        panel_y = SCREEN_HEIGHT - 180
        line_height = 25
        
        status_text = "LIVE" if is_live else "ANALYZING"
        status_color = PRIMARY if is_live else AMBER
        
        lines = [
            f"DIST: {distance:.2f}M",
            f"CONF: {confidence:.3f}",
            f"STATUS: {status_text}",
            f"SOUL PATTERN: {'AUTHENTIC' if is_live else 'SCANNING...'}",
        ]
        
        for i, line in enumerate(lines):
            cv2.putText(canvas, line, (panel_x, panel_y + i * line_height),
                       self.font, 0.6, status_color, 1, cv2.LINE_AA)
    
    def draw_matrix_rain(self, canvas: np.ndarray, elapsed: float):
        """Matrix-style falling characters in background."""
        # Only draw occasionally for performance
        if int(elapsed * 10) % 3 == 0:
            for _ in range(5):
                x = np.random.randint(30, SCREEN_WIDTH-30)
                y = np.random.randint(70, SCREEN_HEIGHT-200)
                char = chr(np.random.randint(0x30, 0x7A))  # Random ASCII
                alpha = np.random.random() * 0.3
                color = tuple(int(c * alpha) for c in PRIMARY)
                cv2.putText(canvas, char, (x, y), self.font, 0.4, color, 1)
    
    def draw_final_flash(self, canvas: np.ndarray, is_live: bool):
        """Full screen flash when scan complete."""
        flash_color = PRIMARY if is_live else RED
        overlay = canvas.copy()
        cv2.rectangle(overlay, (0, 0), (SCREEN_WIDTH, SCREEN_HEIGHT), flash_color, -1)
        cv2.addWeighted(canvas, 0.7, overlay, 0.3, 0, canvas)
        
        # Big text
        text = "ACCESS GRANTED" if is_live else "ACCESS DENIED"
        text_size = cv2.getTextSize(text, self.font, 1.5, 3)[0]
        text_x = (SCREEN_WIDTH - text_size[0]) // 2
        text_y = SCREEN_HEIGHT // 2
        
        # Text with glow
        for offset in range(5, 0, -1):
            alpha = 1.0 - (offset / 5.0)
            glow_color = tuple(int(c * alpha) for c in flash_color)
            cv2.putText(canvas, text, (text_x, text_y), 
                       self.font, 1.5, glow_color, offset+3, cv2.LINE_AA)
        
        cv2.putText(canvas, text, (text_x, text_y), 
                   self.font, 1.5, (255, 255, 255), 3, cv2.LINE_AA)
    
    def process_frame(self, frame: np.ndarray, elapsed: float) -> Tuple[np.ndarray, bool, float]:
        """Process camera frame and detect face."""
        # Convert to RGB for MediaPipe
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Detect face
        results = self.face_detector.process(rgb)
        
        face_bbox = None
        confidence = 0.0
        is_live = False
        distance = 0.0
        
        if results.detections:
            detection = results.detections[0]
            confidence = detection.score[0]
            
            # Get bounding box
            bbox = detection.location_data.relative_bounding_box
            h, w = frame.shape[:2]
            
            x = int(bbox.xmin * w)
            y = int(bbox.ymin * h)
            box_w = int(bbox.width * w)
            box_h = int(bbox.height * h)
            
            face_bbox = (x, y, box_w, box_h)
            
            # Mock distance based on face size (bigger = closer)
            distance = 1.0 - (box_w / w) * 0.7  # Rough estimate
            
            # Simple liveness: if face detected and reasonable size
            is_live = 0.3 < distance < 1.0 and confidence > 0.6
        
        return frame, is_live, confidence, face_bbox, distance
    
    def render_retro_interface(self, camera_frame: np.ndarray, is_live: bool, 
                               confidence: float, face_bbox: Optional[Tuple], 
                               distance: float, elapsed: float) -> np.ndarray:
        """Render the full 90s retro interface - NO CAMERA FEED, just abstract visualization."""
        # Create base canvas
        canvas = self.create_canvas()
        
        # Update phase based on time
        if elapsed < 1.0:
            self.state.phase = "INITIALIZING"
            self.state.progress = elapsed / 1.0
        elif elapsed < 3.5:
            self.state.phase = "SCANNING"
            self.state.progress = (elapsed - 1.0) / 2.5
        elif elapsed < 4.5:
            self.state.phase = "ANALYZING"
            self.state.progress = (elapsed - 3.5) / 1.0
        else:
            self.state.phase = "COMPLETE"
            self.state.progress = 1.0
        
        # Draw border
        border_color = PRIMARY if is_live else AMBER
        self.draw_border(canvas, border_color)
        
        # Draw header
        self.draw_header(canvas)
        
        # Matrix rain in background
        if self.state.phase in ["SCANNING", "ANALYZING"]:
            self.draw_matrix_rain(canvas, elapsed)
        
        # NO CAMERA FEED - Just abstract visualization
        if face_bbox:
            # Map face position to canvas center area
            x, y, w, h = face_bbox
            
            # Create abstract representation in center of screen
            center_x = SCREEN_WIDTH // 2
            center_y = SCREEN_HEIGHT // 2 - 50
            
            # Size based on face size (but don't show actual face)
            viz_size = min(200, max(100, w))
            
            canvas_bbox = (center_x - viz_size//2, center_y - viz_size//2, viz_size, viz_size)
            
            # Draw abstract face region (box with grid)
            self.draw_face_grid(canvas, canvas_bbox)
            
            # Draw soul aura around abstract region
            if self.state.phase == "SCANNING":
                self.draw_soul_aura(canvas, canvas_bbox, elapsed, is_live)
            
            # Draw scanning beam across abstract region
            if self.state.phase == "SCANNING":
                self.draw_scanning_beam(canvas, canvas_bbox, elapsed)
            
            # Draw central soul orb (instead of face)
            orb_color = PRIMARY if is_live else AMBER
            pulse = 0.8 + 0.2 * np.sin(elapsed * 4)
            orb_radius = int(30 * pulse)
            
            # Draw pulsing orb with glow
            for r in range(orb_radius, 0, -3):
                alpha = r / orb_radius
                color = tuple(int(c * alpha) for c in orb_color)
                cv2.circle(canvas, (center_x, center_y), r, color, -1)
            
            # Core bright center
            cv2.circle(canvas, (center_x, center_y), 8, (255, 255, 255), -1)
        
        # Draw progress bar
        if self.state.phase in ["SCANNING", "ANALYZING"]:
            self.draw_progress_bar(canvas, self.state.progress)
        
        # Draw status panel
        self.draw_status_panel(canvas, distance, is_live, confidence)
        
        # Glitch effect (random)
        if self.state.phase == "ANALYZING":
            self.draw_glitch_effect(canvas)
        
        # Final flash
        if self.state.phase == "COMPLETE":
            self.draw_final_flash(canvas, is_live)
        
        # Add hieroglyph watermark (𓅽 as text)
        cv2.putText(canvas, "SOUL", (SCREEN_WIDTH - 100, SCREEN_HEIGHT - 40),
                   self.font, 0.5, SECONDARY, 1)
        
        return canvas
    
    def run(self):
        """Main loop."""
        print("🎮 90s Retro Face Scanner - Identity of Soul")
        print("Press 'q' to quit, 'r' to restart scan")
        
        start_time = time.time()
        
        while True:
            ret, frame = self.cap.read()
            if not ret:
                print("Failed to grab frame")
                break
            
            elapsed = time.time() - start_time
            
            # Reset scan on 'r' key or after 5 seconds
            if elapsed > 5.0:
                start_time = time.time()
                self.state = ScanState()
            
            # Process frame
            _, is_live, confidence, face_bbox, distance = self.process_frame(frame, elapsed)
            
            # Render retro interface
            display = self.render_retro_interface(frame, is_live, confidence, 
                                                  face_bbox, distance, elapsed)
            
            # Show
            cv2.imshow("Identity of Soul - Retro Scanner", display)
            
            # Handle keys
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('r'):
                start_time = time.time()
                self.state = ScanState()
        
        # Cleanup
        self.cap.release()
        self.face_detector.close()
        self.face_mesh.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    scanner = RetroFaceScanner()
    scanner.run()
