#!/usr/bin/env python3
"""
Design 8: Sound Visualizer Style
- Waveforms representing frequency
- Circular audio spectrum
- Pulsing to confidence
- Music visualizer aesthetic
"""

import cv2
import numpy as np
import time
import mediapipe as mp

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

CYAN = (255, 200, 0)
BLUE = (255, 100, 0)
WHITE = (255, 255, 255)

class SoundwaveScanner:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        self.face_detector = mp.solutions.face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=0.5
        )
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        
        # Waveform data
        self.num_bars = 60
        self.bar_heights = np.zeros(self.num_bars)
    
    def update_bars(self, is_live: bool, confidence: float, elapsed: float):
        """Update frequency bars."""
        # Simulate audio spectrum based on detection
        for i in range(self.num_bars):
            if is_live:
                # Active - high amplitude
                target = np.sin(elapsed * 3 + i * 0.3) * 0.5 + 0.5
                target *= confidence * 100
            else:
                # Idle - low amplitude
                target = np.random.random() * 20
            
            # Smooth transition
            self.bar_heights[i] += (target - self.bar_heights[i]) * 0.2
    
    def render(self, is_live: bool, confidence: float, elapsed: float) -> np.ndarray:
        """Audio visualizer style interface."""
        # Dark background
        canvas = np.full((SCREEN_HEIGHT, SCREEN_WIDTH, 3), (10, 5, 15), dtype=np.uint8)
        
        center_x = SCREEN_WIDTH // 2
        center_y = SCREEN_HEIGHT // 2
        
        # Circular spectrum
        spectrum_radius = 180
        
        for i in range(self.num_bars):
            angle = (i / self.num_bars) * 2 * np.pi - np.pi / 2
            
            # Start point (inner circle)
            x1 = int(center_x + spectrum_radius * np.cos(angle))
            y1 = int(center_y + spectrum_radius * np.sin(angle))
            
            # End point (outer, based on bar height)
            bar_length = self.bar_heights[i]
            x2 = int(center_x + (spectrum_radius + bar_length) * np.cos(angle))
            y2 = int(center_y + (spectrum_radius + bar_length) * np.sin(angle))
            
            # Color gradient based on position
            color_ratio = i / self.num_bars
            color = (
                int(255 * (1 - color_ratio) + 100 * color_ratio),  # B
                int(200 * (1 - color_ratio) + 100 * color_ratio),  # G
                int(0 * (1 - color_ratio) + 255 * color_ratio)     # R
            )
            
            # Draw bar
            cv2.line(canvas, (x1, y1), (x2, y2), color, 4)
        
        # Inner circle
        cv2.circle(canvas, (center_x, center_y), spectrum_radius, BLUE, 2)
        
        # Central waveform (horizontal)
        wave_y = center_y
        wave_points = []
        for x in range(0, SCREEN_WIDTH, 5):
            y_offset = int(30 * np.sin(x * 0.02 + elapsed * 5))
            wave_points.append([x, wave_y + y_offset])
        
        wave_points = np.array(wave_points, dtype=np.int32)
        cv2.polylines(canvas, [wave_points], False, CYAN, 2)
        
        # Central soul orb
        pulse = 0.8 + 0.2 * np.sin(elapsed * 6) if is_live else 0.3
        orb_radius = int(30 * pulse)
        orb_color = CYAN if is_live else BLUE
        
        for r in range(orb_radius+15, orb_radius, -1):
            alpha = 1.0 - ((r - orb_radius) / 15.0)
            color = tuple(int(c * alpha * 0.7) for c in orb_color)
            cv2.circle(canvas, (center_x, center_y), r, color, -1)
        
        cv2.circle(canvas, (center_x, center_y), orb_radius, WHITE, -1)
        
        # Status
        if is_live:
            text = "RESONANCE DETECTED"
            text_color = CYAN
        else:
            text = "LISTENING..."
            text_color = BLUE
        
        text_size = cv2.getTextSize(text, self.font, 0.8, 2)[0]
        text_x = (SCREEN_WIDTH - text_size[0]) // 2
        cv2.putText(canvas, text, (text_x, SCREEN_HEIGHT - 40),
                   self.font, 0.8, text_color, 2)
        
        # Confidence meter
        meter_y = 50
        meter_width = int(300 * confidence)
        cv2.rectangle(canvas, (center_x-150, meter_y), 
                     (center_x-150+meter_width, meter_y+10), CYAN, -1)
        cv2.rectangle(canvas, (center_x-150, meter_y), 
                     (center_x+150, meter_y+10), BLUE, 2)
        
        return canvas
    
    def run(self):
        print("🎵 Soundwave Scanner - Press 'q' to quit")
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
            
            self.update_bars(is_live, confidence, elapsed)
            display = self.render(is_live, confidence, elapsed)
            
            cv2.imshow("Soundwave Scanner", display)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        self.cap.release()
        self.face_detector.close()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    scanner = SoundwaveScanner()
    scanner.run()




