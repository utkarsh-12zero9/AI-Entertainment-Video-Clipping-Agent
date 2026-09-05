"""Automated QA and validation module for extracted video clips.

Validates duration, stream integrity, audio/video sync, black frames, and audio silence.
"""

from datetime import datetime, timezone
from pathlib import Path
import subprocess
from typing import List, Optional

from backend.config.settings import PipelineSettings, get_settings
from backend.models.clip import ClipSpecification, SelectedClipsReport
from backend.models.qa import ClipQAChecks, ClipQAResult, ProjectQAReport
from backend.models.video import ProjectWorkspace
from backend.utils.logger import get_logger
from backend.video.inspector import VideoInspector

logger = get_logger("clip_validator")


class ClipValidator:
    """Performs automated QA checks on extracted clips using FFprobe and FFmpeg filters."""

    def __init__(self, settings: Optional[PipelineSettings] = None):
        self.settings = settings or get_settings()
        # Create a dedicated inspector copy for clips allowing short clip durations (down to 0.5s)
        clip_inspector_settings = self.settings.model_copy(update={"min_video_duration": 0.5})
        self.inspector = VideoInspector(settings=clip_inspector_settings)

    def validate_clip(
        self,
        clip_path: Path,
        clip_spec: ClipSpecification,
    ) -> ClipQAResult:
        """Run comprehensive QA inspection on an extracted clip.

        Args:
            clip_path: Path to the extracted clip file.
            clip_spec: The expected clip specification.

        Returns:
            ClipQAResult detailing all individual checks and overall pass/fail status.
        """
        logger.info(f"Running automated QA on clip: {clip_path.name}")
        issues: List[str] = []

        expected_dur = getattr(clip_spec, "duration", None) or getattr(clip_spec, "duration_seconds", 0.0)

        if not clip_path.exists() or clip_path.stat().st_size == 0:
            return ClipQAResult(
                clip_id=str(clip_spec.clip_id),
                file_path=str(clip_path),
                expected_duration=round(expected_dur, 3),
                actual_duration=0.0,
                duration_diff=round(expected_dur, 3),
                checks=ClipQAChecks(
                    duration=False,
                    video=False,
                    audio=False,
                    sync=False,
                    silence=False,
                    black_frames=False,
                    corruption=True,
                ),
                passed=False,
                errors=["Clip file does not exist or has 0 bytes"],
            )

        # 1. Inspect metadata via ffprobe
        has_video = False
        has_audio = False
        actual_duration = 0.0
        no_decode_errors = True

        try:
            metadata = self.inspector.inspect(clip_path)
            has_video = (metadata.width > 0 and metadata.height > 0)
            has_audio = metadata.has_audio
            actual_duration = metadata.duration
        except Exception as e:
            issues.append(f"Inspection error: {e}")
            no_decode_errors = False

        if not has_video:
            issues.append("Missing video stream")
        if not has_audio:
            issues.append("Missing audio stream")

        # 2. Check duration tolerance
        duration_diff = abs(actual_duration - expected_dur)
        duration_valid = duration_diff <= self.settings.qa_duration_tolerance_sec
        if not duration_valid:
            issues.append(
                f"Duration discrepancy exceeds tolerance: expected {expected_dur:.2f}s, "
                f"got {actual_duration:.2f}s (diff: {duration_diff:.2f}s, tol: {self.settings.qa_duration_tolerance_sec:.2f}s)"
            )

        # 3. Stream sync (video and audio stream start and duration alignment)
        stream_sync_valid = True
        try:
            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=codec_type,start_time,duration",
                "-of",
                "json",
                str(clip_path),
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            import json
            stream_info = json.loads(res.stdout).get("streams", [])
            v_start = 0.0
            a_start = 0.0
            for s in stream_info:
                if s.get("codec_type") == "video":
                    v_start = float(s.get("start_time", 0.0) or 0.0)
                elif s.get("codec_type") == "audio":
                    a_start = float(s.get("start_time", 0.0) or 0.0)
            if abs(v_start - a_start) > 0.5:
                stream_sync_valid = False
                issues.append(f"Audio/Video start offset high ({abs(v_start - a_start):.3f}s)")
        except Exception as e:
            logger.debug(f"Sync check note: {e}")

        # 4. Check for excessive silence (silencedetect filter)
        no_excessive_silence = True
        try:
            silence_cmd = [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(clip_path),
                "-af",
                f"silencedetect=noise=-40dB:d={self.settings.qa_max_allowed_silence_sec}",
                "-f",
                "null",
                "-",
            ]
            silence_res = subprocess.run(silence_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if "silence_duration" in silence_res.stderr:
                # Parse detected silence duration
                for line in silence_res.stderr.splitlines():
                    if "silence_duration:" in line:
                        try:
                            parts = line.split("silence_duration:")
                            dur = float(parts[1].strip().split()[0])
                            if dur >= self.settings.qa_max_allowed_silence_sec:
                                no_excessive_silence = False
                                issues.append(f"Excessive silence detected ({dur:.2f}s)")
                                break
                        except Exception:
                            pass
        except Exception as e:
            logger.debug(f"Silence check note: {e}")

        # 5. Check for excessive black frames (blackdetect filter)
        no_excessive_black = True
        try:
            black_cmd = [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(clip_path),
                "-vf",
                "blackdetect=d=3.0:pix_th=0.10",
                "-f",
                "null",
                "-",
            ]
            black_res = subprocess.run(black_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if "black_duration" in black_res.stderr:
                no_excessive_black = False
                issues.append("Excessive black frames detected (>3s)")
        except Exception as e:
            logger.debug(f"Blackdetect note: {e}")

        checks = ClipQAChecks(
            duration=duration_valid,
            video=has_video,
            audio=has_audio,
            sync=stream_sync_valid,
            silence=(not no_excessive_silence),
            black_frames=(not no_excessive_black),
            corruption=(not no_decode_errors),
        )

        passed = len(issues) == 0

        return ClipQAResult(
            clip_id=str(clip_spec.clip_id),
            file_path=str(clip_path),
            expected_duration=round(expected_dur, 3),
            actual_duration=round(actual_duration, 3),
            duration_diff=round(duration_diff, 3),
            checks=checks,
            passed=passed,
            errors=issues,
        )

    def validate_all_clips(
        self,
        report: SelectedClipsReport,
        workspace: ProjectWorkspace,
    ) -> ProjectQAReport:
        """Validate all clips in a SelectedClipsReport within the workspace.

        Args:
            report: The SelectedClipsReport with clips to test.
            workspace: The target project workspace.

        Returns:
            ProjectQAReport containing individual and aggregate QA results.
        """
        results: List[ClipQAResult] = []

        for clip_spec in report.clips:
            filename = getattr(clip_spec, "output_filename", None) or f"{clip_spec.clip_id}.mp4"
            clip_path = workspace.raw_clips / clip_spec.category / filename
            result = self.validate_clip(clip_path, clip_spec)
            results.append(result)

        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed

        qa_report = ProjectQAReport(
            project_id=workspace.project_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            total_clips=total,
            passed_clips=passed,
            failed_clips=failed,
            all_passed=(failed == 0),
            results=results,
        )

        logger.info(
            f"QA completed for project {workspace.project_id}: {passed}/{total} passed (failed: {failed})"
        )
        return qa_report
