"""Models package."""
from backend.models.candidate import CandidateMoment, CandidateReport, CandidateScores
from backend.models.caption import CaptionChunk, CaptionWord, ClipCaptionResult, ProjectCaptionReport
from backend.models.clip import ClipSpecification, SelectedClipsReport
from backend.models.editing import CropWindow, EditedClipResult, ProjectEditReport
from backend.models.job import JobState, StageExecutionRecord, StageStatus
from backend.models.metadata import ClipSocialMetadata, PlatformMetadata, ProjectMetadataReport
from backend.models.qa import (
    ClipQAChecks,
    ClipQAResult,
    FinalClipQAResult,
    FinalProjectQAReport,
    MultimodalQAChecks,
    ProjectQAReport,
    RepairAction,
    RepairRecommendation,
)
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
    "MultimodalQAChecks",
    "RepairAction",
    "RepairRecommendation",
    "FinalClipQAResult",
    "FinalProjectQAReport",
    "CropWindow",
    "EditedClipResult",
    "ProjectEditReport",
    "CaptionWord",
    "CaptionChunk",
    "ClipCaptionResult",
    "ProjectCaptionReport",
    "PlatformMetadata",
    "ClipSocialMetadata",
    "ProjectMetadataReport",
    "JobState",
    "StageStatus",
    "StageExecutionRecord",
]



