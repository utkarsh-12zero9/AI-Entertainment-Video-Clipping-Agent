"""Models package."""
from backend.models.candidate import CandidateMoment, CandidateReport, CandidateScores
from backend.models.clip import ClipSpecification, SelectedClipsReport
from backend.models.qa import ClipQAChecks, ClipQAResult, ProjectQAReport
from backend.models.transcript import TranscriptResult, TranscriptSegment, WordTimestamp
from backend.models.video import ProjectWorkspace, VideoMetadata
from backend.models.vision import (
    FaceBoundingBox,
    FrameIndex,
    FrameInfo,
    FrameVisualAnalysis,
    SceneBoundary,
    VisualAnalysisResult,
)

__all__ = [
    "ProjectWorkspace",
    "VideoMetadata",
    "TranscriptResult",
    "TranscriptSegment",
    "WordTimestamp",
    "SceneBoundary",
    "FrameInfo",
    "FrameIndex",
    "FaceBoundingBox",
    "FrameVisualAnalysis",
    "VisualAnalysisResult",
    "CandidateMoment",
    "CandidateScores",
    "CandidateReport",
    "ClipSpecification",
    "SelectedClipsReport",
    "ClipQAChecks",
    "ClipQAResult",
    "ProjectQAReport",
]
