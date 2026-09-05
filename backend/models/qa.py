"""Data models for automated Quality Assurance (QA) results."""

from typing import Any, Dict, List
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

