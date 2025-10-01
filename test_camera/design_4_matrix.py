#!/usr/bin/env python3
"""
Design 4: Matrix Code Rain
- Full screen falling characters
- Face = void in the rain
- Green on black
- Iconic minimal style
"""

import cv2
import numpy as np
import time
import mediapipe as mp
from collections import deque

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

GREEN = (0, 255, 0)
DARK_GREEN = (0, 128, 0)

class MatrixScanner:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        self.face_detector = mp.solutions.face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=0.5
        )
        
        # Matrix columns
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.columns = 60
        self.streams = [deque(maxlen=30) for _ in range(self.columns)]
        
        # Initialize streams
        for stream in self.streams:
            for _ in range(np.random.randint(5, 20)):
                stream.append(chr(np.random.randint(0x30, 0x7A)))
    
    def render(self, is_live: bool, face_bbox: Optional, elapsed: float) -> np.ndarray:
        """Matrix rain with void for soul."""
        canvas = np.zeros((SCREEN_HEIGHT, SCREEN_WIDTH, 3), dtype=np.uint8)
        
        # Update and draw matrix columns
        col_width = SCREEN_WIDTH // self.columns
        
        for i, stream in enumerate(self.streams):
            x = i * col_width + 5
            
            # Add new character occasionally
            if np.random.random() < 0.1:
                stream.append(chr(np.random.randint(0x30, 0x7A)))
            
            # Draw stream
            for j, char in enumerate(stream):
                y = 20 + j * 15
                if y > SCREEN_HEIGHT:
                    continue
                
                # Skip drawing in face region (create void)
                center_x = SCREEN_WIDTH // 2
                center_y = SCREEN_HEIGHT // 2
                void_radius = 120 if face_bbox else 0
                
                if face_bbox:
                    dist = np.sqrt((x - center_x)**2 + (y - center_y)**2)
                    if dist < void_radius:
                        continue  # Skip - create void
                
                # Fade from bright (head) to dark (tail)
                alpha = 1.0 - (j / len(stream))
                color = tuple(int(c * alpha) for c in GREEN)
                
                # Brightest at head
                if j == len(stream) - 1:
                    color = (255, 255, 255)
                
                cv2.putText(canvas, char, (x, y), self.font, 0.4, color, 1)
        
        # Draw soul orb in the void
        if face_bbox:
            pulse = 0.7 + 0.3 * np.sin(elapsed * 3)
            orb_radius = int(40 * pulse)
            
            # Orb with glow
            for r in range(orb_radius+20, orb_radius, -2):
                alpha = 1.0 - ((r - orb_radius) / 20.0)
                color = tuple(int(c * alpha * 0.6) for c in GREEN)
                cv2.circle(canvas, (center_x, center_y), r, color, -1)
            
            cv2.circle(canvas, (center_x, center_y), orb_radius, GREEN, -1)
            cv2.circle(canvas, (center_x, center_y), orb_radius+3, (255, 255, 255), 2)
            
            # Status
            if is_live:
                cv2.putText(canvas, "ESSENCE DETECTED", (center_x-100, center_y+80),
                           self.font, 0.7, GREEN, 2)
        
        return canvas
    
    def run(self):
        print("💚 Matrix Scanner - Press 'q' to quit")
        start_time = time.time()
        
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            
            elapsed = time.time() - start_time
            
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.face_detector.process(rgb)
            
            is_live = False
            face_bbox = None
            
            if results.detections:
                is_live = True
                det = results.detections[0]
                bbox = det.location_data.relative_bounding_box
                h, w = frame.shape[:2]
                face_bbox = (int(bbox.xmin * w), int(bbox.ymin * h), 
                            int(bbox.width * w), int(bbox.height * h))
            
            display = self.render(is_live, face_bbox, elapsed)
            cv2.imshow("Matrix Scanner", display)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        self.cap.release()
        self.face_detector.close()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    scanner = MatrixScanner()
    scanner.run()


