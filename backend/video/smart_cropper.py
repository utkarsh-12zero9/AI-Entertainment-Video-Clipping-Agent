"""Intelligent face-aware 9:16 reframing and horizontal crop calculator."""

from pathlib import Path
from typing import List, Optional, Tuple
import cv2
import numpy as np

from backend.config.settings import PipelineSettings, get_settings
from backend.models.editing import CropWindow
from backend.utils.logger import get_logger

logger = get_logger("smart_cropper")


class SmartCropper:
    """Calculates intelligent 9:16 vertical crop windows targeting active subjects and faces."""

    def __init__(self, settings: Optional[PipelineSettings] = None):
        self.settings = settings or get_settings()
        self._cascade: Optional[cv2.CascadeClassifier] = None
        self._init_cascade()

    def _init_cascade(self) -> None:
        """Initializes OpenCV Haar cascade face detector with defensive fallback."""
        try:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            if Path(cascade_path).exists():
                self._cascade = cv2.CascadeClassifier(cascade_path)
        except Exception as e:
            logger.warning(f"Could not load OpenCV Haar cascade: {e}. Falling back to center crop.")
            self._cascade = None

    def calculate_crop(
        self,
        video_path: Path,
        original_width: int,
        original_height: int,
        strategy: Optional[str] = None,
    ) -> CropWindow:
        """Calculate optimal 9:16 crop window for a raw video clip.

        When scaled to target height (1920), original width scales proportionally to:
            scaled_w = round(original_width * (1920 / original_height))
        The horizontal 9:16 crop window of width 1080 is then positioned at:
            X in [0, max(0, scaled_w - 1080)]

        Args:
            video_path: Path to the raw clip file.
            original_width: Original clip width in pixels.
            original_height: Original clip height in pixels.
            strategy: Optional override ('smart_face' or 'center').

        Returns:
            CropWindow with x, y, width, height, and strategy metadata.
        """
        strat = strategy or self.settings.reframing_strategy
        target_h = self.settings.target_vertical_height  # 1920
        target_w = self.settings.target_vertical_width   # 1080

        # Calculate proportional scaled width
        scale_factor = target_h / max(1, original_height)
        scaled_w = int(round(original_width * scale_factor))
        max_x = max(0, scaled_w - target_w)

        # Default center crop
        center_x = max_x // 2

        if strat == "center" or not self._cascade or max_x == 0:
            return CropWindow(
                x=center_x,
                y=0,
                width=target_w,
                height=target_h,
                strategy_used="center",
                detected_faces=0,
            )

        # Sample frames from video to locate faces
        face_x_centers: List[float] = []
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return CropWindow(
                x=center_x,
                y=0,
                width=target_w,
                height=target_h,
                strategy_used="center",
                detected_faces=0,
            )

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        sample_step = max(1, total_frames // 10)  # sample ~10 frames

        frame_idx = 0
        while cap.isOpened() and frame_idx < total_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self._cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=4,
                minSize=(30, 30),
            )

            for (fx, fy, fw, fh) in faces:
                # Face center in original coordinates
                face_center_x = fx + (fw / 2.0)
                # Map to scaled coordinates
                scaled_face_center_x = face_center_x * scale_factor
                face_x_centers.append(scaled_face_center_x)

            frame_idx += sample_step

        cap.release()

        if not face_x_centers:
            # No faces detected, fallback to center crop
            return CropWindow(
                x=center_x,
                y=0,
                width=target_w,
                height=target_h,
                strategy_used="center",
                detected_faces=0,
            )

        # Robust median horizontal face center to avoid outlier jumps
        median_face_x = float(np.median(face_x_centers))

        # Position 1080 crop window centered on median face
        ideal_x = int(round(median_face_x - (target_w / 2.0)))
        clamped_x = max(0, min(max_x, ideal_x))

        logger.info(
            f"Smart face reframing for {video_path.name}: detected {len(face_x_centers)} face instances, "
            f"median X={median_face_x:.1f}px, crop X={clamped_x}px (max_x={max_x}px)"
        )

        return CropWindow(
            x=clamped_x,
            y=0,
            width=target_w,
            height=target_h,
            strategy_used="smart_face",
            detected_faces=len(face_x_centers),
        )
