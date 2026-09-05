"""Entertainment Moment Detection orchestrator with deduplication and Markdown reporting."""

from pathlib import Path
from typing import List, Optional

from backend.audio.analyzer import AudioSignalAnalyzer
from backend.clip_detection.contextual_window import ContextualWindow, ContextualWindowExtractor
from backend.clip_detection.multimodal_scorer import MultimodalScorer
from backend.config.settings import PipelineSettings, default_settings
from backend.models.candidate import CandidateMoment, CandidateReport
from backend.models.transcript import TranscriptResult, TranscriptSegment
from backend.models.vision import VisualAnalysisResult
from backend.utils.logger import logger


def calculate_iou(start_a: float, end_a: float, start_b: float, end_b: float) -> float:
    """Calculates Intersection over Union between two 1D time ranges."""
    inter_start = max(start_a, start_b)
    inter_end = min(end_a, end_b)
    intersection = max(0.0, inter_end - inter_start)

    union_start = min(start_a, start_b)
    union_end = max(end_a, end_b)
    union = union_end - union_start

    if union <= 0.0:
        return 0.0
    return intersection / union


class EntertainmentMomentDetector:
    """Detects, scores, and deduplicates entertainment-oriented short-form moments."""

    def __init__(self, settings: Optional[PipelineSettings] = None):
        self.settings = settings or default_settings
        self.window_extractor = ContextualWindowExtractor(
            min_duration=self.settings.min_candidate_duration,
            max_duration=self.settings.max_candidate_duration
        )
        self.audio_analyzer = AudioSignalAnalyzer()

    def deduplicate_candidates(
        self,
        candidates: List[CandidateMoment],
        max_iou: float = 0.50
    ) -> List[CandidateMoment]:
        """Merges or removes overlapping candidate moments, preserving higher scoring ones."""
        # Sort candidates descending by social potential score
        sorted_candidates = sorted(
            candidates,
            key=lambda c: (c.scores.social_potential, c.confidence),
            reverse=True
        )

        retained: List[CandidateMoment] = []
        for candidate in sorted_candidates:
            is_duplicate = False
            for existing in retained:
                iou = calculate_iou(
                    candidate.start_time, candidate.end_time,
                    existing.start_time, existing.end_time
                )
                if iou >= max_iou:
                    is_duplicate = True
                    break
            if not is_duplicate:
                retained.append(candidate)

        # Sort chronologically by start_time for downstream processing
        retained.sort(key=lambda c: c.start_time)
        return retained

    def detect_candidates(
        self,
        transcript: TranscriptResult,
        audio_path: Optional[Path] = None,
        visual_analysis: Optional[VisualAnalysisResult] = None,
        video_duration: float = 0.0
    ) -> CandidateReport:
        """Discovers candidate moments across transcript, audio, and vision inputs."""
        logger.info("Detecting candidate entertainment moments...")

        # Load audio energy profile if available
        rms_profile = None
        if audio_path and Path(audio_path).exists():
            try:
                rms_profile, _ = self.audio_analyzer.analyze_audio_energy(Path(audio_path))
            except Exception as e:
                logger.warning(f"Audio energy extraction failed, continuing without it: {e}")

        scorer = MultimodalScorer(audio_analyzer=self.audio_analyzer, rms_profile=rms_profile)
        windows = self.window_extractor.extract_windows(transcript)

        # Fallback if transcript was empty / no speech segments
        if not windows and video_duration >= self.settings.min_candidate_duration:
            logger.info("No speech windows extracted. Generating scene/time-based candidate window fallback.")
            step = 25.0
            t = 0.0
            while t + self.settings.min_candidate_duration <= video_duration:
                end_t = min(video_duration, t + 25.0)
                windows.append(
                    ContextualWindow(
                        start_time=t,
                        end_time=end_t,
                        segments=[
                            TranscriptSegment(
                                id=0,
                                start=t,
                                end=end_t,
                                text="[Visual/Ambient audio sequence]"
                            )
                        ]
                    )
                )
                t += step

        raw_candidates: List[CandidateMoment] = []
        for i, win in enumerate(windows, start=1):
            scores, categories, reason = scorer.score_window(win, visual_analysis)

            if scores.social_potential >= self.settings.min_candidate_score:
                candidate = CandidateMoment(
                    id=f"candidate_{i:03d}",
                    start_time=round(win.start_time, 2),
                    end_time=round(win.end_time, 2),
                    duration=round(win.duration, 2),
                    categories=categories,
                    transcript=win.full_text,
                    hook=win.hook_text,
                    payoff=win.payoff_text,
                    reason=reason,
                    confidence=0.88,
                    scores=scores
                )
                raw_candidates.append(candidate)

        # Deduplicate overlapping moments
        final_candidates = self.deduplicate_candidates(
            raw_candidates,
            max_iou=self.settings.max_candidate_overlap_iou
        )

        # Re-number IDs cleanly (candidate_001, candidate_002, ...)
        for idx, c in enumerate(final_candidates, start=1):
            c.id = f"candidate_{idx:03d}"

        logger.info(f"Discovered {len(final_candidates)} distinct candidate moments (from {len(windows)} windows).")
        return CandidateReport(
            total_candidates=len(final_candidates),
            candidates=final_candidates
        )

    @staticmethod
    def generate_markdown_summary(report: CandidateReport) -> str:
        """Generates human-readable candidates.md developer documentation."""
        lines = [
            "# Candidate Entertainment Moments Report",
            f"\nTotal Candidates Identified: **{report.total_candidates}**\n",
            "| ID | Start | End | Duration | Categories | Social Potential | Hook Strength |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]

        for c in report.candidates:
            cats = ", ".join(c.categories)
            lines.append(
                f"| `{c.id}` | {c.start_time:.1f}s | {c.end_time:.1f}s | {c.duration:.1f}s | {cats} | **{c.scores.social_potential:.2f}** | {c.scores.hook_strength:.2f} |"
            )

        lines.append("\n---\n")
        lines.append("## Detailed Candidate Breakdown\n")

        for c in report.candidates:
            cats_badges = " ".join(f"`#{cat}`" for cat in c.categories)
            lines.extend([
                f"### {c.id} ({c.start_time:.1f}s - {c.end_time:.1f}s) {cats_badges}",
                f"- **Reason:** {c.reason}",
                f"- **Hook:** *\"{c.hook}\"*",
                f"- **Payoff:** *\"{c.payoff}\"*",
                f"- **Scores:** Humor: `{c.scores.humor:.2f}` | Surprise: `{c.scores.surprise:.2f}` | Emotion: `{c.scores.emotion:.2f}` | Visual: `{c.scores.visual_interest:.2f}` | Context: `{c.scores.context_completeness:.2f}`",
                f"- **Transcript:**\n> {c.transcript}\n"
            ])

        return "\n".join(lines)
