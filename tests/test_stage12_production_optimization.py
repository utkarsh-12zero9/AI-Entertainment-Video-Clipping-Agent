"""Comprehensive unit and integration test suite for Stage 12: Production Optimization."""

from datetime import datetime, timezone
import json
from pathlib import Path
import pytest

from backend.config.settings import PipelineSettings
from backend.models.candidate import CandidateMoment, CandidateReport, CandidateScores
from backend.models.clip import ClipSpecification, SelectedClipsReport
from backend.models.job import JobState, PipelineStages, StageStatus
from backend.models.transcript import TranscriptResult
from backend.pipeline.orchestrator import PipelineOrchestrator
from backend.pipeline.workspace import WorkspaceManager
from backend.scoring.deduplicator import SemanticClipDeduplicator
from backend.scoring.ranker import ClipRanker


def create_dummy_candidate(
    cid: str,
    start: float,
    end: float,
    category: str,
    hook: str,
    payoff: str,
    hook_strength: float = 0.85,
    humor: float = 0.80,
) -> CandidateMoment:
    """Helper to instantiate mock CandidateMoment objects."""
    return CandidateMoment(
        id=cid,
        start_time=start,
        end_time=end,
        duration=end - start,
        categories=[category],
        transcript=f"{hook} Here is the middle discussion that builds context. {payoff}",
        hook=hook,
        payoff=payoff,
        reason="Test candidate",
        confidence=0.90,
        scores=CandidateScores(
            hook_strength=hook_strength,
            humor=humor,
            emotion=0.75,
            payoff=0.80,
            visual_interest=0.70,
            context_completeness=0.85,
            social_potential=0.85,
        ),
    )


def test_semantic_deduplication_detection():
    """Verifies that SemanticClipDeduplicator detects identical or near-duplicate joke transcripts."""
    dedup = SemanticClipDeduplicator()

    # Exact or near-identical text
    text_1 = "Why did the chicken cross the road? To get to the other side of the road!"
    text_2 = "Why did the chicken cross the road? To get to the other side!"
    is_dup, sim = dedup.are_transcripts_duplicate(text_1, text_2)
    assert is_dup is True
    assert sim >= 0.65

    # Completely different topics
    text_3 = "The quantum physics experiment revealed unexpected particles under high pressure."
    is_dup_diff, sim_diff = dedup.are_transcripts_duplicate(text_1, text_3)
    assert is_dup_diff is False
    assert sim_diff < 0.20


def test_category_diversity_and_quota_enforcement():
    """Verifies that no single category exceeds the configured maximum quota (e.g. 2 clips)."""
    settings = PipelineSettings(
        category_max_clips_per_type=2,
        min_clip_spacing_sec=5.0,
    )
    dedup = SemanticClipDeduplicator(settings=settings)

    # 4 funny candidates, 2 insightful candidates
    candidates = [
        {"candidate": create_dummy_candidate("c1", 10.0, 30.0, "Humor", "Joke one", "Punchline one"), "score": 0.95, "start": 10.0, "transcript": "Joke one punchline one"},
        {"candidate": create_dummy_candidate("c2", 40.0, 60.0, "Humor", "Joke two", "Punchline two"), "score": 0.92, "start": 40.0, "transcript": "Joke two punchline two"},
        {"candidate": create_dummy_candidate("c3", 70.0, 90.0, "Humor", "Joke three", "Punchline three"), "score": 0.90, "start": 70.0, "transcript": "Joke three punchline three"},
        {"candidate": create_dummy_candidate("c4", 100.0, 120.0, "Humor", "Joke four", "Punchline four"), "score": 0.88, "start": 100.0, "transcript": "Joke four punchline four"},
        {"candidate": create_dummy_candidate("c5", 130.0, 150.0, "Insightful", "Secret one", "Payoff one"), "score": 0.85, "start": 130.0, "transcript": "Secret one payoff one"},
        {"candidate": create_dummy_candidate("c6", 160.0, 180.0, "Insightful", "Secret two", "Payoff two"), "score": 0.82, "start": 160.0, "transcript": "Secret two payoff two"},
    ]

    diversified = dedup.filter_and_diversify(candidates, max_clips=5)
    
    # Check that max clips from "Humor" is capped at 2
    humor_count = sum(1 for c in diversified if c["candidate"].categories[0] == "Humor")
    insightful_count = sum(1 for c in diversified if c["candidate"].categories[0] == "Insightful")
    assert humor_count == 2
    assert insightful_count == 2
    assert len(diversified) == 4


def test_hook_scoring_bonus_and_filler_penalty():
    """Verifies that punchy openings receive a bonus while filler starts are penalized."""
    settings = PipelineSettings(
        hook_first_3s_boost=0.08,
        filler_words_penalty=0.10,
    )
    ranker = ClipRanker(settings=settings)

    base_cand = create_dummy_candidate("c1", 10.0, 35.0, "Humor", "Standard statement here", "Payoff")

    # 1. Clean punchy question hook
    score_punchy = ranker.calculate_weighted_score(base_cand, transcript_text="Did you know this crazy fact?")

    # 2. Filler words opening
    score_filler = ranker.calculate_weighted_score(base_cand, transcript_text="Um, uh, so yeah, basically this happened.")

    # Punchy hook must outrank filler hook
    assert score_punchy > score_filler
    assert (score_punchy - score_filler) >= 0.15


def test_orchestrator_candidate_review_fine_tuning(tmp_path: Path):
    """Verifies that review_candidates supports rejection, boundary editing, and category reassignment."""
    workspace = WorkspaceManager.create_workspace(tmp_path)

    initial_report = SelectedClipsReport(
        project_id=workspace.project_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        source_video=str(tmp_path / "dummy.mp4"),
        total_selected=3,
        clips=[
            ClipSpecification(
                clip_id="clip_001",
                candidate_id="cand_001",
                start_time=10.0,
                end_time=30.0,
                duration=20.0,
                score=0.90,
                hook="Opening 1",
                payoff="Ending 1",
                transcript="Full transcript 1",
                reason="Rank 1",
                category="General",
            ),
            ClipSpecification(
                clip_id="clip_002",
                candidate_id="cand_002",
                start_time=40.0,
                end_time=60.0,
                duration=20.0,
                score=0.85,
                hook="Opening 2",
                payoff="Ending 2",
                transcript="Full transcript 2",
                reason="Rank 2",
                category="Humor",
            ),
            ClipSpecification(
                clip_id="clip_003",
                candidate_id="cand_003",
                start_time=70.0,
                end_time=95.0,
                duration=25.0,
                score=0.80,
                hook="Opening 3",
                payoff="Ending 3",
                transcript="Full transcript 3",
                reason="Rank 3",
                category="Insightful",
            ),
        ]
    )
    WorkspaceManager.save_selected_clips(initial_report, workspace)

    orchestrator = PipelineOrchestrator()

    # Reject clip_002, modify clip_001 time boundaries and category
    updated_report = orchestrator.review_candidates(
        project_dir=workspace.root,
        rejected_ids=["clip_002"],
        time_adjustments={"clip_001": (12.0, 35.0)},
        category_overrides={"clip_001": "Dramatic"},
    )

    assert updated_report.total_selected == 2
    assert "clip_002" not in [c.clip_id for c in updated_report.clips]

    clip_1 = next(c for c in updated_report.clips if c.clip_id == "clip_001")
    assert clip_1.start_time == 12.0
    assert clip_1.end_time == 35.0
    assert clip_1.duration == 23.0
    assert clip_1.category == "Dramatic"
