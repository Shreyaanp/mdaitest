#!/usr/bin/env python3
"""
Interactive Particle Scanner - "Identity of Soul"
- Particles follow your face movement
- Gather at your face position
- Change color based on distance
- React to head tilt/rotation
- NO camera feed shown - pure abstract feedback
"""

import cv2
import numpy as np
import time
import mediapipe as mp
from dataclasses import dataclass
from typing import List, Optional, Tuple

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

# Colors
SOUL_BLUE = (255, 180, 100)      # Cyan-ish
SOUL_PURPLE = (200, 100, 255)    # Purple
SOUL_GOLD = (0, 215, 255)        # Gold
SOUL_WHITE = (255, 255, 255)     # White

@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    target_x: float = 0.0
    target_y: float = 0.0
    energy: float = 1.0

class InteractiveScanner:
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
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # Initialize particles
        self.particles: List[Particle] = []
        for _ in range(400):
            self.particles.append(Particle(
                x=np.random.random() * SCREEN_WIDTH,
                y=np.random.random() * SCREEN_HEIGHT,
                vx=0, vy=0
            ))
        
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.face_center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
        self.face_size = 0.0
        self.head_tilt = 0.0
    
    def update_face_tracking(self, frame: np.ndarray) -> Tuple[Optional[Tuple], float, float]:
        """Track face position and properties WITHOUT displaying it."""
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Detect face
        det_results = self.face_detector.process(rgb)
        mesh_results = self.face_mesh.process(rgb)
        
        if not det_results or not det_results.detections:
            return None, 0.0, 0.0
        
        detection = det_results.detections[0]
        bbox = detection.location_data.relative_bounding_box
        
        h, w = frame.shape[:2]
        
        # Get face center in normalized coords (0-1)
        face_center_norm_x = bbox.xmin + bbox.width / 2
        face_center_norm_y = bbox.ymin + bbox.height / 2
        
        # Map to canvas coordinates
        face_x = int(face_center_norm_x * SCREEN_WIDTH)
        face_y = int(face_center_norm_y * SCREEN_HEIGHT)
        
        # Face size (larger face = closer)
        face_size = (bbox.width + bbox.height) / 2
        
        # Detect head tilt from landmarks
        head_tilt = 0.0
        if mesh_results and mesh_results.multi_face_landmarks:
            landmarks = mesh_results.multi_face_landmarks[0]
            
            # Use left eye (33) and right eye (263) to detect tilt
            left_eye = landmarks.landmark[33]
            right_eye = landmarks.landmark[263]
            
            dy = right_eye.y - left_eye.y
            dx = right_eye.x - left_eye.x
            head_tilt = np.arctan2(dy, dx) if dx != 0 else 0.0
        
        return (face_x, face_y), face_size, head_tilt
    
    def update_particles(self, face_pos: Optional[Tuple], face_size: float, 
                        head_tilt: float, dt: float):
        """Update particles to follow face position."""
        if face_pos:
            target_x, target_y = face_pos
        else:
            # No face - return to center
            target_x, target_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        
        attraction_force = 300.0 if face_pos else 50.0
        
        for p in self.particles:
            # Update target based on face
            p.target_x = target_x + np.random.randn() * (100 * (1 - face_size))
            p.target_y = target_y + np.random.randn() * (100 * (1 - face_size))
            
            # Head tilt affects particle rotation
            if abs(head_tilt) > 0.1:
                angle = head_tilt
                dx = p.x - target_x
                dy = p.y - target_y
                p.target_x = target_x + dx * np.cos(angle * 0.2) - dy * np.sin(angle * 0.2)
                p.target_y = target_y + dx * np.sin(angle * 0.2) + dy * np.cos(angle * 0.2)
            
            # Calculate force to target
            dx = p.target_x - p.x
            dy = p.target_y - p.y
            dist = np.sqrt(dx**2 + dy**2) + 1.0
            
            force = attraction_force / (dist + 10)
            
            # Apply force
            p.vx += (dx / dist) * force * dt
            p.vy += (dy / dist) * force * dt
            
            # Damping
            p.vx *= 0.95
            p.vy *= 0.95
            
            # Update position
            p.x += p.vx * dt * 60
            p.y += p.vy * dt * 60
            
            # Energy based on distance (glow more when near face)
            p.energy = max(0.1, 1.0 - min(dist / 200, 1.0))
    
    def render(self, face_pos: Optional[Tuple], face_size: float, 
              head_tilt: float, confidence: float, elapsed: float) -> np.ndarray:
        """Render interactive particle visualization."""
        # Dark gradient background
        canvas = np.zeros((SCREEN_HEIGHT, SCREEN_WIDTH, 3), dtype=np.uint8)
        
        # Subtle gradient based on face position
        if face_pos:
            fx, fy = face_pos
            for y in range(SCREEN_HEIGHT):
                for x in range(0, SCREEN_WIDTH, 4):  # Sample every 4px for speed
                    dist = np.sqrt((x - fx)**2 + (y - fy)**2)
                    intensity = max(0, int(30 * (1 - dist / 600)))
                    canvas[y, x:x+4] = (intensity, 0, int(intensity * 0.5))
        
        # Draw particles
        for p in self.particles:
            # Color based on energy and position
            if face_pos:
                dist_to_face = np.sqrt((p.x - face_pos[0])**2 + (p.y - face_pos[1])**2)
                
                if dist_to_face < 80:
                    # Core - bright white/gold
                    color = SOUL_WHITE
                    size = 4
                elif dist_to_face < 150:
                    # Middle - cyan
                    alpha = p.energy
                    color = tuple(int(c * alpha) for c in SOUL_BLUE)
                    size = 3
                else:
                    # Outer - purple
                    alpha = p.energy * 0.6
                    color = tuple(int(c * alpha) for c in SOUL_PURPLE)
                    size = 2
            else:
                # No face - dim purple drift
                color = tuple(int(c * 0.3) for c in SOUL_PURPLE)
                size = 2
            
            cv2.circle(canvas, (int(p.x), int(p.y)), size, color, -1)
            
            # Connect nearby particles (soul network)
            if face_pos:
                for p2 in self.particles:
                    if p == p2:
                        continue
                    d = np.sqrt((p.x - p2.x)**2 + (p.y - p2.y)**2)
                    if d < 40:
                        alpha = (1.0 - d / 40) * p.energy * p2.energy * 0.5
                        color = tuple(int(c * alpha) for c in SOUL_BLUE)
                        cv2.line(canvas, (int(p.x), int(p.y)), 
                                (int(p2.x), int(p2.y)), color, 1)
        
        # Draw soul core at face position
        if face_pos:
            fx, fy = face_pos
            pulse = 0.8 + 0.2 * np.sin(elapsed * 4)
            core_radius = int((30 + 50 * face_size) * pulse)
            
            # Layered glow
            for r in range(core_radius+30, core_radius, -2):
                alpha = 1.0 - ((r - core_radius) / 30.0)
                color = tuple(int(c * alpha * 0.7) for c in SOUL_GOLD)
                cv2.circle(canvas, (fx, fy), r, color, -1)
            
            # Core
            cv2.circle(canvas, (fx, fy), core_radius, SOUL_GOLD, -1)
            cv2.circle(canvas, (fx, fy), core_radius+3, SOUL_WHITE, 2)
            
            # Show head tilt with rotation indicator
            if abs(head_tilt) > 0.1:
                indicator_len = 60
                ind_x = int(fx + indicator_len * np.cos(head_tilt))
                ind_y = int(fy + indicator_len * np.sin(head_tilt))
                cv2.line(canvas, (fx, fy), (ind_x, ind_y), SOUL_WHITE, 2)
        
        # Status text
        if face_pos:
            # Show feedback about face properties
            status = f"ESSENCE LOCKED • SIZE: {face_size:.1%} • TILT: {np.degrees(head_tilt):.0f}°"
            text_color = SOUL_GOLD
        else:
            status = "SEARCHING FOR SOUL..."
            text_color = SOUL_PURPLE
        
        text_size = cv2.getTextSize(status, self.font, 0.6, 2)[0]
        text_x = (SCREEN_WIDTH - text_size[0]) // 2
        cv2.putText(canvas, status, (text_x, SCREEN_HEIGHT - 40),
                   self.font, 0.6, text_color, 2)
        
        # Particle count in soul
        if face_pos:
            gathered = sum(1 for p in self.particles 
                          if np.sqrt((p.x - face_pos[0])**2 + (p.y - face_pos[1])**2) < 100)
            cv2.putText(canvas, f"PARTICLES: {gathered}/400", (30, SCREEN_HEIGHT - 40),
                       self.font, 0.5, SOUL_BLUE, 1)
        
        return canvas
    
    def run(self):
        print("✨ Interactive Particle Scanner - Identity of Soul")
        print("Press 'q' to quit")
        print("\nTry:")
        print("  • Move your head left/right (particles follow)")
        print("  • Move closer/farther (particle density changes)")
        print("  • Tilt your head (particles rotate)")
        print("  • Move away (particles disperse)")
        
        start_time = time.time()
        last_frame_time = start_time
        
        while True:
            ret, frame = self.cap.read()
            if not ret:
                print("Failed to grab frame")
                break
            
            current_time = time.time()
            dt = min(current_time - last_frame_time, 0.1)  # Cap dt for stability
            last_frame_time = current_time
            elapsed = current_time - start_time
            
            # Track face (but don't display it!)
            face_pos, face_size, head_tilt = self.update_face_tracking(frame)
            
            # Update particles based on face feedback
            self.update_particles(face_pos, face_size, head_tilt, dt)
            
            # Render abstract visualization
            display = self.render(face_pos, face_size, head_tilt, 1.0, elapsed)
            
            cv2.imshow("Identity of Soul - Interactive", display)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        self.cap.release()
        self.face_detector.close()
        self.face_mesh.close()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    scanner = InteractiveScanner()
    scanner.run()





