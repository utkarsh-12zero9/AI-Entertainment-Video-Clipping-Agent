"""Tests for candidate moment models."""

from backend.models.candidate import CandidateMoment, CandidateReport, CandidateScores


def test_candidate_models_serialization():
    scores = CandidateScores(
        hook_strength=0.90,
        humor=0.85,
        surprise=0.75,
        emotion=0.60,
        visual_interest=0.80,
        context_completeness=0.95,
        social_potential=0.87
    )
    moment = CandidateMoment(
        id="candidate_001",
        start_time=10.0,
        end_time=35.0,
        duration=25.0,
        categories=["funny", "punchline"],
        transcript="Why did the programmer quit? Because they did not get arrays.",
        hook="Why did the programmer quit?",
        payoff="Because they did not get arrays.",
        reason="Classic setup and punchline structure with high comedic timing.",
        confidence=0.92,
        scores=scores
    )
    report = CandidateReport(
        total_candidates=1,
        candidates=[moment]
    )

    data = report.model_dump()
    assert data["total_candidates"] == 1
    assert data["candidates"][0]["id"] == "candidate_001"
    assert data["candidates"][0]["scores"]["humor"] == 0.85
    assert "funny" in data["candidates"][0]["categories"]
