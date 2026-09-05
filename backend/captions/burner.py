"""Caption burning and video rendering module using FFmpeg."""

from datetime import datetime, timezone
from pathlib import Path
import subprocess
from typing import List, Optional

from backend.config.settings import PipelineSettings, get_settings
from backend.models.caption import ClipCaptionResult, ProjectCaptionReport
from backend.models.clip import ClipSpecification, SelectedClipsReport
from backend.models.transcript import TranscriptResult
from backend.models.video import ProjectWorkspace
from backend.utils.logger import get_logger
from backend.captions.generator import CaptionGenerator

logger = get_logger("caption_burner")


class CaptionBurner:
    """Burns styled subtitles onto vertical 9:16 videos."""

    def __init__(self, settings: Optional[PipelineSettings] = None):
        self.settings = settings or get_settings()
        self.generator = CaptionGenerator(settings=self.settings)

    def burn_captions(
        self,
        input_video_path: Path,
        ass_path: Path,
        output_video_path: Path,
    ) -> Path:
        """Burn an .ass subtitle file onto a video using FFmpeg subtitles filter.

        Args:
            input_video_path: Path to the clean vertical video.
            ass_path: Path to the styled .ass subtitle file.
            output_video_path: Destination path for the captioned video.

        Returns:
            Path to the rendered captioned video.
        """
        output_video_path.parent.mkdir(parents=True, exist_ok=True)

        # In FFmpeg, the subtitles filter takes: subtitles=filename='escaped_path'
        # Colons in drive letters (e.g. C:) and backslashes must be escaped inside the filter string
        clean_path = str(ass_path.resolve()).replace("\\", "/")
        escaped_ass = clean_path.replace(":", "\\:")

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_video_path),
            "-vf",
            f"subtitles=filename='{escaped_ass}'",
            "-c:v",
            "libx264",
            "-preset",
            self.settings.clip_preset,
            "-crf",
            str(self.settings.clip_crf),
            "-c:a",
            "copy",
            str(output_video_path),
        ]

        logger.info(f"Burning subtitles onto {input_video_path.name} -> {output_video_path.name}")

        try:
            subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg subtitle burning failed: {e.stderr}")
            raise RuntimeError(f"FFmpeg subtitle burning failed: {e.stderr}") from e

        if not output_video_path.exists() or output_video_path.stat().st_size == 0:
            raise RuntimeError(f"Captioned output video missing or empty: {output_video_path}")

        return output_video_path

    def process_all_clips(
        self,
        report: SelectedClipsReport,
        transcript: TranscriptResult,
        workspace: ProjectWorkspace,
        style: Optional[str] = None,
    ) -> ProjectCaptionReport:
        """Generate subtitles and burn them onto all vertical edited clips in the workspace.

        Args:
            report: SelectedClipsReport specifying clips.
            transcript: Full transcription data.
            workspace: Target project workspace.
            style: Optional subtitle style override ('bold_highlight', 'clean', 'karaoke').

        Returns:
            ProjectCaptionReport containing per-clip caption metadata.
        """
        results: List[ClipCaptionResult] = []
        chosen_style = style or self.settings.caption_style

        # Ensure output directory exists
        workspace.captioned_clips.mkdir(parents=True, exist_ok=True)

        for clip_spec in report.clips:
            filename = getattr(clip_spec, "output_filename", None) or f"{clip_spec.clip_id}.mp4"
            # Prefer vertical edited clip; fallback to raw clip if edited clip doesn't exist
            edited_path = workspace.edited_clips / clip_spec.category / filename
            source_video = edited_path if edited_path.exists() else (workspace.raw_clips / clip_spec.category / filename)

            if not source_video.exists():
                logger.warning(f"No video found to caption for clip {clip_spec.clip_id}: {source_video}")
                continue

            srt_path = workspace.captions_dir / f"{clip_spec.clip_id}.srt"
            ass_path = workspace.captions_dir / f"{clip_spec.clip_id}.ass"

            # 1. Generate subtitle files
            chunks = self.generator.generate_captions_for_clip(
                clip_spec=clip_spec,
                transcript=transcript,
                srt_output_path=srt_path,
                ass_output_path=ass_path,
                style=chosen_style,
            )

            # 2. Burn subtitles into output video
            out_category_dir = workspace.captioned_clips / clip_spec.category
            out_video = out_category_dir / filename
            self.burn_captions(source_video, ass_path, out_video)

            results.append(
                ClipCaptionResult(
                    clip_id=str(clip_spec.clip_id),
                    category=clip_spec.category,
                    srt_path=str(srt_path),
                    ass_path=str(ass_path),
                    captioned_clip_path=str(out_video),
                    total_chunks=len(chunks),
                    style_used=chosen_style,
                    duration=clip_spec.duration if hasattr(clip_spec, "duration") else (clip_spec.end_time - clip_spec.start_time),
                )
            )

        caption_report = ProjectCaptionReport(
            project_id=workspace.project_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            total_clips=len(results),
            caption_style=chosen_style,
            clips=results,
        )

        logger.info(f"Successfully processed captions for {len(results)} clips in project {workspace.project_id}.")
        return caption_report
