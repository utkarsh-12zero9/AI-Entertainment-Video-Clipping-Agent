"""Raw clip extraction module using FFmpeg.

Extracts candidate clips from the original video with frame accuracy, high visual quality,
and category-prefixed directory organization.
"""

from pathlib import Path
import subprocess
from typing import List, Optional

from backend.config.settings import PipelineSettings, get_settings
from backend.models.clip import ClipSpecification, SelectedClipsReport
from backend.models.video import ProjectWorkspace
from backend.utils.logger import get_logger

logger = get_logger("raw_clip_extractor")


class RawClipExtractor:
    """Extracts raw candidate clips from source video according to specifications."""

    def __init__(self, settings: Optional[PipelineSettings] = None):
        self.settings = settings or get_settings()

    def extract_clip(
        self,
        source_video_path: Path,
        clip_spec: ClipSpecification,
        output_file_path: Path,
    ) -> Path:
        """Extract a single clip using FFmpeg.

        Uses -ss and -to with input seek and re-encoding for high-quality, keyframe-accurate cuts.

        Args:
            source_video_path: Path to master video file.
            clip_spec: Clip specification with start/end timestamps.
            output_file_path: Target path for the output mp4 clip.

        Returns:
            Path to the successfully extracted clip.
        """
        output_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Standard fast seek + accurate cut command
        # Placing -ss before -i for fast seek to near keyframe, and re-encoding with libx264/aac
        # ensures perfect sync and zero freeze at clip start.
        duration = clip_spec.duration if hasattr(clip_spec, "duration") else (clip_spec.end_time - clip_spec.start_time)
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{clip_spec.start_time:.3f}",
            "-i",
            str(source_video_path),
            "-t",
            f"{duration:.3f}",
            "-c:v",
            "libx264",
            "-crf",
            str(self.settings.clip_crf),
            "-preset",
            self.settings.clip_preset,
            "-c:a",
            "aac",
            "-b:a",
            self.settings.clip_audio_bitrate,
            "-avoid_negative_ts",
            "make_zero",
            str(output_file_path),
        ]

        logger.info(
            f"Extracting clip {clip_spec.clip_id} ({clip_spec.category}) "
            f"[{clip_spec.start_time:.2f}s - {clip_spec.end_time:.2f}s] -> {output_file_path.name}"
        )

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg extraction failed for clip {clip_spec.clip_id}: {e.stderr}")
            raise RuntimeError(f"FFmpeg failed to extract clip {clip_spec.clip_id}: {e.stderr}") from e

        if not output_file_path.exists() or output_file_path.stat().st_size == 0:
            raise RuntimeError(f"Extracted clip is missing or empty: {output_file_path}")

        logger.info(
            f"Clip {clip_spec.clip_id} extracted successfully ({output_file_path.stat().st_size / 1024 / 1024:.2f} MB)"
        )
        return output_file_path

    def extract_all_clips(
        self,
        source_video_path: Path,
        report: SelectedClipsReport,
        workspace: ProjectWorkspace,
    ) -> List[Path]:
        """Extract all clips specified in a SelectedClipsReport into the workspace.

        Files are saved to:
            workspace.raw_clips / <category> / <output_filename>

        Args:
            source_video_path: Path to master video file.
            report: SelectedClipsReport with ranked/optimized clip specs.
            workspace: Target project workspace.

        Returns:
            List of Paths to extracted clip files.
        """
        extracted_paths: List[Path] = []

        if not report.clips:
            logger.warning("No clips to extract in report.")
            return extracted_paths

        for clip_spec in report.clips:
            category_dir = workspace.raw_clips / clip_spec.category
            filename = getattr(clip_spec, "output_filename", None) or f"{clip_spec.clip_id}.mp4"
            output_file = category_dir / filename
            extracted = self.extract_clip(source_video_path, clip_spec, output_file)
            extracted_paths.append(extracted)

        logger.info(f"Successfully extracted {len(extracted_paths)} raw clips.")
        return extracted_paths
