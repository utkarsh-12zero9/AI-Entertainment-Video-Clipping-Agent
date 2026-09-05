"""Contextual speech window extraction for candidate moment detection."""

from typing import List, Tuple
from backend.models.transcript import TranscriptResult, TranscriptSegment


class ContextualWindow:
    """Represents a coherent sequence of speech segments forming a potential candidate window."""
    def __init__(
        self,
        start_time: float,
        end_time: float,
        segments: List[TranscriptSegment]
    ):
        self.start_time = start_time
        self.end_time = end_time
        self.segments = segments

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    @property
    def full_text(self) -> str:
        return " ".join(s.text for s in self.segments).strip()

    @property
    def hook_text(self) -> str:
        """First segment or first 10 words."""
        if not self.segments:
            return ""
        return self.segments[0].text

    @property
    def payoff_text(self) -> str:
        """Final segment."""
        if not self.segments:
            return ""
        return self.segments[-1].text


class ContextualWindowExtractor:
    """Extracts overlapping contextual speech windows matching target clip duration constraints."""

    def __init__(
        self,
        min_duration: float = 15.0,
        max_duration: float = 45.0,
        step_segments: int = 1
    ):
        self.min_duration = min_duration
        self.max_duration = max_duration
        self.step_segments = step_segments

    def extract_windows(self, transcript: TranscriptResult) -> List[ContextualWindow]:
        """Extracts contextual speech windows from transcribed segments."""
        segments = transcript.segments
        if not segments:
            # Fallback if no speech segments (e.g. video without dialogue)
            return []

        windows: List[ContextualWindow] = []
        n = len(segments)

        for i in range(0, n, self.step_segments):
            window_segments: List[TranscriptSegment] = []
            for j in range(i, n):
                window_segments.append(segments[j])
                dur = window_segments[-1].end - window_segments[0].start

                if self.min_duration <= dur <= self.max_duration:
                    windows.append(
                        ContextualWindow(
                            start_time=window_segments[0].start,
                            end_time=window_segments[-1].end,
                            segments=list(window_segments)
                        )
                    )
                elif dur > self.max_duration:
                    break

        return windows
