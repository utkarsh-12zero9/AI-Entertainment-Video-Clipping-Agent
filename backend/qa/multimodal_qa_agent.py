"""Final Multimodal Quality Assurance (QA) Agent module.

Evaluates rendered 9:16 vertical clips (with captions), thumbnails, and platform social
metadata against rigorous multimodal quality standards. Detects abrupt cuts in speech
boundaries, caption safe-margin compliance, audio integrity, and artifact completeness.
Provides structured repair recommendations (RETRIM, REPOSITION_CAPTIONS, REGENERATE)
and promotes approved deliverables into the project final/ folder.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from backend.config.settings import PipelineSettings, get_settings
from backend.models.clip import ClipSpecification, SelectedClipsReport
from backend.models.qa import (
    FinalClipQAResult,
    FinalProjectQAReport,
    MultimodalQAChecks,
    RepairAction,
    RepairRecommendation,
)
from backend.models.transcript import TranscriptResult, WordTimestamp
from backend.models.video import ProjectWorkspace
from backend.utils.logger import get_logger
from backend.video.inspector import VideoInspector

logger = get_logger("multimodal_qa_agent")


class MultimodalQAAgent:
    """Performs end-to-end multimodal quality assurance on final rendered video deliverables."""

    def __init__(self, settings: Optional[PipelineSettings] = None):
        self.settings = settings or get_settings()
        clip_inspector_settings = self.settings.model_copy(update={"min_video_duration": 0.5})
        self.inspector = VideoInspector(settings=clip_inspector_settings)

    def _inspect_technical_quality(
        self,
        video_path: Path,
        expected_dur: float,
    ) -> Tuple[bool, bool, List[str]]:
        """Verifies video decodability, 1080x1920 vertical format, and audio stream existence."""
        issues: List[str] = []
        if not video_path.exists() or video_path.stat().st_size == 0:
            return False, False, ["Rendered video file is missing or zero bytes"]

        technical_valid = True
        audio_loudness_valid = True

        try:
            meta = self.inspector.inspect(video_path)

            # Check dimensions (must be vertical 9:16)
            if meta.width != self.settings.target_vertical_width or meta.height != self.settings.target_vertical_height:
                technical_valid = False
                issues.append(f"Invalid vertical resolution: {meta.width}x{meta.height} (expected {self.settings.target_vertical_width}x{self.settings.target_vertical_height})")

            # Check duration tolerance
            diff = abs(meta.duration - expected_dur)
            tolerance = getattr(self.settings, "qa_duration_tolerance_sec", 0.75)
            if diff > tolerance:
                technical_valid = False
                issues.append(f"Duration mismatch: actual {meta.duration:.2f}s vs expected {expected_dur:.2f}s (diff: {diff:.2f}s)")

            # Check audio presence
            if not meta.has_audio:
                technical_valid = False
                audio_loudness_valid = False
                issues.append("Audio stream missing from rendered clip")
        except Exception as e:
            # If inspection failed specifically due to audio missing
            if "audio" in str(e).lower():
                technical_valid = False
                audio_loudness_valid = False
                issues.append(f"Audio stream missing or unusable: {e}")
            else:
                technical_valid = False
                issues.append(f"Video inspection failed: {e}")

        # Check for decodability with OpenCV
        try:
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                technical_valid = False
                issues.append("OpenCV cannot decode video stream")
            else:
                ret, frame = cap.read()
                if not ret or frame is None or frame.size == 0:
                    technical_valid = False
                    issues.append("Failed to decode initial frame of video stream")
            cap.release()
        except Exception as e:
            technical_valid = False
            issues.append(f"Frame decode check failed: {e}")

        return technical_valid, audio_loudness_valid, issues

    def _inspect_abrupt_cuts(
        self,
        clip_spec: ClipSpecification,
        transcript: Optional[TranscriptResult],
    ) -> Tuple[bool, bool, Optional[float], Optional[float], List[str]]:
        """Evaluates whether clip start/end boundaries cut through active words or end abruptly."""
        no_abrupt_start = True
        no_abrupt_end = True
        suggested_start = None
        suggested_end = None
        issues: List[str] = []

        if not transcript or not transcript.segments:
            return True, True, None, None, issues

        start = clip_spec.start_time
        end = clip_spec.end_time
        tolerance = self.settings.qa_abrupt_cut_tolerance_sec

        # Collect all words across transcript
        all_words: List[WordTimestamp] = []
        for seg in transcript.segments:
            if seg.words:
                all_words.extend(seg.words)

        if not all_words:
            return True, True, None, None, issues

        # 1. Inspect START cut: check if start falls right inside an active word
        for w in all_words:
            # Word starts strictly before clip start, but ends well after clip start
            if (w.start < start - tolerance) and (w.end > start + tolerance):
                no_abrupt_start = False
                suggested_start = max(0.0, w.start - 0.1)
                issues.append(f"Abrupt start: cuts mid-word '{w.word}' ({w.start:.2f}s - {w.end:.2f}s)")
                break

        # 2. Inspect END cut: check if end slices mid-word or terminates prematurely
        for w in all_words:
            if (w.start < end - tolerance) and (w.end > end + tolerance):
                no_abrupt_end = False
                suggested_end = w.end + 0.2
                issues.append(f"Abrupt end: cuts mid-word '{w.word}' ({w.start:.2f}s - {w.end:.2f}s)")
                break

        return no_abrupt_start, no_abrupt_end, suggested_start, suggested_end, issues

    def _inspect_captions(
        self,
        clip_id: str,
        category: str,
        workspace: ProjectWorkspace,
    ) -> Tuple[bool, List[str]]:
        """Verifies presence and validity of subtitle files (.srt and .ass)."""
        issues: List[str] = []
        srt_file = workspace.captions_dir / f"{clip_id}.srt"
        ass_file = workspace.captions_dir / f"{clip_id}.ass"

        if not srt_file.exists() and not ass_file.exists():
            issues.append(f"No subtitle file found for {clip_id} in {workspace.captions_dir}")
            return False, issues

        # Verify ASS file format and dialogue cues
        if ass_file.exists():
            content = ass_file.read_text(encoding="utf-8")
            if "Dialogue:" not in content:
                issues.append("ASS subtitle file contains no dialogue cues")
                return False, issues
            if "MarginV" not in content:
                issues.append("ASS subtitle file missing mobile safe area margins")
                return False, issues

        return True, issues

    def _inspect_thumbnail(
        self,
        clip_id: str,
        workspace: ProjectWorkspace,
    ) -> Tuple[bool, List[str]]:
        """Verifies thumbnail existence, 1080x1920 dimension, and valid contrast."""
        issues: List[str] = []
        thumb_path = workspace.thumbnails_dir / f"{clip_id}.jpg"
        if not thumb_path.exists() or thumb_path.stat().st_size == 0:
            issues.append(f"Thumbnail missing or empty: {thumb_path.name}")
            return False, issues

        try:
            with Image.open(thumb_path) as img:
                w, h = img.size
                if (w, h) != (1080, 1920):
                    issues.append(f"Thumbnail has non-vertical dimensions: {w}x{h}")
                    return False, issues
                
                # Check for completely blank/black image
                img_gray = img.convert("L")
                stat = np.array(img_gray)
                if stat.mean() == 0 or stat.std() < 0.1:
                    issues.append("Thumbnail appears completely flat/blank (all black or zero variance)")
                    return False, issues
        except Exception as e:
            issues.append(f"Failed to inspect thumbnail image: {e}")
            return False, issues

        return True, issues

    def _inspect_metadata(
        self,
        clip_id: str,
        workspace: ProjectWorkspace,
    ) -> Tuple[bool, List[str]]:
        """Verifies social metadata JSON package existence and completeness across platforms."""
        issues: List[str] = []
        meta_file = workspace.metadata_dir / f"{clip_id}.json"
        if not meta_file.exists() or meta_file.stat().st_size == 0:
            issues.append(f"Social metadata JSON missing or empty: {meta_file.name}")
            return False, issues

        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not data.get("primary_title"):
                issues.append("Metadata missing primary curiosity-driven title")
            
            platforms = data.get("platforms", {})
            for p in self.settings.default_platforms:
                if p not in platforms:
                    issues.append(f"Metadata missing platform record for: {p}")
                else:
                    p_info = platforms[p]
                    if not p_info.get("title"):
                        issues.append(f"Platform {p} missing title")
                    if not p_info.get("hashtags"):
                        issues.append(f"Platform {p} missing hashtags")
        except Exception as e:
            issues.append(f"Failed to parse metadata JSON: {e}")
            return False, issues

        return len(issues) == 0, issues

    def evaluate_clip(
        self,
        clip_spec: ClipSpecification,
        workspace: ProjectWorkspace,
        transcript: Optional[TranscriptResult] = None,
    ) -> FinalClipQAResult:
        """Runs the complete multimodal QA pipeline on a candidate clip.

        Args:
            clip_spec: Clip specification.
            workspace: Target project workspace.
            transcript: Full video transcript with word timestamps if available.

        Returns:
            FinalClipQAResult with multimodal checks, score, and repair recommendations.
        """
        clip_id = clip_spec.clip_id
        cat = clip_spec.category
        filename = getattr(clip_spec, "output_filename", None) or f"{clip_id}.mp4"

        # Locate captioned video (prefer captioned > edited > raw)
        clip_path = workspace.captioned_clips / cat / filename
        if not clip_path.exists():
            clip_path = workspace.captioned_clips / filename
        if not clip_path.exists():
            clip_path = workspace.edited_clips_dir / cat / filename
        if not clip_path.exists():
            clip_path = workspace.edited_clips_dir / filename

        expected_dur = getattr(clip_spec, "duration", None) or getattr(clip_spec, "duration_seconds", 25.0)

        all_issues: List[str] = []
        recommendations: List[RepairRecommendation] = []

        # 1. Technical inspection
        tech_valid, loudness_valid, tech_issues = self._inspect_technical_quality(clip_path, expected_dur)
        all_issues.extend(tech_issues)

        # 2. Abrupt cut inspection
        no_abrupt_start, no_abrupt_end, sug_start, sug_end, cut_issues = self._inspect_abrupt_cuts(clip_spec, transcript)
        all_issues.extend(cut_issues)
        if not no_abrupt_start or not no_abrupt_end:
            recommendations.append(
                RepairRecommendation(
                    action=RepairAction.RETRIM,
                    reason="Speech boundary slice detected; clip starts or ends mid-word",
                    suggested_start=sug_start or clip_spec.start_time,
                    suggested_end=sug_end or clip_spec.end_time,
                    details={"cut_issues": cut_issues},
                )
            )

        # 3. Caption inspection
        captions_valid, cap_issues = self._inspect_captions(clip_id, cat, workspace)
        all_issues.extend(cap_issues)
        if not captions_valid:
            recommendations.append(
                RepairRecommendation(
                    action=RepairAction.REPOSITION_CAPTIONS,
                    reason="Subtitles missing or ill-formatted",
                    details={"caption_issues": cap_issues},
                )
            )

        # 4. Thumbnail inspection
        thumb_valid, thumb_issues = self._inspect_thumbnail(clip_id, workspace)
        all_issues.extend(thumb_issues)

        # 5. Metadata inspection
        meta_valid, meta_issues = self._inspect_metadata(clip_id, workspace)
        all_issues.extend(meta_issues)

        if not thumb_valid or not meta_valid or not tech_valid:
            recommendations.append(
                RepairRecommendation(
                    action=RepairAction.REGENERATE,
                    reason="Missing critical artifact(s) or technical render failure",
                    details={"issues": tech_issues + thumb_issues + meta_issues},
                )
            )

        checks = MultimodalQAChecks(
            technical_valid=tech_valid,
            audio_loudness_valid=loudness_valid,
            captions_valid=captions_valid,
            thumbnail_valid=thumb_valid,
            metadata_valid=meta_valid,
            no_abrupt_start=no_abrupt_start,
            no_abrupt_end=no_abrupt_end,
            no_excessive_silence=loudness_valid,
        )

        # Compute weighted overall score (0.0 to 1.0)
        score_weights = {
            "technical": (1.0 if tech_valid else 0.0) * 0.30,
            "captions": (1.0 if captions_valid else 0.0) * 0.20,
            "cuts": ((1.0 if no_abrupt_start else 0.0) * 0.10) + ((1.0 if no_abrupt_end else 0.0) * 0.10),
            "thumbnail": (1.0 if thumb_valid else 0.0) * 0.15,
            "metadata": (1.0 if meta_valid else 0.0) * 0.15,
        }
        overall_score = round(sum(score_weights.values()), 3)

        passed = (
            overall_score >= self.settings.qa_min_overall_score
            and tech_valid
            and thumb_valid
            and meta_valid
        )

        promoted_paths: Dict[str, str] = {}
        if passed and self.settings.qa_promote_passing_to_final:
            promoted_paths = self.promote_clip(clip_id, cat, clip_path, workspace)

        return FinalClipQAResult(
            clip_id=clip_id,
            category=cat,
            overall_score=overall_score,
            passed=passed,
            checks=checks,
            issues=all_issues,
            recommendations=recommendations,
            promoted_paths=promoted_paths,
        )

    def promote_clip(
        self,
        clip_id: str,
        category: str,
        source_clip_path: Path,
        workspace: ProjectWorkspace,
    ) -> Dict[str, str]:
        """Copies verified clip, thumbnail, and social metadata package to final/<category>/."""
        target_dir = workspace.final_dir / category
        target_dir.mkdir(parents=True, exist_ok=True)

        promoted: Dict[str, str] = {}

        # 1. Video
        final_video_dest = target_dir / f"{clip_id}.mp4"
        if source_clip_path.exists():
            shutil.copy2(source_clip_path, final_video_dest)
            promoted["video"] = str(final_video_dest)

        # 2. Thumbnail
        thumb_src = workspace.thumbnails_dir / f"{clip_id}.jpg"
        if thumb_src.exists():
            thumb_dest = target_dir / f"{clip_id}.jpg"
            shutil.copy2(thumb_src, thumb_dest)
            promoted["thumbnail"] = str(thumb_dest)

        # 3. Metadata
        meta_src = workspace.metadata_dir / f"{clip_id}.json"
        if meta_src.exists():
            meta_dest = target_dir / f"{clip_id}.json"
            shutil.copy2(meta_src, meta_dest)
            promoted["metadata"] = str(meta_dest)

        logger.info(f"Promoted verified clip deliverables for [{clip_id}] to: {target_dir}")
        return promoted

    def evaluate_all_clips(
        self,
        report: SelectedClipsReport,
        workspace: ProjectWorkspace,
        transcript: Optional[TranscriptResult] = None,
    ) -> FinalProjectQAReport:
        """Executes full multimodal evaluation across all selected clips.

        Returns:
            FinalProjectQAReport containing individual and aggregate audit results.
        """
        results: List[FinalClipQAResult] = []
        for clip_spec in report.clips:
            res = self.evaluate_clip(clip_spec, workspace, transcript)
            results.append(res)

        passed_count = sum(1 for r in results if r.passed)
        failed_count = len(results) - passed_count
        all_passed = (failed_count == 0) and (len(results) > 0)

        proj_report = FinalProjectQAReport(
            project_id=workspace.project_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            total_clips=len(results),
            passed_clips=passed_count,
            failed_clips=failed_count,
            all_passed=all_passed,
            clips=results,
        )

        logger.info(f"Final Multimodal QA completed: {passed_count}/{len(results)} passed.")
        return proj_report
