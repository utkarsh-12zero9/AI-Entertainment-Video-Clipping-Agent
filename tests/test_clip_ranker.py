"""Tests for ClipRanker weighted scoring, diversity enforcement, and category naming."""

from backend.config.settings import PipelineSettings
from backend.models.candidate import CandidateMoment, CandidateReport, CandidateScores
from backend.models.transcript import TranscriptResult, TranscriptSegment
from backend.scoring.ranker import ClipRanker


def test_clip_ranker_weighted_and_diversity():
    segments = [
        TranscriptSegment(id=1, start=0.0, end=10.0, text="First topic about engineering systems."),
        TranscriptSegment(id=2, start=10.5, end=25.0, text="Hilarious story about accidentally deleting database."),
        TranscriptSegment(id=3, start=26.0, end=40.0, text="Another variant of deleting database."), # Same cluster
        TranscriptSegment(id=4, start=60.0, end=85.0, text="Completely separate emotional topic about startup struggles."),
    ]
    transcript = TranscriptResult(
        language="en",
        duration=90.0,
        text="Full text",
        segments=segments
    )

    c1 = CandidateMoment(
        id="c1",
        start_time=10.5,
        end_time=35.0,
        duration=24.5,
        categories=["funny"],
        transcript="Hilarious story about accidentally deleting database.",
        hook="Hilarious story",
        payoff="deleting database.",
        reason="Funny startup story",
        confidence=0.95,
        scores=CandidateScores(hook_strength=0.9, humor=0.95, social_potential=0.92)
    )

    # c2 starts only 5 seconds after c1 (temporal cluster, should be filtered by diversity)
    c2 = CandidateMoment(
        id="c2",
        start_time=15.0,
        end_time=38.0,
        duration=23.0,
        categories=["funny"],
        transcript="Duplicate funny moment",
        hook="Variant",
        payoff="Payoff",
        reason="Variant moment",
        confidence=0.85,
        scores=CandidateScores(hook_strength=0.8, humor=0.80, social_potential=0.82)
    )

    # c3 is at 60s (independent moment)
    c3 = CandidateMoment(
        id="c3",
        start_time=60.0,
        end_time=85.0,
        duration=25.0,
        categories=["emotional"],
        transcript="Completely separate emotional topic about startup struggles.",
        hook="Startup struggles",
        payoff="Lessons learned",
        reason="Emotional story",
        confidence=0.90,
        scores=CandidateScores(hook_strength=0.85, emotion=0.90, social_potential=0.86)
    )

    report = CandidateReport(total_candidates=3, candidates=[c1, c2, c3])

    settings = PipelineSettings(
        max_clips=5,
        min_clip_spacing_sec=15.0 # 15s spacing
    )
    ranker = ClipRanker(settings=settings)
    selected = ranker.rank_and_select_clips(report, transcript, video_duration=90.0)

    # Out of 3 candidates, c2 should be filtered out by temporal spacing with c1
    assert selected.total_selected == 2
    ids = [clip.clip_id for clip in selected.clips]
    assert "funny_001" in ids
    assert "emotional_001" in ids
    assert selected.clips[0].score >= selected.clips[1].score
