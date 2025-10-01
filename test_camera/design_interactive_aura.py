#!/usr/bin/env python3
"""
Interactive Soul Aura Scanner
- Aura rings follow face position
- Ring size based on face distance
- Ring color based on face expression (smile detection)
- Ripples when you move quickly
- NO camera feed - just soul energy visualization
"""

import cv2
import numpy as np
import time
import mediapipe as mp
from collections import deque
from typing import Optional, Tuple

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

class AuraScanner:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        self.face_detector = mp.solutions.face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=0.5
        )
        
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=False,
            min_detection_confidence=0.5
        )
        
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        
        # Tracking
        self.position_history = deque(maxlen=10)
        self.face_pos = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        self.face_size = 0.3
        self.ripples = []  # [(x, y, radius, alpha), ...]
        self.soul_energy = 0.0
    
    def detect_movement_speed(self) -> float:
        """Calculate how fast the face is moving."""
        if len(self.position_history) < 2:
            return 0.0
        
        total_dist = 0.0
        for i in range(1, len(self.position_history)):
            dx = self.position_history[i][0] - self.position_history[i-1][0]
            dy = self.position_history[i][1] - self.position_history[i-1][1]
            total_dist += np.sqrt(dx**2 + dy**2)
        
        return total_dist / len(self.position_history)
    
    def update_tracking(self, frame: np.ndarray):
        """Update face tracking."""
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        det_results = self.face_detector.process(rgb)
        mesh_results = self.face_mesh.process(rgb)
        
        if det_results and det_results.detections:
            det = det_results.detections[0]
            bbox = det.location_data.relative_bounding_box
            
            # Map face center to screen
            face_x = int((bbox.xmin + bbox.width / 2) * SCREEN_WIDTH)
            face_y = int((bbox.ymin + bbox.height / 2) * SCREEN_HEIGHT)
            
            # Smooth position (ease in)
            self.face_pos = (
                int(self.face_pos[0] * 0.7 + face_x * 0.3),
                int(self.face_pos[1] * 0.7 + face_y * 0.3)
            )
            
            self.position_history.append(self.face_pos)
            
            # Face size
            self.face_size = (bbox.width + bbox.height) / 2
            
            # Detect smile (mouth corners up)
            smile_detected = False
            if mesh_results and mesh_results.multi_face_landmarks:
                landmarks = mesh_results.multi_face_landmarks[0]
                mouth_left = landmarks.landmark[61].y
                mouth_right = landmarks.landmark[291].y
                mouth_top = landmarks.landmark[13].y
                
                # Smiling if corners higher than top
                smile_detected = (mouth_left + mouth_right) / 2 < mouth_top
            
            # Energy increases when smiling
            target_energy = 1.0 if smile_detected else 0.5
            self.soul_energy += (target_energy - self.soul_energy) * 0.1
            
            # Create ripple on fast movement
            speed = self.detect_movement_speed()
            if speed > 15:
                self.ripples.append([self.face_pos[0], self.face_pos[1], 0, 1.0])
    
    def render(self, elapsed: float) -> np.ndarray:
        """Render soul aura visualization."""
        # Deep indigo background
        canvas = np.full((SCREEN_HEIGHT, SCREEN_WIDTH, 3), (60, 20, 10), dtype=np.uint8)
        
        fx, fy = self.face_pos
        
        # Background particle field (subtle)
        for _ in range(50):
            x = np.random.randint(0, SCREEN_WIDTH)
            y = np.random.randint(0, SCREEN_HEIGHT)
            dist = np.sqrt((x - fx)**2 + (y - fy)**2)
            if dist < 300:
                alpha = 0.3 * (1 - dist / 300)
                color = (int(100 * alpha), int(150 * alpha), int(255 * alpha))
                cv2.circle(canvas, (x, y), 1, color, -1)
        
        # Soul aura - concentric rings
        base_radius = 60 + 100 * self.face_size
        num_rings = 8
        
        for i in range(num_rings):
            pulse_offset = elapsed * 2 + i * 0.5
            pulse = 0.9 + 0.1 * np.sin(pulse_offset)
            
            radius = int((base_radius + i * 25) * pulse)
            alpha = (1.0 - i / num_rings) * self.soul_energy
            
            # Color gradient from center (gold) to outer (purple)
            ratio = i / num_rings
            color = (
                int((255 * (1-ratio) + 200 * ratio) * alpha),  # B
                int((215 * (1-ratio) + 100 * ratio) * alpha),  # G
                int((0 * (1-ratio) + 255 * ratio) * alpha)     # R
            )
            
            cv2.circle(canvas, (fx, fy), radius, color, 2)
        
        # Update and draw ripples (from fast movement)
        new_ripples = []
        for ripple in self.ripples:
            x, y, r, alpha = ripple
            r += 5
            alpha -= 0.05
            
            if alpha > 0:
                color = tuple(int(c * alpha) for c in (255, 200, 100))
                cv2.circle(canvas, (int(x), int(y)), int(r), color, 2)
                new_ripples.append([x, y, r, alpha])
        
        self.ripples = new_ripples
        
        # Central soul core
        core_pulse = 0.7 + 0.3 * np.sin(elapsed * 5) * self.soul_energy
        core_radius = int(35 * core_pulse)
        
        # Glow layers
        for r in range(core_radius+25, core_radius, -1):
            alpha = 1.0 - ((r - core_radius) / 25.0)
            color = tuple(int(c * alpha * 0.8) for c in (0, 215, 255))
            cv2.circle(canvas, (fx, fy), r, color, -1)
        
        # Bright core
        cv2.circle(canvas, (fx, fy), core_radius, (255, 255, 255), -1)
        
        # Energy level indicator
        energy_bars = int(self.soul_energy * 10)
        bar_text = "█" * energy_bars + "░" * (10 - energy_bars)
        cv2.putText(canvas, f"SOUL ENERGY: {bar_text}", (30, 50),
                   self.font, 0.6, (0, 215, 255), 2)
        
        # Status
        if self.soul_energy > 0.7:
            status = "SOUL RESONATING"
            color = (0, 255, 255)
        elif self.face_size > 0.3:
            status = "ESSENCE DETECTED"
            color = (0, 215, 255)
        else:
            status = "SEEKING PRESENCE..."
            color = (200, 100, 255)
        
        text_size = cv2.getTextSize(status, self.font, 0.8, 2)[0]
        text_x = (SCREEN_WIDTH - text_size[0]) // 2
        cv2.putText(canvas, status, (text_x, SCREEN_HEIGHT - 40),
                   self.font, 0.8, color, 2)
        
        return canvas
    
    def run(self):
        print("🌊 Interactive Aura Scanner - Identity of Soul")
        print("Press 'q' to quit")
        print("\nYour movements create soul energy:")
        print("  • Move around → aura follows you")
        print("  • Move closer → aura grows")  
        print("  • Move quickly → creates ripples")
        print("  • Smile → increases soul energy!")
        
        start_time = time.time()
        last_frame_time = start_time
        
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            
            current_time = time.time()
            dt = min(current_time - last_frame_time, 0.1)
            last_frame_time = current_time
            elapsed = current_time - start_time
            
            # Update face tracking
            self.update_tracking(frame)
            
            # Render
            display = self.render(elapsed)
            
            cv2.imshow("Soul Aura Scanner", display)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        self.cap.release()
        self.face_detector.close()
        self.face_mesh.close()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    scanner = AuraScanner()
    scanner.run()





