#!/usr/bin/env python3
"""
Design 1: Minimalist Zen
- Pure black screen
- Single pulsing dot
- Subtle ripples
- No text, pure visual
"""

import cv2
import numpy as np
import time
import mediapipe as mp
from typing import Optional, Tuple

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

class ZenScanner:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        self.face_detector = mp.solutions.face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=0.5
        )
    
    def render(self, is_live: bool, elapsed: float) -> np.ndarray:
        """Pure minimalist zen interface."""
        # Pure black canvas
        canvas = np.zeros((SCREEN_HEIGHT, SCREEN_WIDTH, 3), dtype=np.uint8)
        
        center_x = SCREEN_WIDTH // 2
        center_y = SCREEN_HEIGHT // 2
        
        # Breathing pulse
        pulse = 0.5 + 0.5 * np.sin(elapsed * 2)
        
        if is_live:
            # Soul detected - white pulsing dot
            core_color = (255, 255, 255)
            ripple_color = (200, 200, 200)
        else:
            # Searching - dim gray dot
            core_color = (80, 80, 80)
            ripple_color = (50, 50, 50)
        
        # Draw expanding ripples (subtle)
        for i in range(5):
            radius = int(30 + i * 40 + (elapsed * 20) % 200)
            alpha = 1.0 - (radius / 250.0)
            if alpha > 0:
                color = tuple(int(c * alpha * 0.3) for c in ripple_color)
                cv2.circle(canvas, (center_x, center_y), radius, color, 1)
        
        # Central pulsing soul dot
        dot_radius = int(15 + 10 * pulse)
        
        # Glow layers
        for r in range(dot_radius + 20, dot_radius, -2):
            alpha = 1.0 - ((r - dot_radius) / 20.0)
            color = tuple(int(c * alpha * 0.4) for c in core_color)
            cv2.circle(canvas, (center_x, center_y), r, color, -1)
        
        # Core
        cv2.circle(canvas, (center_x, center_y), dot_radius, core_color, -1)
        
        return canvas
    
    def run(self):
        print("🧘 Zen Scanner - Press 'q' to quit")
        start_time = time.time()
        
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            
            elapsed = time.time() - start_time
            
            # Detect face
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.face_detector.process(rgb)
            is_live = results.detections is not None and len(results.detections) > 0
            
            # Render zen interface
            display = self.render(is_live, elapsed)
            
            cv2.imshow("Zen Scanner", display)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        self.cap.release()
        self.face_detector.close()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    scanner = ZenScanner()
    scanner.run()


