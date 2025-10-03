"""
Eye of Horus Tracking Visualization
Extracts eye landmarks from MediaPipe and renders Eye of Ra/Horus design
"""

import cv2
import numpy as np
from typing import Optional, Tuple, List
from dataclasses import dataclass

# MediaPipe face mesh landmark indices for eyes
# LEFT_EYE: 33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246
# RIGHT_EYE: 362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398
LEFT_EYE_INDICES = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
RIGHT_EYE_INDICES = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]

# Simplified eye contour indices for drawing
LEFT_EYE_CONTOUR = [33, 160, 158, 133, 153, 144, 163, 7]
RIGHT_EYE_CONTOUR = [362, 385, 387, 263, 373, 380, 381, 382]

# Iris/pupil approximation
LEFT_IRIS_CENTER = 468  # Left iris center landmark
RIGHT_IRIS_CENTER = 468  # Right iris center landmark

# Eye of Horus colors (Crisp Silver theme)
GOLD = (200, 200, 200)  # Brighter silver for visibility in BGR format
DARK_GOLD = (120, 120, 120)  # Medium gray
ACCENT = (240, 240, 240)  # Very light silver accent
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)


@dataclass
class EyeData:
    """Stores extracted eye landmark data."""
    left_eye_points: List[Tuple[int, int]]
    right_eye_points: List[Tuple[int, int]]
    left_center: Tuple[int, int]
    right_center: Tuple[int, int]
    face_detected: bool


