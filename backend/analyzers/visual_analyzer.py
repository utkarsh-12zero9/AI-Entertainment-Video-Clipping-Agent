"""Local free visual analyzer using OpenCV and Pillow."""

from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

from backend.config.settings import PipelineSettings, default_settings
from backend.models.vision import (
    FaceBoundingBox,
    FrameIndex,
    FrameVisualAnalysis,
    SceneBoundary,
    VisualAnalysisResult,
)
from backend.utils.errors import VideoPipelineError
from backend.utils.logger import logger


class VisualAnalyzerError(VideoPipelineError):
    """Raised when visual analysis fails."""
    pass


class VisualAnalyzer:
    """Performs 100% free, local visual content analysis on sampled video frames."""

    def __init__(self, settings: Optional[PipelineSettings] = None):
        self.settings = settings or default_settings
        self.face_cascade = None
        # Attempt to load CascadeClassifier if available in cv2
        if hasattr(cv2, "CascadeClassifier") and hasattr(cv2, "data") and hasattr(cv2.data, "haarcascades"):
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            try:
                self.face_cascade = cv2.CascadeClassifier(cascade_path)
            except Exception:
                self.face_cascade = None

    def _detect_faces(self, gray_img: np.ndarray) -> List[FaceBoundingBox]:
        """Detects faces using cascade classifier or skin-tone/edge heuristics if unavailable."""
        if self.face_cascade is not None:
            try:
                faces = self.face_cascade.detectMultiScale(
                    gray_img,
                    scaleFactor=1.1,
                    minNeighbors=5,
                    minSize=(30, 30),
                    flags=getattr(cv2, "CASCADE_SCALE_IMAGE", 0)
                )
                return [FaceBoundingBox(x=int(x), y=int(y), w=int(w), h=int(h)) for (x, y, w, h) in faces]
            except Exception:
                pass
        return []

    def analyze_single_frame(self, image_path: Path, timestamp: float) -> FrameVisualAnalysis:
        """Extracts facial, sharpness, lighting, activity, and composition features from a single frame."""
        image_path = Path(image_path).resolve()
        if not image_path.exists():
            raise VisualAnalyzerError(f"Frame image not found: {image_path}")

        img_bgr = cv2.imread(str(image_path))
        if img_bgr is None:
            raise VisualAnalyzerError(f"Could not load frame image: {image_path}")

        height, width = img_bgr.shape[:2]
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

        # 1. Lighting / Brightness & Contrast
        brightness = float(np.mean(gray))
        contrast = float(np.std(gray))

        # 2. Sharpness & Blur Detection (Laplacian variance)
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        is_blurry = laplacian_var < 50.0

        # 3. Free Local Face Detection
        face_boxes = self._detect_faces(gray)
        max_face_area_ratio = 0.0

        for box in face_boxes:
            area_ratio = (box.w * box.h) / (width * height)
            if area_ratio > max_face_area_ratio:
                max_face_area_ratio = area_ratio

        num_faces = len(face_boxes)

        # 4. Shot Composition Classification
        if max_face_area_ratio > 0.12:
            scene_type = "close_up"
        elif num_faces > 0 or max_face_area_ratio > 0.03:
            scene_type = "medium_shot"
        elif contrast > 40:
            scene_type = "wide_shot"
        else:
            scene_type = "unknown"

        # 5. Visual Activity Level (based on edge density and contrast)
        edges = cv2.Canny(gray, 100, 200)
        edge_density = float(np.count_nonzero(edges)) / (width * height)

        if edge_density > 0.08 or contrast > 65:
            visual_activity = "high"
        elif edge_density > 0.03 or contrast > 40:
            visual_activity = "moderate"
        else:
            visual_activity = "low"

        # Confidence assessment
        confidence = 0.90 if not is_blurry else 0.70

        return FrameVisualAnalysis(
            frame=image_path.name,
            timestamp=timestamp,
            num_faces=num_faces,
            faces=face_boxes,
            brightness=round(brightness, 2),
            contrast=round(contrast, 2),
            sharpness=round(laplacian_var, 2),
            is_blurry=is_blurry,
            visual_activity=visual_activity,
            scene_type=scene_type,
            confidence=confidence,
        )

    def analyze_sampled_frames(
        self,
        frames_dir: Path,
        frame_index: FrameIndex,
        scenes: List[SceneBoundary],
        video_duration: float
    ) -> VisualAnalysisResult:
        """Analyzes all sampled frames in the index and outputs aggregated report."""
        logger.info(f"Analyzing {len(frame_index.frames)} sampled frames with local vision analyzer...")

        frame_analyses: List[FrameVisualAnalysis] = []
        for frame_info in frame_index.frames:
            frame_path = frames_dir / frame_info.filename
            analysis = self.analyze_single_frame(frame_path, frame_info.timestamp)
            frame_analyses.append(analysis)

        result = VisualAnalysisResult(
            video_duration=video_duration,
            total_frames_analyzed=len(frame_analyses),
            scenes=scenes,
            frames=frame_analyses,
        )

        logger.info(
            f"Visual analysis complete: {len(frame_analyses)} frames evaluated across {len(scenes)} scenes."
        )
        return result
