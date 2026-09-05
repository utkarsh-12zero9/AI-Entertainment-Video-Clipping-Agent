"""Intelligent thumbnail generator module.

Extracts the strongest frame (highest clarity, prominent face/subject, good contrast)
from the vertical video and renders a high-visibility, mobile-friendly hook banner overlay.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from backend.config.settings import PipelineSettings, get_settings
from backend.models.clip import ClipSpecification, SelectedClipsReport
from backend.models.video import ProjectWorkspace
from backend.utils.logger import get_logger

logger = get_logger("thumbnail_generator")


class ThumbnailGenerator:
    """Selects the strongest frame from a vertical clip and overlays high-contrast text."""

    def __init__(self, settings: Optional[PipelineSettings] = None):
        self.settings = settings or get_settings()
        self._cascade: Optional[cv2.CascadeClassifier] = None
        self._init_cascade()

    def _init_cascade(self) -> None:
        """Loads Haar cascade face detector with graceful fallback."""
        try:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            if Path(cascade_path).exists():
                self._cascade = cv2.CascadeClassifier(cascade_path)
        except Exception:
            self._cascade = None

    def _score_frame(self, frame: np.ndarray) -> Tuple[float, Optional[Tuple[int, int, int, int]]]:
        """Scores candidate frame based on sharpness, face presence, and contrast.

        Returns:
            Tuple of (composite_score, best_face_bbox)
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 1. Sharpness via Laplacian variance
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        sharpness_score = min(1.0, laplacian_var / 500.0)

        # 2. Contrast & dynamic range
        min_val, max_val, _, _ = cv2.minMaxLoc(gray)
        contrast_score = (max_val - min_val) / 255.0

        # 3. Face detection
        face_score = 0.0
        best_face = None
        if self._cascade:
            faces = self._cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(60, 60))
            if len(faces) > 0:
                # Find largest face by area
                largest = max(faces, key=lambda f: f[2] * f[3])
                h, w = frame.shape[:2]
                face_area_ratio = (largest[2] * largest[3]) / (w * h)
                face_score = min(1.0, face_area_ratio * 15.0)  # optimal ~6-10% of screen
                best_face = (int(largest[0]), int(largest[1]), int(largest[2]), int(largest[3]))

        # Weighted composite score
        total_score = (0.40 * sharpness_score) + (0.35 * face_score) + (0.25 * contrast_score)
        return total_score, best_face

    def select_best_frame(self, video_path: Path) -> Tuple[np.ndarray, Optional[Tuple[int, int, int, int]]]:
        """Samples candidate frames across video and selects the highest scoring frame."""
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video file for thumbnail: {video_path}")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        num_samples = self.settings.thumbnail_num_sample_frames
        step = max(1, total_frames // num_samples)

        best_score = -1.0
        best_frame = None
        best_face = None

        frame_idx = 0
        while cap.isOpened() and frame_idx < total_frames:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            score, face = self._score_frame(frame)
            if score > best_score:
                best_score = score
                best_frame = frame.copy()
                best_face = face

            frame_idx += step

        cap.release()

        if best_frame is None:
            raise RuntimeError(f"Failed to extract any valid frames from {video_path}")

        logger.info(f"Selected best thumbnail frame for {video_path.name} (score: {best_score:.2f})")
        return best_frame, best_face

    def overlay_text(
        self,
        image: Image.Image,
        text: str,
        face_bbox: Optional[Tuple[int, int, int, int]] = None,
    ) -> Image.Image:
        """Renders high-contrast hook text banner onto thumbnail image away from faces.

        Args:
            image: PIL Image object (1080x1920).
            text: Text to overlay (typically the hook line, cleaned).
            face_bbox: Optional (x, y, w, h) of detected face to avoid.

        Returns:
            PIL Image with rendered text banner.
        """
        # Clean and shorten text
        clean_text = text.upper().strip()
        if len(clean_text) > 40:
            clean_text = clean_text[:37] + "..."

        draw = ImageDraw.Draw(image, "RGBA")
        width, height = image.size

        # Simple cross-platform default font
        font_size = self.settings.thumbnail_font_size
        try:
            font = ImageFont.truetype("arialbd.ttf", font_size)
        except IOError:
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except IOError:
                font = ImageFont.load_default()

        # Word wrap text into 2 lines if needed
        words = clean_text.split()
        lines = []
        curr_line = []
        for w in words:
            curr_line.append(w)
            if len(" ".join(curr_line)) > 18:
                lines.append(" ".join(curr_line))
                curr_line = []
        if curr_line:
            lines.append(" ".join(curr_line))

        full_display_text = "\n".join(lines[:2])

        # Vertical placement:
        # Default top-third banner (Y=240 to 380), safe above face
        banner_y = int(height * 0.14)
        if face_bbox:
            fx, fy, fw, fh = face_bbox
            # If face is high up, place banner beneath it
            if fy < height * 0.25:
                banner_y = min(int(height * 0.70), fy + fh + 40)

        # Measure text
        bbox = draw.textbbox((0, 0), full_display_text, font=font, align="center")
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        pad_x = 40
        pad_y = 24
        rect_x0 = max(40, (width - text_w) // 2 - pad_x)
        rect_y0 = banner_y - pad_y
        rect_x1 = min(width - 40, (width + text_w) // 2 + pad_x)
        rect_y1 = banner_y + text_h + pad_y

        # Semi-transparent dark banner background
        draw.rectangle(
            [rect_x0, rect_y0, rect_x1, rect_y1],
            fill=(0, 0, 0, 200),
            outline=(255, 215, 0, 255),  # Gold accent border
            width=4,
        )

        # Centered bold white text
        text_x = (width - text_w) // 2
        text_y = banner_y
        draw.text(
            (text_x, text_y),
            full_display_text,
            font=font,
            fill=(255, 255, 255, 255),
            align="center",
        )

        return image

    def generate_thumbnail(
        self,
        video_path: Path,
        output_image_path: Path,
        clip_spec: ClipSpecification,
        overlay_text: Optional[bool] = None,
    ) -> Path:
        """Generates and saves a high-quality vertical thumbnail for a clip.

        Args:
            video_path: Path to vertical video file.
            output_image_path: Destination .jpg file.
            clip_spec: Clip specification containing hook text.
            overlay_text: Explicit toggle for overlaying text (defaults to settings).

        Returns:
            Path to saved thumbnail.
        """
        output_image_path.parent.mkdir(parents=True, exist_ok=True)

        best_frame, best_face = self.select_best_frame(video_path)

        # Convert OpenCV BGR to RGB PIL Image
        rgb_frame = cv2.cvtColor(best_frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_frame)

        # Ensure vertical 1080x1920 dimension
        if pil_img.size != (1080, 1920):
            pil_img = pil_img.resize((1080, 1920), Image.Resampling.LANCZOS)

        should_overlay = self.settings.thumbnail_overlay_text if overlay_text is None else overlay_text
        if should_overlay:
            text_to_show = clip_spec.hook or clip_spec.category
            pil_img = self.overlay_text(pil_img, text_to_show, face_bbox=best_face)

        # Save high-quality JPEG
        pil_img.save(str(output_image_path), "JPEG", quality=95)
        logger.info(f"Saved thumbnail to {output_image_path.name}")
        return output_image_path

    def generate_all_thumbnails(
        self,
        report: SelectedClipsReport,
        workspace: ProjectWorkspace,
    ) -> Dict[str, Path]:
        """Generates thumbnails for all clips in a SelectedClipsReport.

        Returns:
            Dict mapping clip_id to saved thumbnail Path.
        """
        workspace.thumbnails_dir.mkdir(parents=True, exist_ok=True)
        results: Dict[str, Path] = {}

        for clip_spec in report.clips:
            filename = getattr(clip_spec, "output_filename", None) or f"{clip_spec.clip_id}.mp4"
            thumb_path = workspace.thumbnails_dir / f"{clip_spec.clip_id}.jpg"

            # Check potential locations for clip video (captioned > edited > raw)
            src_video = None
            for cand_dir in [workspace.captioned_clips, workspace.edited_clips_dir, workspace.raw_clips_dir]:
                p1 = cand_dir / clip_spec.category / filename
                p2 = cand_dir / filename
                if p1.exists():
                    src_video = p1
                    break
                elif p2.exists():
                    src_video = p2
                    break

            if src_video and src_video.exists():
                try:
                    saved = self.generate_thumbnail(src_video, thumb_path, clip_spec)
                    results[clip_spec.clip_id] = saved
                except Exception as e:
                    logger.warning(f"Failed to generate thumbnail for {clip_spec.clip_id}: {e}")
            else:
                logger.warning(f"Could not find video file to generate thumbnail for {clip_spec.clip_id}")

        return results