class EyeOfHorusRenderer:
    """Renders Eye of Horus/Ra design based on tracked eye landmarks."""
    
    def __init__(self, width: int = 640, height: int = 480, *, mirror_input: bool = False):
        self.width = width
        self.height = height
        self.animation_phase = 0.0  # For pulsing effects
        self.animation_speed = 0.05  # Controls breathing cadence
        self.breath_amplitude = 0.12  # Scale modulation for breathing
        self.mirror_input = mirror_input
        
        # Smoothing for movement (exponential moving average)
        self.smooth_center_x = width // 2
        self.smooth_center_y = height // 2
        self.smoothing_factor = 0.6  # Lower = smoother but slower response
        
        # Fixed eye spacing
        self.eye_spacing = 180  # Fixed distance between eyes
        self.eye_size = 130  # Size of each eye
        
        # State smoothing to prevent flickering
        self.face_detected_frames = 0  # Count consecutive frames with face
        self.no_face_frames = 0  # Count consecutive frames without face
        self.smooth_state = "searching"  # "searching" or "scanning"
        self.state_change_threshold = 3  # Need 3 consecutive frames to change state
        self.fade_alpha = 0.0  # For smooth fade transitions (0.0 = invisible, 1.0 = visible)
        
    def extract_eye_landmarks(self, face_landmarks, image_width: int, image_height: int) -> Optional[EyeData]:
        """Extract eye coordinates from MediaPipe face mesh."""
        if not face_landmarks:
            return None
        
        try:
            # Convert normalized landmarks to pixel coordinates
            def to_pixel(idx: int) -> Tuple[int, int]:
                landmark = face_landmarks.landmark[idx]
                px = int(landmark.x * image_width)
                py = int(landmark.y * image_height)
                if self.mirror_input:
                    px = (image_width - 1) - px
                return px, py

            left_eye_points = [to_pixel(idx) for idx in LEFT_EYE_CONTOUR]
            right_eye_points = [to_pixel(idx) for idx in RIGHT_EYE_CONTOUR]
            
            # Get eye centers (use iris centers if available, else compute from contour)
            if len(face_landmarks.landmark) > 468:
                left_center = to_pixel(LEFT_IRIS_CENTER)
                right_center = to_pixel(RIGHT_IRIS_CENTER)
            else:
                # Fallback: compute center from contour
                left_center = tuple(np.mean(left_eye_points, axis=0).astype(int))
                right_center = tuple(np.mean(right_eye_points, axis=0).astype(int))
            
            return EyeData(
                left_eye_points=left_eye_points,
                right_eye_points=right_eye_points,
                left_center=left_center,
                right_center=right_center,
                face_detected=True
            )
        except Exception as e:
            print(f"Error extracting eye landmarks: {e}")
            return None
    
    def create_eye_data_from_precomputed(self, eye_landmarks: dict, image_width: int) -> Optional[EyeData]:
        """
        Create EyeData from pre-extracted eye landmarks (optimization to avoid duplicate MediaPipe).
        
        Args:
            eye_landmarks: Dict with "left_eye", "right_eye", "left_center", "right_center"
            image_width: Image width for mirror calculation
        
        Returns:
            EyeData object ready for rendering
        """
        if not eye_landmarks:
            return None
        
        try:
            left_eye = eye_landmarks["left_eye"]
            right_eye = eye_landmarks["right_eye"]
            left_center = eye_landmarks["left_center"]
            right_center = eye_landmarks["right_center"]
            
            # Apply mirroring if needed
            if self.mirror_input:
                left_eye = [((image_width - 1) - x, y) for x, y in left_eye]
                right_eye = [((image_width - 1) - x, y) for x, y in right_eye]
                left_center = ((image_width - 1) - left_center[0], left_center[1])
                right_center = ((image_width - 1) - right_center[0], right_center[1])
            
            return EyeData(
                left_eye_points=left_eye,
                right_eye_points=right_eye,
                left_center=left_center,
                right_center=right_center,
                face_detected=True
            )
        except Exception as e:
            print(f"Error creating EyeData from precomputed landmarks: {e}")
            return None
    
    def draw_eye_of_horus(
        self, 
        canvas: np.ndarray, 
        center: Tuple[int, int], 
        is_left: bool = True
    ):
        """Draw Eye of Horus design - large, stylized version."""
        x, y = center
        # Breathing modulation keeps proportions fluid without jitter
        breath = 1.0 + self.breath_amplitude * np.sin(self.animation_phase)
        scale = (self.eye_size / 100) * breath  # Scale factor for 300px eyes
        pulse_wave = (np.sin(self.animation_phase) + 1.0) * 0.5  # 0 → 1

        # Subtle pulsing glow effect aligned with breathing
        glow_radius = int(80 * scale + 18 * pulse_wave)
        glow_alpha = 0.06 + 0.08 * pulse_wave
        overlay = canvas.copy()
        cv2.circle(overlay, center, glow_radius, ACCENT, -1)
        cv2.addWeighted(overlay, glow_alpha, canvas, 1 - glow_alpha, 0, canvas)
        
        # Main eye almond shape (THICKER for sharper lines)
        eye_width = int(60 * scale)
        eye_height = int(30 * scale)
        line_thickness = max(3, int(5 * breath))
        
        # Draw almond eye shape with thick crisp line
        ellipse_center = (x, y)
        axes = (eye_width, eye_height)
        cv2.ellipse(canvas, ellipse_center, axes, 0, 0, 360, GOLD, line_thickness, cv2.LINE_AA)
        
        # Pupil/iris circle (large and prominent) - THICKER lines
        iris_radius = int(35 * scale)
        cv2.circle(canvas, center, iris_radius, DARK_GOLD, -1)
        cv2.circle(canvas, center, iris_radius, GOLD, max(3, int(4 * breath)))
        cv2.circle(canvas, center, int(iris_radius * 0.6), BLACK, -1)
        cv2.circle(canvas, center, int(iris_radius * 0.4), ACCENT, -1)
        
        # Eye of Horus decorative elements
        # Bottom decorative line (tear drop)
        # Compute intersection point between almond eye (ellipse) and iris (large circle) at the *bottom*.
        # This is where the ellipse and the circle meet at the lowest y (bottom of the eye).
        #
        # The ellipse is centered at (x, y) with axes (eye_width, eye_height)
        # The iris is a circle centered at (x, y) with radius iris_radius
        # The bottom point of both is at angle theta = pi/2 (90 deg, downward)
        #
        # For both left and right eye, the intersection at the bottom is:
        angle = np.pi / 2  # 90 degrees, downward
        # Ellipse point at bottom
        ellipse_bottom_x = int(6+x + eye_width * np.cos(angle))
        ellipse_bottom_y = int(6+y + eye_height * np.sin(angle))
        # Circle point at bottom
        circle_bottom_x = int(6+x + iris_radius * np.cos(angle))
        circle_bottom_y = int(6+y + iris_radius * np.sin(angle))
        # The intersection is where the almond and the circle meet at the bottom.
        # For a stylized effect, use the midpoint between the two bottoms.
        intersect_x = int((ellipse_bottom_x + circle_bottom_x) / 2)
        intersect_y = int((ellipse_bottom_y + circle_bottom_y) / 2)

        # Now, draw the tear curve and end, slanted at 30 degrees away from vertical
        # For left eye, slant to the left; for right eye, slant to the right
        slant_angle = np.pi / 2 + (np.deg2rad(60) if is_left else np.deg2rad(-60))
        # First control point (curve)
        tear_curve_x = int(intersect_x + 15 * scale * np.cos(slant_angle))
        tear_curve_y = int(intersect_y + 30 * scale * np.sin(slant_angle))
        # End point
        tear_end_x = int(intersect_x + 30 * scale * np.cos(slant_angle))
        tear_end_y = int(intersect_y + 60 * scale * np.sin(slant_angle))
        tear_curve = (tear_curve_x, tear_curve_y)
        tear_end = (tear_end_x, tear_end_y)

        # Draw tear line starting from intersection point - THICKER for sharpness
        cv2.line(canvas, (intersect_x, intersect_y), tear_curve, GOLD, line_thickness, cv2.LINE_AA)
        cv2.line(canvas, tear_curve, tear_end, GOLD, line_thickness, cv2.LINE_AA)
        
        # Spiral at end of tear (Ra symbol) - THICKER outline
        spiral_radius = int(12 * scale)
        cv2.circle(canvas, tear_end, spiral_radius, DARK_GOLD, -1)
        cv2.circle(canvas, tear_end, spiral_radius, GOLD, max(3, int(4 * breath)))
        
        # Top eyebrow arc - THICKER line
        eyebrow_start = (x - eye_width, y - int(25 * scale))
        eyebrow_end = (x + eye_width, y - int(25 * scale))
        eyebrow_peak = (x, y - int(45 * scale))
        
        pts = np.array([eyebrow_start, eyebrow_peak, eyebrow_end], dtype=np.int32)
        cv2.polylines(canvas, [pts], False, GOLD, line_thickness, cv2.LINE_AA)
        
        # Add inner eye detail lines (Egyptian style) - THICKER
        # Inner corner accent
        corner_offset = int(20 * scale)
        if is_left:
            cv2.line(canvas, (x - corner_offset, y), (x - corner_offset - 10, y + 5), GOLD, max(2, int(3 * breath)), cv2.LINE_AA)
        else:
            cv2.line(canvas, (x + corner_offset, y), (x + corner_offset + 10, y + 5), GOLD, max(2, int(3 * breath)), cv2.LINE_AA)
    
    def render(self, eye_data: Optional[EyeData], show_guide: bool = True, progress: float = 0.0) -> np.ndarray:
        """
        Render Eye of Horus with smooth state transitions and progress bar.
        
        Args:
            eye_data: Detected eye landmarks (None if no face)
            show_guide: Whether to show text/progress (default True)
            progress: Validation progress 0.0-1.0 (0-10 frames collected)
        """
        # Create black canvas
        canvas = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Update animation phase (slow breathing cadence)
        self.animation_phase += self.animation_speed
        if self.animation_phase > 2 * np.pi:
            self.animation_phase = 0.0
        
        # State smoothing to prevent flickering
        face_detected = eye_data is not None and eye_data.face_detected
        
        if face_detected:
            self.face_detected_frames += 1
            self.no_face_frames = 0
        else:
            self.no_face_frames += 1
            self.face_detected_frames = 0
        
        # Change state only after threshold consecutive frames
        if self.face_detected_frames >= self.state_change_threshold:
            self.smooth_state = "scanning"
        elif self.no_face_frames >= self.state_change_threshold:
            self.smooth_state = "searching"
        
        # Smooth fade transition (~0.6s at 30fps for softer entry/exit)
        fade_speed = 0.05  # Adjust per frame
        if self.smooth_state == "scanning":
            self.fade_alpha = min(1.0, self.fade_alpha + fade_speed)
        else:
            self.fade_alpha = max(0.0, self.fade_alpha - fade_speed)
        
        # SEARCHING STATE: No face detected
        if self.smooth_state == "searching":
            center_x = self.width // 2
            center_y = self.height // 2 - 40  # Slightly higher for text below
            
            # Reset smoothing to center when searching
            self.smooth_center_x = center_x
            self.smooth_center_y = center_y
            
            # Draw faint ghost eyes
            half_spacing = self.eye_spacing // 2
            left_eye_pos = (center_x - half_spacing, center_y)
            right_eye_pos = (center_x + half_spacing, center_y)
            
            overlay = canvas.copy()
            self.draw_eye_of_horus(overlay, left_eye_pos, is_left=True)
            self.draw_eye_of_horus(overlay, right_eye_pos, is_left=False)
            cv2.addWeighted(overlay, 0.25, canvas, 0.75, 0, canvas)
            
            # Text: "looking for face..."
            text1 = "looking for face..."
            font = cv2.FONT_HERSHEY_SIMPLEX
            text_size1 = cv2.getTextSize(text1, font, 0.9, 2)[0]
            text1_x = (self.width - text_size1[0]) // 2
            text1_y = self.height - 120
            cv2.putText(canvas, text1, (text1_x, text1_y), font, 0.9, GOLD, 2, cv2.LINE_AA)
            
            # Text: "adjust your position"
            text2 = "adjust your position"
            text_size2 = cv2.getTextSize(text2, font, 0.7, 2)[0]
            text2_x = (self.width - text_size2[0]) // 2
            text2_y = self.height - 80
            cv2.putText(canvas, text2, (text2_x, text2_y), font, 0.7, (160, 160, 160), 2, cv2.LINE_AA)
            
            return canvas
        
        # SCANNING STATE: Face detected
        # Safety check: eye_data might be None during state transition
        if not eye_data or not eye_data.face_detected:
            # Edge case: smooth_state is "scanning" but no eye_data yet
            return canvas
        
        # Calculate center point between the two real eyes
        target_center_x = (eye_data.left_center[0] + eye_data.right_center[0]) // 2
        target_center_y = (eye_data.left_center[1] + eye_data.right_center[1]) // 2
        
        # Apply smoothing (exponential moving average)
        self.smooth_center_x += (target_center_x - self.smooth_center_x) * self.smoothing_factor
        self.smooth_center_y += (target_center_y - self.smooth_center_y) * self.smoothing_factor
        
        # Calculate fixed positions for both eyes
        half_spacing = self.eye_spacing // 2
        left_eye_pos = (int(self.smooth_center_x - half_spacing), int(self.smooth_center_y))
        right_eye_pos = (int(self.smooth_center_x + half_spacing), int(self.smooth_center_y))
        
        # Draw eyes on overlay for fade effect
        eye_overlay = canvas.copy()
        self.draw_eye_of_horus(eye_overlay, left_eye_pos, is_left=True)
        self.draw_eye_of_horus(eye_overlay, right_eye_pos, is_left=False)
        
        # Subtle connection line
        cv2.line(eye_overlay, left_eye_pos, right_eye_pos, DARK_GOLD, 2, cv2.LINE_AA)
        
        # Third eye (center chakra)
        third_eye_pos = (int(self.smooth_center_x), int(self.smooth_center_y))
        cv2.circle(eye_overlay, third_eye_pos, 6, ACCENT, -1)
        cv2.circle(eye_overlay, third_eye_pos, 8, GOLD, 3)
        
        # Apply fade alpha for smooth transition
        cv2.addWeighted(eye_overlay, self.fade_alpha, canvas, 1 - self.fade_alpha, 0, canvas)
        
        # Progress bar (only when scanning and progress > 0)
        if show_guide and progress > 0:
            self._draw_progress_bar(canvas, progress)
        
        return canvas
    
    def _draw_progress_bar(self, canvas: np.ndarray, progress: float):
        """Draw progress bar showing validation progress (0.0 - 1.0)."""
        bar_width = 300
        bar_height = 6
        bar_x = (self.width - bar_width) // 2
        bar_y = self.height - 70
        
        # Background bar (dark)
        cv2.rectangle(canvas, (bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height), 
                     DARK_GOLD, -1)
        cv2.rectangle(canvas, (bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height), 
                     GOLD, 1)
        
        # Filled progress (silver/gold)
        filled_width = int(bar_width * min(1.0, max(0.0, progress)))
        if filled_width > 0:
            cv2.rectangle(canvas, (bar_x, bar_y), (bar_x + filled_width, bar_y + bar_height), 
                         GOLD, -1)
            
            # Add glow to progress bar
            glow_overlay = canvas.copy()
            cv2.rectangle(glow_overlay, (bar_x, bar_y - 2), (bar_x + filled_width, bar_y + bar_height + 2), 
                         ACCENT, -1)
            cv2.addWeighted(glow_overlay, 0.2, canvas, 0.8, 0, canvas)
        
        # Progress text (percentage)
        percent_text = f"{int(progress * 100)}%"
        font = cv2.FONT_HERSHEY_SIMPLEX
        text_size = cv2.getTextSize(percent_text, font, 0.5, 1)[0]
        text_x = (self.width - text_size[0]) // 2
        text_y = bar_y - 15
        cv2.putText(canvas, percent_text, (text_x, text_y), font, 0.5, GOLD, 1, cv2.LINE_AA)
    
    def render_from_mesh_result(self, mesh_result, image_width: int, image_height: int, progress: float = 0.0) -> np.ndarray:
        """Convenience method: extract and render in one call."""
        if mesh_result and mesh_result.multi_face_landmarks:
            face_landmarks = mesh_result.multi_face_landmarks[0]
            eye_data = self.extract_eye_landmarks(face_landmarks, image_width, image_height)
        else:
            eye_data = None
        
        return self.render(eye_data, show_guide=True, progress=progress)


def create_eye_tracking_frame(mesh_result, width: int = 640, height: int = 480) -> np.ndarray:
    """
    Convenience function to create eye tracking visualization frame.
    
    Args:
        mesh_result: MediaPipe face mesh result
        width: Output frame width
        height: Output frame height
    
    Returns:
        BGR image with Eye of Horus visualization
    """
    renderer = EyeOfHorusRenderer(width, height)
    return renderer.render_from_mesh_result(mesh_result, width, height)
