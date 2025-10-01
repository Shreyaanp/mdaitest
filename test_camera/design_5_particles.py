#!/usr/bin/env python3
"""
Design 5: Particle Field
- Hundreds of particles
- Gather to form essence
- Flow physics simulation
- Ethereal, mystical
"""

import cv2
import numpy as np
import time
import mediapipe as mp
from dataclasses import dataclass
from typing import List

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    age: float = 0.0

class ParticleScanner:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        
        self.face_detector = mp.solutions.face_detection.FaceDetection(
            model_selection=0, min_detection_confidence=0.5
        )
        
        # Initialize particles
        self.particles: List[Particle] = []
        for _ in range(300):
            self.particles.append(Particle(
                x=np.random.random() * SCREEN_WIDTH,
                y=np.random.random() * SCREEN_HEIGHT,
                vx=np.random.randn() * 0.5,
                vy=np.random.randn() * 0.5
            ))
    
    def update_particles(self, is_live: bool, dt: float):
        """Update particle physics."""
        center_x = SCREEN_WIDTH // 2
        center_y = SCREEN_HEIGHT // 2
        
        for p in self.particles:
            if is_live:
                # Attract to center (soul detected)
                dx = center_x - p.x
                dy = center_y - p.y
                dist = np.sqrt(dx**2 + dy**2) + 0.1
                
                force = 200.0 / (dist + 1)
                p.vx += (dx / dist) * force * dt
                p.vy += (dy / dist) * force * dt
            else:
                # Random drift (searching)
                p.vx += np.random.randn() * 2 * dt
                p.vy += np.random.randn() * 2 * dt
            
            # Damping
            p.vx *= 0.98
            p.vy *= 0.98
            
            # Update position
            p.x += p.vx * dt * 60
            p.y += p.vy * dt * 60
            
            # Wrap around screen
            if p.x < 0: p.x += SCREEN_WIDTH
            if p.x > SCREEN_WIDTH: p.x -= SCREEN_WIDTH
            if p.y < 0: p.y += SCREEN_HEIGHT
            if p.y > SCREEN_HEIGHT: p.y -= SCREEN_HEIGHT
            
            p.age += dt
    
    def render(self, is_live: bool, elapsed: float) -> np.ndarray:
        """Particle field visualization."""
        canvas = np.zeros((SCREEN_HEIGHT, SCREEN_WIDTH, 3), dtype=np.uint8)
        
        center_x = SCREEN_WIDTH // 2
        center_y = SCREEN_HEIGHT // 2
        
        # Draw particles
        for p in self.particles:
            # Distance from center affects color
            dist = np.sqrt((p.x - center_x)**2 + (p.y - center_y)**2)
            
            if is_live:
                # Cyan to white gradient (soul gathering)
                if dist < 100:
                    color = (255, 255, 200)  # Bright white-cyan
                else:
                    alpha = 1.0 - min(dist / 400, 1.0)
                    color = (int(255 * alpha), int(255 * alpha), int(180 * alpha))
            else:
                # Purple to blue (searching)
                alpha = 1.0 - min(dist / 400, 1.0)
                color = (int(200 * alpha), int(100 * alpha), int(150 * alpha))
            
            # Draw particle
            size = 3 if dist < 150 else 2
            cv2.circle(canvas, (int(p.x), int(p.y)), size, color, -1)
            
            # Connect nearby particles
            for p2 in self.particles:
                if p == p2:
                    continue
                d = np.sqrt((p.x - p2.x)**2 + (p.y - p2.y)**2)
                if d < 50 and is_live:
                    alpha = 1.0 - (d / 50)
                    color = tuple(int(c * alpha * 0.3) for c in (255, 255, 200))
                    cv2.line(canvas, (int(p.x), int(p.y)), (int(p2.x), int(p2.y)), 
                            color, 1)
        
        # Central soul core (when detected)
        if is_live:
            pulse = 0.8 + 0.2 * np.sin(elapsed * 5)
            core_radius = int(35 * pulse)
            
            for r in range(core_radius+20, 0, -2):
                alpha = r / (core_radius + 20)
                color = (int(255 * alpha), int(255 * alpha), int(220 * alpha))
                cv2.circle(canvas, (center_x, center_y), r, color, -1)
            
            # Status
            cv2.putText(canvas, "SOUL ESSENCE GATHERED", (center_x-140, SCREEN_HEIGHT-40),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 255, 255), 2)
        
        return canvas
    
    def run(self):
        print("✨ Particle Scanner - Press 'q' to quit")
        start_time = time.time()
        last_frame_time = start_time
        
        while True:
            ret, frame = self.cap.read()
            if not ret:
                break
            
            current_time = time.time()
            dt = current_time - last_frame_time
            last_frame_time = current_time
            elapsed = current_time - start_time
            
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.face_detector.process(rgb)
            
            is_live = results.detections is not None and len(results.detections) > 0
            
            self.update_particles(is_live, dt)
            display = self.render(is_live, elapsed)
            
            cv2.imshow("Particle Scanner", display)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        self.cap.release()
        self.face_detector.close()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    scanner = ParticleScanner()
    scanner.run()


