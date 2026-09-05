"""Tests for ClipSpecification and SelectedClipsReport models."""

from backend.models.clip import ClipSpecification, SelectedClipsReport


def test_clip_specification_serialization():
    spec = ClipSpecification(
        clip_id="funny_001",
        candidate_id="candidate_001",
        start_time=12.5,
        end_time=37.5,
        duration=25.0,
        category="funny",
        categories=["funny", "reaction"],
        score=0.92,
        reason="Strong comedic setup with perfect punchline.",
        hook="Why did the server crash?",
        payoff="Because it had too many open connections to reality.",
        transcript="Why did the server crash? Because it had too many open connections to reality."
    )

    report = SelectedClipsReport(
        total_selected=1,
        clips=[spec]
    )

    data = report.model_dump()
    assert data["total_selected"] == 1
    assert data["clips"][0]["clip_id"] == "funny_001"
    assert data["clips"][0]["duration"] == 25.0
    assert data["clips"][0]["category"] == "funny"
