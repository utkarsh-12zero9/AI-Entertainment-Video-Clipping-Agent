"""Data models for automated Quality Assurance (QA) results."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ClipQAChecks(BaseModel):
    """Granular pass/fail results for individual QA checks."""
    duration: bool = Field(default=True, description="Duration matches specification within tolerance")
    audio: bool = Field(default=True, description="Audio stream exists and is usable")
    video: bool = Field(default=True, description="Video stream exists and has valid dimensions")
    sync: bool = Field(default=True, description="Timestamps and streams are in sync")
    corruption: bool = Field(default=False, description="True if corruption was detected (false is good)")
    black_frames: bool = Field(default=False, description="True if excessive black frames were detected")
    silence: bool = Field(default=False, description="True if excessive dead silence was detected")


class ClipQAResult(BaseModel):
    """QA assessment outcome for an individual extracted clip."""
    clip_id: str = Field(description="Clip identifier e.g. funny_001")
    file_path: str = Field(description="Relative or absolute path to extracted video file")
    expected_duration: float = Field(default=0.0, description="Expected duration in seconds")
    actual_duration: float = Field(default=0.0, description="Actual duration in seconds")
    duration_diff: float = Field(default=0.0, description="Difference between expected and actual duration")
    passed: bool = Field(description="Whether the clip passed all critical QA checks")
    checks: ClipQAChecks = Field(description="Individual check results")
    details: Dict[str, Any] = Field(default_factory=dict, description="Metadata metrics extracted during QA")
    errors: List[str] = Field(default_factory=list, description="Descriptions of any detected faults")

    @property
    def issues(self) -> List[str]:
        return self.errors


class ProjectQAReport(BaseModel):
    """Aggregated QA report for all clips in a project."""
    project_id: str = Field(default="project", description="Associated project identifier")
    created_at: str = Field(default="", description="Timestamp when QA report was generated")
    total_clips: int = Field(description="Total number of clips inspected")
    passed_clips: int = Field(description="Number of clips passing QA")
    failed_clips: int = Field(description="Number of clips failing QA")
    all_passed: bool = Field(description="Whether 100% of clips passed QA")
    results: List[ClipQAResult] = Field(default_factory=list, description="Per-clip QA result entries")

    @property
    def clip_results(self) -> List[ClipQAResult]:
        return self.results


class MultimodalQAChecks(BaseModel):
    """Detailed checks evaluated by the Stage 10 Final Multimodal QA Agent."""
    technical_valid: bool = Field(default=True, description="Video decodable, valid duration, 1080x1920, audio present")
    audio_loudness_valid: bool = Field(default=True, description="Audio volume is within acceptable loudness envelope")
    captions_valid: bool = Field(default=True, description="Captions exist, non-empty, and render inside safe areas")
    thumbnail_valid: bool = Field(default=True, description="Thumbnail exists, 1080x1920, good clarity and contrast")
    metadata_valid: bool = Field(default=True, description="Platform social metadata packages are complete")
    no_abrupt_start: bool = Field(default=True, description="Start does not slice mid-word or begin unnaturally")
    no_abrupt_end: bool = Field(default=True, description="Ending preserves complete sentence and punchline/payoff")
    no_excessive_silence: bool = Field(default=True, description="No trailing or leading dead silence")


class RepairAction:
    """Standard repair actions when QA detects issues."""
    RETRIM = "RETRIM"
    REPOSITION_CAPTIONS = "REPOSITION_CAPTIONS"
    REGENERATE = "REGENERATE"
    NONE = "NONE"


class RepairRecommendation(BaseModel):
    """Actionable structured recommendation to fix a failing clip."""
    action: str = Field(description="Recommended action e.g. RETRIM, REPOSITION_CAPTIONS, REGENERATE, NONE")
    reason: str = Field(description="Explanation of why repair is needed")
    suggested_start: Optional[float] = Field(default=None, description="Suggested new start timestamp in seconds")
    suggested_end: Optional[float] = Field(default=None, description="Suggested new end timestamp in seconds")
    details: Dict[str, Any] = Field(default_factory=dict, description="Supplementary diagnostic information")


class FinalClipQAResult(BaseModel):
    """Final comprehensive QA evaluation for an exported social clip."""
    clip_id: str = Field(description="Unique clip identifier")
    category: str = Field(description="Clip category name")
    overall_score: float = Field(description="Composite multimodal quality score (0.0 to 1.0)")
    passed: bool = Field(description="Whether the clip passed all mandatory criteria")
    checks: MultimodalQAChecks = Field(description="Fine-grained pass/fail status for each multimodal dimension")
    issues: List[str] = Field(default_factory=list, description="List of detected defects or warnings")
    recommendations: List[RepairRecommendation] = Field(default_factory=list, description="Actionable repair steps if failed")
    promoted_paths: Dict[str, str] = Field(default_factory=dict, description="Paths to final promoted files if passed")


class FinalProjectQAReport(BaseModel):
    """Project-wide audit report generated by Stage 10 Final Multimodal QA Agent."""
    project_id: str = Field(description="Unique project identifier")
    created_at: str = Field(description="Timestamp of QA execution")
    total_clips: int = Field(description="Total clips inspected")
    passed_clips: int = Field(description="Number of clips meeting quality threshold")
    failed_clips: int = Field(description="Number of clips requiring remediation")
    all_passed: bool = Field(description="True if 100% of clips passed final QA")
    clips: List[FinalClipQAResult] = Field(default_factory=list, description="Per-clip evaluation outcomes")


