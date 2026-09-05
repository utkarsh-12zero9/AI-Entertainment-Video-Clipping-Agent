"""Script to run moment detection on a realistic conversational interview transcript."""

import json
from pathlib import Path

from backend.clip_detection.detector import EntertainmentMomentDetector
from backend.config.settings import PipelineSettings
from backend.models.transcript import TranscriptResult, TranscriptSegment, WordTimestamp
from backend.models.vision import FaceBoundingBox, FrameVisualAnalysis, SceneBoundary, VisualAnalysisResult
from backend.pipeline.workspace import WorkspaceManager

# Create realistic 60-second podcast/interview scenario
segments = [
    TranscriptSegment(
        id=1,
        start=0.0,
        end=5.2,
        text="So what is the most insane coding bug you ever shipped into production?",
        words=[
            WordTimestamp(word="So", start=0.0, end=0.4),
            WordTimestamp(word="what", start=0.5, end=0.8),
            WordTimestamp(word="is", start=0.9, end=1.1),
            WordTimestamp(word="the", start=1.2, end=1.4),
            WordTimestamp(word="most", start=1.5, end=1.9),
            WordTimestamp(word="insane", start=2.0, end=2.6),
            WordTimestamp(word="coding", start=2.7, end=3.1),
            WordTimestamp(word="bug", start=3.2, end=3.6),
            WordTimestamp(word="you", start=3.7, end=3.9),
            WordTimestamp(word="ever", start=4.0, end=4.4),
            WordTimestamp(word="shipped", start=4.5, end=4.9),
            WordTimestamp(word="into", start=5.0, end=5.2),
        ]
    ),
    TranscriptSegment(
        id=2,
        start=5.5,
        end=14.0,
        text="Oh man, on my very first Friday at the startup, I accidentally ran DROP DATABASE in production right before happy hour.",
    ),
    TranscriptSegment(
        id=3,
        start=14.5,
        end=24.8,
        text="And the funniest thing was our CTO walked over, took a sip of coffee, and said 'Welcome to the team, now go fix it'.",
    ),
    TranscriptSegment(
        id=4,
        start=25.5,
        end=32.0,
        text="Everyone in the office burst out laughing because they had all done the exact same mistake before.",
    ),
    TranscriptSegment(
        id=5,
        start=33.0,
        end=42.0,
        text="It taught me the ultimate lesson about automated backups and never deploying on Friday afternoon.",
    ),
]

transcript = TranscriptResult(
    language="en",
    duration=45.0,
    text=" ".join(s.text for s in segments),
    segments=segments
)

# Mock visual frames matching face presence
frames = [
    FrameVisualAnalysis(
        frame=f"frame_{i:06d}.jpg",
        timestamp=float(i * 3),
        num_faces=1,
        faces=[FaceBoundingBox(x=100, y=100, w=200, h=200)],
        brightness=110.0,
        contrast=55.0,
        sharpness=120.0,
        is_blurry=False,
        visual_activity="moderate",
        scene_type="medium_shot",
        confidence=0.92
    )
    for i in range(1, 15)
]

visual_report = VisualAnalysisResult(
    video_duration=45.0,
    total_frames_analyzed=len(frames),
    scenes=[SceneBoundary(scene_id=1, start=0.0, end=45.0, duration=45.0)],
    frames=frames
)

workspace = WorkspaceManager.create_workspace(Path("./projects/podcast_demo_001"))
detector = EntertainmentMomentDetector(settings=PipelineSettings(min_candidate_duration=15.0, max_candidate_duration=35.0, min_candidate_score=0.45))

report = detector.detect_candidates(
    transcript=transcript,
    audio_path=None,
    visual_analysis=visual_report,
    video_duration=45.0
)

md_summary = EntertainmentMomentDetector.generate_markdown_summary(report)
WorkspaceManager.save_transcript(transcript, workspace)
WorkspaceManager.save_visual_analysis(visual_report, workspace)
WorkspaceManager.save_candidates(report, md_summary, workspace)

print(f"Generated {report.total_candidates} candidate entertainment moments.")
print("\n" + md_summary)
