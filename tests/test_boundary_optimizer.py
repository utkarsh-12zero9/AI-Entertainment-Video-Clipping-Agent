"""Tests for ClipBoundaryOptimizer sentence snapping, pronoun handling, and breathing room."""

from backend.clip_detection.boundary_optimizer import ClipBoundaryOptimizer
from backend.config.settings import PipelineSettings
from backend.models.candidate import CandidateMoment, CandidateScores
from backend.models.transcript import TranscriptResult, TranscriptSegment


def test_boundary_optimizer_pronoun_expansion():
    # Segment 1 introduces subject, Segment 2 starts with dangling pronoun "He"
    segments = [
        TranscriptSegment(id=1, start=0.0, end=4.0, text="John was working late in the data center."),
        TranscriptSegment(id=2, start=4.5, end=15.0, text="He accidentally tripped over the main power cable."),
        TranscriptSegment(id=3, start=15.5, end=25.0, text="And the entire building went completely dark!"),
    ]
    transcript = TranscriptResult(
        language="en",
        duration=25.0,
        text="John was working late in the data center. He accidentally tripped over the main power cable. And the entire building went completely dark!",
        segments=segments
    )

    candidate = CandidateMoment(
        id="candidate_001",
        start_time=4.5, # Starts at segment 2 ("He...")
        end_time=25.0,
        duration=20.5,
        categories=["funny"],
        transcript="He accidentally tripped over the main power cable. And the entire building went completely dark!",
        hook="He accidentally tripped",
        payoff="building went completely dark!",
        reason="Funny mishap",
        confidence=0.90,
        scores=CandidateScores(humor=0.8)
    )

    settings = PipelineSettings(
        min_clip_duration=20.0,
        max_clip_duration=30.0,
        boundary_audio_padding_sec=0.3
    )
    optimizer = ClipBoundaryOptimizer(settings=settings)

    opt_start, opt_end, opt_hook, opt_payoff, opt_transcript = optimizer.optimize_boundaries(
        candidate=candidate,
        transcript=transcript,
        video_duration=26.0
    )

    # Verifies that optimizer pulled in segment 1 ("John...") to avoid starting on dangling "He"
    assert opt_start == 0.0
    assert "John was working" in opt_transcript
    assert opt_end >= 25.3 # Includes breathing room
    assert (opt_end - opt_start) >= 20.0
