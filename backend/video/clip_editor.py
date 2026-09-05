"""Vertical social media clip editing engine.

Converts raw clips to 9:16 vertical video (1080x1920) with smart reframing,
mild visual sharpening/contrast enhancements, and EBU R128 audio normalization.
"""

from datetime import datetime, timezone
from pathlib import Path
import subprocess
from typing import List, Optional

from backend.config.settings import PipelineSettings, get_settings
from backend.models.clip import ClipSpecification, SelectedClipsReport
from backend.models.editing import CropWindow, EditedClipResult, ProjectEditReport
from backend.models.video import ProjectWorkspace
from backend.utils.logger import get_logger
from backend.video.inspector import VideoInspector
from backend.video.smart_cropper import SmartCropper

logger = get_logger("clip_editor")


class ClipEditor:
    """Edits raw horizontal clips into 9:16 social-media vertical short-form videos."""

    def __init__(self, settings: Optional[PipelineSettings] = None):
        self.settings = settings or get_settings()
        self.cropper = SmartCropper(settings=self.settings)
        # Dedicated inspector with relaxed duration constraints for clips
        clip_inspector_settings = self.settings.model_copy(update={"min_video_duration": 0.5})
        self.inspector = VideoInspector(settings=clip_inspector_settings)

    def edit_clip(
        self,
        raw_clip_path: Path,
        output_file_path: Path,
        clip_spec: ClipSpecification,
        strategy: Optional[str] = None,
    ) -> EditedClipResult:
        """Transform a single raw clip into an edited 9:16 vertical video.

        Args:
            raw_clip_path: Path to the raw extracted clip.
            output_file_path: Destination path for the vertical edited clip.
            clip_spec: Clip specification containing metadata.
            strategy: Optional crop strategy override ('smart_face' or 'center').

        Returns:
            EditedClipResult detailing resolution, crop window, audio normalization, and file info.
        """
        output_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Inspect raw clip
        metadata = self.inspector.inspect(raw_clip_path)

        # Calculate 9:16 crop window
        crop = self.cropper.calculate_crop(
            video_path=raw_clip_path,
            original_width=metadata.width,
            original_height=metadata.height,
            strategy=strategy,
        )

        target_w = self.settings.target_vertical_width
        target_h = self.settings.target_vertical_height

        # Video filters:
        # 1. Scale height to 1920 (width auto-scales to -1 maintaining aspect ratio)
        # 2. Crop 1080x1920 starting at crop.x
        # 3. Optional subtle sharpening/contrast optimization
        vf_components = [
            f"scale=-1:{target_h}",
            f"crop={target_w}:{target_h}:{crop.x}:0",
        ]
        if self.settings.enable_visual_enhancements:
            vf_components.append("unsharp=5:5:0.5:5:5:0.0")

        video_filter = ",".join(vf_components)

        # Audio filter: EBU R128 loudness normalization for punchy mobile vocal delivery
        audio_filter = f"loudnorm=I={self.settings.audio_loudnorm_target}:LRA=11:TP=-1.5"

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(raw_clip_path),
            "-vf",
            video_filter,
            "-af",
            audio_filter,
            "-c:v",
            "libx264",
            "-preset",
            self.settings.clip_preset,
            "-crf",
            str(self.settings.clip_crf),
            "-c:a",
            "aac",
            "-b:a",
            self.settings.clip_audio_bitrate,
            str(output_file_path),
        ]

        logger.info(
            f"Rendering 9:16 vertical clip {clip_spec.clip_id} ({clip_spec.category}) "
            f"using {crop.strategy_used} crop at X={crop.x} -> {output_file_path.name}"
        )

        try:
            subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg vertical render failed for clip {clip_spec.clip_id}: {e.stderr}")
            raise RuntimeError(f"FFmpeg failed to edit clip {clip_spec.clip_id}: {e.stderr}") from e

        if not output_file_path.exists() or output_file_path.stat().st_size == 0:
            raise RuntimeError(f"Edited clip output missing or empty: {output_file_path}")

        file_size = output_file_path.stat().st_size
        logger.info(
            f"Edited clip {clip_spec.clip_id} rendered successfully ({file_size / 1024 / 1024:.2f} MB)"
        )

        return EditedClipResult(
            clip_id=str(clip_spec.clip_id),
            category=clip_spec.category,
            raw_clip_path=str(raw_clip_path),
            edited_clip_path=str(output_file_path),
            resolution=f"{target_w}x{target_h}",
            aspect_ratio=self.settings.target_aspect_ratio,
            duration=metadata.duration,
            file_size_bytes=file_size,
            crop=crop,
            audio_normalized=True,
            visual_enhancement_applied=self.settings.enable_visual_enhancements,
        )

    def edit_all_clips(
        self,
        report: SelectedClipsReport,
        workspace: ProjectWorkspace,
        strategy: Optional[str] = None,
    ) -> ProjectEditReport:
        """Transform all raw clips in workspace into vertical social media clips.

        Files are saved to:
            workspace.edited_clips / <category> / <output_filename>

        Args:
            report: SelectedClipsReport specifying clips to edit.
            workspace: Target project workspace.
            strategy: Optional crop strategy override ('smart_face' or 'center').

        Returns:
            ProjectEditReport containing all individual edited clip results.
        """
        results: List[EditedClipResult] = []

        for clip_spec in report.clips:
            filename = getattr(clip_spec, "output_filename", None) or f"{clip_spec.clip_id}.mp4"
            raw_path = workspace.raw_clips / clip_spec.category / filename
            if not raw_path.exists():
                logger.warning(f"Raw clip not found for editing: {raw_path}")
                continue

            edited_dir = workspace.edited_clips / clip_spec.category
            output_file = edited_dir / filename

            result = self.edit_clip(raw_path, output_file, clip_spec, strategy=strategy)
            results.append(result)

        edit_report = ProjectEditReport(
            project_id=workspace.project_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            total_clips=len(results),
            target_resolution=f"{self.settings.target_vertical_width}x{self.settings.target_vertical_height}",
            target_aspect_ratio=self.settings.target_aspect_ratio,
            clips=results,
        )

        logger.info(f"Successfully edited {len(results)} vertical clips for project {workspace.project_id}.")
        return edit_report
