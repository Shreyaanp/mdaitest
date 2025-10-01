#!/usr/bin/env python3
"""
Design 2: Cyberpunk Neon
- Pink/cyan split colors
- Heavy glitch art
- Digital corruption
- Futuristic HUD
"""

import cv2
import numpy as np
import time
import mediapipe as mp

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

CYAN = (255, 255, 0)
PINK = (255, 0, 255)
PURPLE = (255, 0, 128)

class CyberpunkScanner:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        self.face_detector = mp.solutions.face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=0.5
        )
        self.font = cv2.FONT_HERSHEY_SIMPLEX
    
    def render(self, is_live: bool, confidence: float, elapsed: float) -> np.ndarray:
        """Cyberpunk neon interface."""
        # Dark background with purple tint
        canvas = np.full((SCREEN_HEIGHT, SCREEN_WIDTH, 3), (20, 0, 20), dtype=np.uint8)
        
        center_x = SCREEN_WIDTH // 2
        center_y = SCREEN_HEIGHT // 2
        
        # Glitch lines (random horizontal displacements)
        for _ in range(10):
            y = np.random.randint(0, SCREEN_HEIGHT)
            thickness = np.random.randint(1, 4)
            color = CYAN if np.random.random() > 0.5 else PINK
            cv2.line(canvas, (0, y), (SCREEN_WIDTH, y), color, thickness)
        
        # HUD corners
        corner_size = 50
        cv2.line(canvas, (30, 30), (30+corner_size, 30), CYAN, 3)
        cv2.line(canvas, (30, 30), (30, 30+corner_size), CYAN, 3)
        
        cv2.line(canvas, (SCREEN_WIDTH-30, 30), (SCREEN_WIDTH-30-corner_size, 30), PINK, 3)
        cv2.line(canvas, (SCREEN_WIDTH-30, 30), (SCREEN_WIDTH-30, 30+corner_size), PINK, 3)
        
        # Central hexagon (soul container)
        hex_radius = 100 + int(30 * np.sin(elapsed * 3))
        points = []
        for i in range(6):
            angle = i * np.pi / 3
            x = int(center_x + hex_radius * np.cos(angle))
            y = int(center_y + hex_radius * np.sin(angle))
            points.append([x, y])
        
        points = np.array(points, dtype=np.int32)
        cv2.polylines(canvas, [points], True, CYAN, 3)
        
        # Inner pulsing core
        if is_live:
            core_color = CYAN
            cv2.putText(canvas, "IDENTITY LOCKED", (center_x-120, center_y+150),
                       self.font, 0.8, CYAN, 2)
        else:
            core_color = PINK
            cv2.putText(canvas, "SCANNING...", (center_x-80, center_y+150),
                       self.font, 0.8, PINK, 2)
        
        pulse = 0.6 + 0.4 * np.sin(elapsed * 4)
        core_radius = int(25 * pulse)
        cv2.circle(canvas, (center_x, center_y), core_radius, core_color, -1)
        cv2.circle(canvas, (center_x, center_y), core_radius+5, (255, 255, 255), 2)
        
        # Digital rain effect
        for _ in range(20):
            x = np.random.randint(0, SCREEN_WIDTH)
            y = np.random.randint(0, SCREEN_HEIGHT)
            color = CYAN if np.random.random() > 0.5 else PINK
            cv2.circle(canvas, (x, y), 1, color, -1)
        
        # Confidence bar
        cv2.putText(canvas, f"CONF: {confidence:.1%}", (SCREEN_WIDTH-200, SCREEN_HEIGHT-30),
                   self.font, 0.6, PURPLE, 2)
        
        return canvas
    
    def run(self):
        print("🌃 Cyberpunk Scanner - Press 'q' to quit")
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
            cv2.imshow("Cyberpunk Scanner", display)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        self.cap.release()
        self.face_detector.close()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    scanner = CyberpunkScanner()
    scanner.run()


