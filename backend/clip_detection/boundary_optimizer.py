"""Boundary optimizer ensuring clean sentence boundaries, pronoun context, and natural payoff."""

import re
from typing import List, Optional, Tuple

from backend.config.settings import PipelineSettings, default_settings
from backend.models.candidate import CandidateMoment
from backend.models.transcript import TranscriptResult, TranscriptSegment
from backend.utils.logger import logger

# Unexplained dangling pronouns that should not open a short clip
DANGLING_PRONOUNS = {"he", "she", "it", "they", "that", "this", "him", "her", "them", "these", "those"}


class ClipBoundaryOptimizer:
    """Optimizes candidate start and end timestamps to natural speech and linguistic boundaries."""

    def __init__(self, settings: Optional[PipelineSettings] = None):
        self.settings = settings or default_settings

    def _find_overlapping_segments(
        self,
        transcript: TranscriptResult,
        start_time: float,
        end_time: float
    ) -> List[TranscriptSegment]:
        """Finds all speech segments overlapping with the given range."""
        return [
            s for s in transcript.segments
            if not (s.end < start_time or s.start > end_time)
        ]

    def _get_segment_index(self, transcript: TranscriptResult, segment: TranscriptSegment) -> int:
        """Finds index of segment in transcript."""
        for idx, s in enumerate(transcript.segments):
            if s.id == segment.id:
                return idx
        return 0

    def optimize_boundaries(
        self,
        candidate: CandidateMoment,
        transcript: TranscriptResult,
        video_duration: float
    ) -> Tuple[float, float, str, str, str]:
        """Snaps candidate to clean sentence starts, preserves punchline, and adds breathing room.

        Returns:
            (optimized_start, optimized_end, optimized_hook, optimized_payoff, optimized_transcript)
        """
        overlapping = self._find_overlapping_segments(transcript, candidate.start_time, candidate.end_time)

        if not overlapping:
            # Fallback if video had no speech segments
            start_t = max(0.0, round(candidate.start_time, 2))
            end_t = min(video_duration, round(start_t + self.settings.target_clip_duration, 2))
            return start_t, end_t, candidate.hook, candidate.payoff, candidate.transcript

        first_seg = overlapping[0]
        last_seg = overlapping[-1]

        opt_start = first_seg.start

        # Check if first segment starts with a dangling pronoun (e.g. "He then said...")
        words = first_seg.text.strip().split()
        if words:
            first_word_clean = re.sub(r"[^\w]", "", words[0].lower())
            if first_word_clean in DANGLING_PRONOUNS:
                # Try to pull in the immediately preceding segment if available
                first_idx = self._get_segment_index(transcript, first_seg)
                if first_idx > 0:
                    prev_seg = transcript.segments[first_idx - 1]
                    potential_duration = last_seg.end - prev_seg.start
                    if potential_duration <= self.settings.max_clip_duration:
                        opt_start = prev_seg.start
                        overlapping.insert(0, prev_seg)

        # Snap end time to last segment end + small audio padding (laughter/reaction room)
        opt_end = last_seg.end + self.settings.boundary_audio_padding_sec
        opt_end = min(video_duration, round(opt_end, 2))

        # Enforce target duration window [min_clip_duration, max_clip_duration]
        current_duration = opt_end - opt_start

        if current_duration > self.settings.max_clip_duration:
            # Trim from beginning or end while preserving punchline
            # Punchline at end is sacred, so shift start forward if possible
            while len(overlapping) > 1 and (overlapping[-1].end - overlapping[1].start) >= self.settings.min_clip_duration:
                overlapping.pop(0)
                opt_start = overlapping[0].start
                if (overlapping[-1].end + self.settings.boundary_audio_padding_sec - opt_start) <= self.settings.max_clip_duration:
                    break
            opt_end = min(video_duration, overlapping[-1].end + self.settings.boundary_audio_padding_sec)

        elif current_duration < self.settings.min_clip_duration:
            # Expand slightly if needed to reach min duration
            last_idx = self._get_segment_index(transcript, overlapping[-1])
            if last_idx + 1 < len(transcript.segments):
                next_seg = transcript.segments[last_idx + 1]
                if (next_seg.end - opt_start) <= self.settings.max_clip_duration:
                    overlapping.append(next_seg)
                    opt_end = min(video_duration, next_seg.end + self.settings.boundary_audio_padding_sec)

        opt_start = max(0.0, round(opt_start, 2))
        opt_end = min(video_duration, round(opt_end, 2))

        # Build clean texts
        opt_transcript = " ".join(s.text for s in overlapping).strip()
        opt_hook = overlapping[0].text if overlapping else candidate.hook
        opt_payoff = overlapping[-1].text if overlapping else candidate.payoff

        return opt_start, opt_end, opt_hook, opt_payoff, opt_transcript
