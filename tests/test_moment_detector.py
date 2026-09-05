"""Tests for EntertainmentMomentDetector multimodal reasoning and deduplication."""

from pathlib import Path
from backend.clip_detection.detector import EntertainmentMomentDetector, calculate_iou
from backend.config.settings import PipelineSettings
from backend.models.transcript import TranscriptResult, TranscriptSegment


def test_calculate_iou():
    # Identical
    assert calculate_iou(0.0, 10.0, 0.0, 10.0) == 1.0
    # Disjoint
    assert calculate_iou(0.0, 5.0, 5.0, 10.0) == 0.0
    # 50% overlap: [0, 10] and [5, 15] -> intersection is 5, union is 15 -> 0.333
    assert round(calculate_iou(0.0, 10.0, 5.0, 15.0), 2) == 0.33


def test_detect_candidates_with_dialogue():
    segments = [
        TranscriptSegment(id=1, start=0.0, end=5.0, text="Why did you decide to do this crazy experiment?"),
        TranscriptSegment(id=2, start=5.0, end=12.0, text="Well I honestly thought it would never work in a million years."),
        TranscriptSegment(id=3, start=12.0, end=20.0, text="And then suddenly the whole thing caught fire and exploded!"),
        TranscriptSegment(id=4, start=20.0, end=26.0, text="It was the most hilarious mistake of my entire life.")
    ]
    transcript = TranscriptResult(
        language="en",
        duration=26.0,
        text="Why did you decide to do this crazy experiment? Well I honestly thought it would never work in a million years. And then suddenly the whole thing caught fire and exploded! It was the most hilarious mistake of my entire life.",
        segments=segments
    )

    settings = PipelineSettings(min_candidate_duration=15.0, max_candidate_duration=35.0, min_candidate_score=0.40)
    detector = EntertainmentMomentDetector(settings=settings)
    report = detector.detect_candidates(transcript=transcript, video_duration=26.0)

    assert report.total_candidates >= 1
    best_candidate = report.candidates[0]
    assert best_candidate.scores.social_potential >= 0.40
    assert any(c in best_candidate.categories for c in ["funny", "surprising", "insightful", "shocking"])
    assert "experiment" in best_candidate.transcript.lower()

    # Verify markdown generation
    md = EntertainmentMomentDetector.generate_markdown_summary(report)
    assert "# Candidate Entertainment Moments Report" in md
    assert best_candidate.id in md
