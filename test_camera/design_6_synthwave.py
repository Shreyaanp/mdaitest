#!/usr/bin/env python3
"""
Design 6: Synthwave Retro
- Pink/purple gradient
- Grid floor perspective
- Sun/geometric shapes
- 80s aesthetic
"""

import cv2
import numpy as np
import time
import mediapipe as mp

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

PINK = (180, 0, 255)
PURPLE = (255, 0, 128)
CYAN = (255, 255, 0)

class SynthwaveScanner:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        self.face_detector = mp.solutions.face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=0.5
        )
        self.font = cv2.FONT_HERSHEY_SIMPLEX
    
    def draw_gradient_bg(self, canvas: np.ndarray):
        """Purple to pink gradient background."""
        for y in range(SCREEN_HEIGHT):
            ratio = y / SCREEN_HEIGHT
            color = (
                int(180 + (255-180) * ratio),  # B
                0,  # G
                int(255 - 128 * ratio)  # R
            )
            canvas[y, :] = color
    
    def draw_grid_floor(self, canvas: np.ndarray, elapsed: float):
        """Perspective grid floor (80s style)."""
        horizon = SCREEN_HEIGHT // 2
        
        # Horizontal lines (perspective)
        for i in range(10):
            y = int(horizon + (SCREEN_HEIGHT - horizon) * (i / 10))
            thickness = 1 if i < 8 else 2
            cv2.line(canvas, (0, y), (SCREEN_WIDTH, y), CYAN, thickness)
        
        # Vertical lines (converging to center)
        center_x = SCREEN_WIDTH // 2
        for i in range(-5, 6):
            x_top = center_x + i * 30
            x_bottom = center_x + i * 120
            cv2.line(canvas, (x_top, horizon), (x_bottom, SCREEN_HEIGHT), CYAN, 1)
        
        # Animated scan line
        scan_y = int(horizon + ((SCREEN_HEIGHT - horizon) * ((elapsed * 0.5) % 1.0)))
        cv2.line(canvas, (0, scan_y), (SCREEN_WIDTH, scan_y), (255, 255, 255), 2)
    
    def render(self, is_live: bool, confidence: float, elapsed: float) -> np.ndarray:
        """Synthwave aesthetic."""
        canvas = np.zeros((SCREEN_HEIGHT, SCREEN_WIDTH, 3), dtype=np.uint8)
        
        # Gradient background
        self.draw_gradient_bg(canvas)
        
        # Grid floor
        self.draw_grid_floor(canvas, elapsed)
        
        # Sun in background
        sun_y = SCREEN_HEIGHT // 3
        sun_x = SCREEN_WIDTH // 2
        
        # Sun with horizontal lines
        for r in range(80, 0, -10):
            color = PINK if r % 20 == 0 else PURPLE
            cv2.circle(canvas, (sun_x, sun_y), r, color, 2)
        
        # Sun rays
        for i in range(12):
            angle = i * np.pi / 6 + elapsed * 0.5
            x_end = int(sun_x + 100 * np.cos(angle))
            y_end = int(sun_y + 100 * np.sin(angle))
            cv2.line(canvas, (sun_x, sun_y), (x_end, y_end), PINK, 2)
        
        # Soul diamond (floating)
        center_x = SCREEN_WIDTH // 2
        center_y = SCREEN_HEIGHT // 2 + 50
        
        float_offset = int(10 * np.sin(elapsed * 2))
        diamond_y = center_y + float_offset
        
        # Diamond shape
        size = 40
        points = np.array([
            [center_x, diamond_y - size],
            [center_x + size, diamond_y],
            [center_x, diamond_y + size],
            [center_x - size, diamond_y]
        ], dtype=np.int32)
        
        if is_live:
            cv2.fillPoly(canvas, [points], CYAN)
            cv2.polylines(canvas, [points], True, (255, 255, 255), 3)
            
            cv2.putText(canvas, "IDENTITY CONFIRMED", (center_x-120, SCREEN_HEIGHT-40),
                       self.font, 0.8, CYAN, 2)
        else:
            cv2.polylines(canvas, [points], True, PINK, 3)
            cv2.putText(canvas, "SCANNING ESSENCE...", (center_x-120, SCREEN_HEIGHT-40),
                       self.font, 0.8, PINK, 2)
        
        return canvas
    
    def run(self):
        print("🌅 Synthwave Scanner - Press 'q' to quit")
        start_time = time.time()
        
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            
            elapsed = time.time() - start_time
            
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.face_detector.process(rgb)
            
            is_live = False
            confidence = 0.0
            if results.detections:
                is_live = True
                confidence = results.detections[0].score[0]
            
            display = self.render(is_live, confidence, elapsed)
            cv2.imshow("Synthwave Scanner", display)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        self.cap.release()
        self.face_detector.close()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    scanner = SynthwaveScanner()
    scanner.run()


