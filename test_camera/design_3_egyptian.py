#!/usr/bin/env python3
"""
Design 3: Ancient Egyptian Tech
- Hieroglyphs floating
- Golden/bronze colors
- Stone texture
- Ancient meets digital
"""

import cv2
import numpy as np
import time
import mediapipe as mp

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

GOLD = (0, 215, 255)
BRONZE = (0, 140, 205)
DARK_GOLD = (0, 100, 139)

class EgyptianScanner:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        self.face_detector = mp.solutions.face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=0.5
        )
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        
        # Hieroglyphs (using Unicode approximations)
        self.hieroglyphs = ['𓂀', '𓅓', '𓆃', '𓇯', '𓋹', '𓎡']
        self.particles = []
    
    def create_stone_texture(self) -> np.ndarray:
        """Create ancient stone background."""
        # Dark brown/black base
        canvas = np.random.randint(15, 35, (SCREEN_HEIGHT, SCREEN_WIDTH, 3), dtype=np.uint8)
        canvas[:, :, 0] = canvas[:, :, 0] * 0.6  # Less blue
        canvas[:, :, 1] = canvas[:, :, 1] * 0.7  # Less green
        return canvas
    
    def render(self, is_live: bool, confidence: float, elapsed: float) -> np.ndarray:
        """Egyptian tech interface."""
        canvas = self.create_stone_texture()
        
        center_x = SCREEN_WIDTH // 2
        center_y = SCREEN_HEIGHT // 2
        
        # Draw Eye of Ra in center
        eye_width = 120
        eye_height = 60
        
        # Eye outline
        cv2.ellipse(canvas, (center_x, center_y), (eye_width, eye_height), 
                   0, 0, 360, GOLD, 3)
        
        # Pupil (pulsing)
        pulse = 0.7 + 0.3 * np.sin(elapsed * 3)
        pupil_radius = int(20 * pulse)
        
        if is_live:
            pupil_color = GOLD
        else:
            pupil_color = BRONZE
        
        # Pupil with glow
        for r in range(pupil_radius+15, pupil_radius, -1):
            alpha = 1.0 - ((r - pupil_radius) / 15.0)
            color = tuple(int(c * alpha * 0.5) for c in pupil_color)
            cv2.circle(canvas, (center_x, center_y), r, color, -1)
        
        cv2.circle(canvas, (center_x, center_y), pupil_radius, pupil_color, -1)
        
        # Floating hieroglyphs (orbiting)
        num_glyphs = 6
        orbit_radius = 180
        
        for i in range(num_glyphs):
            angle = (elapsed * 0.3 + i * 2 * np.pi / num_glyphs) % (2 * np.pi)
            x = int(center_x + orbit_radius * np.cos(angle))
            y = int(center_y + orbit_radius * np.sin(angle))
            
            # Draw glyph as geometric shape (since Unicode might not render)
            glyph_size = 15
            alpha = 0.6 + 0.4 * np.sin(elapsed * 2 + i)
            color = tuple(int(c * alpha) for c in GOLD)
            
            # Simple hieroglyph-like shapes
            if i % 3 == 0:
                cv2.circle(canvas, (x, y), glyph_size, color, 2)
            elif i % 3 == 1:
                pts = np.array([[x, y-glyph_size], [x+glyph_size, y+glyph_size], 
                               [x-glyph_size, y+glyph_size]], dtype=np.int32)
                cv2.polylines(canvas, [pts], True, color, 2)
            else:
                cv2.rectangle(canvas, (x-glyph_size, y-glyph_size), 
                            (x+glyph_size, y+glyph_size), color, 2)
        
        # Status text (ancient style)
        if is_live:
            text = "KA RECOGNIZED"  # Ka = ancient Egyptian soul
        else:
            text = "SEEKING KA..."
        
        text_size = cv2.getTextSize(text, self.font, 0.8, 2)[0]
        text_x = (SCREEN_WIDTH - text_size[0]) // 2
        cv2.putText(canvas, text, (text_x, SCREEN_HEIGHT - 50),
                   self.font, 0.8, GOLD, 2)
        
        return canvas
    
    def run(self):
        print("𓂀 Egyptian Scanner - Press 'q' to quit")
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
            cv2.imshow("Egyptian Scanner", display)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        self.cap.release()
        self.face_detector.close()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    scanner = EgyptianScanner()
    scanner.run()


