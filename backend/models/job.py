"""Data models for orchestration job lifecycle, execution state, and checkpoints."""

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class StageStatus(str, Enum):
    """Lifecycle status for an individual pipeline stage."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StageExecutionRecord(BaseModel):
    """Execution telemetry and timing for a single pipeline stage."""
    stage_name: str = Field(description="Stage identifier e.g. ingestion, transcription, etc.")
    status: StageStatus = Field(default=StageStatus.PENDING, description="Current stage status")
    started_at: Optional[str] = Field(default=None, description="ISO timestamp when stage began")
    completed_at: Optional[str] = Field(default=None, description="ISO timestamp when stage finished")
    duration_seconds: float = Field(default=0.0, description="Duration in seconds")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    artifacts_produced: List[str] = Field(default_factory=list, description="Relative paths to produced artifacts")


class PipelineStages(str, Enum):
    """Enumeration of all pipeline stages in strict sequential order."""
    INGESTION = "ingestion"
    AUDIO_EXTRACTION = "audio_extraction"
    TRANSCRIPTION = "transcription"
    SCENE_DETECTION = "scene_detection"
    FRAME_SAMPLING = "frame_sampling"
    VISUAL_ANALYSIS = "visual_analysis"
    MOMENT_DETECTION = "moment_detection"
    RANKING = "ranking"
    CANDIDATE_REVIEW = "candidate_review"
    RAW_EXTRACTION = "raw_extraction"
    QA_VALIDATION = "qa_validation"
    VERTICAL_EDITING = "vertical_editing"
    CAPTION_BURNING = "caption_burning"
    THUMBNAIL_GENERATION = "thumbnail_generation"
    METADATA_GENERATION = "metadata_generation"
    FINAL_QA = "final_qa"
    EXPORT = "export"


ORDERED_PIPELINE_STAGES = [
    PipelineStages.INGESTION.value,
    PipelineStages.AUDIO_EXTRACTION.value,
    PipelineStages.TRANSCRIPTION.value,
    PipelineStages.SCENE_DETECTION.value,
    PipelineStages.FRAME_SAMPLING.value,
    PipelineStages.VISUAL_ANALYSIS.value,
    PipelineStages.MOMENT_DETECTION.value,
    PipelineStages.RANKING.value,
    PipelineStages.CANDIDATE_REVIEW.value,
    PipelineStages.RAW_EXTRACTION.value,
    PipelineStages.QA_VALIDATION.value,
    PipelineStages.VERTICAL_EDITING.value,
    PipelineStages.CAPTION_BURNING.value,
    PipelineStages.THUMBNAIL_GENERATION.value,
    PipelineStages.METADATA_GENERATION.value,
    PipelineStages.FINAL_QA.value,
    PipelineStages.EXPORT.value,
]


class JobState(BaseModel):
    """Overall state machine job tracking progress across all stages."""
    job_id: str = Field(description="Unique job identifier")
    project_dir: str = Field(description="Absolute path to project directory")
    source_video: str = Field(description="Path to original source video")
    status: str = Field(default="pending", description="Overall job status: pending, running, completed, failed, paused")
    current_stage: Optional[str] = Field(default=None, description="Currently executing or last attempted stage")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    stages: Dict[str, StageExecutionRecord] = Field(
        default_factory=lambda: {
            stage: StageExecutionRecord(stage_name=stage, status=StageStatus.PENDING)
            for stage in ORDERED_PIPELINE_STAGES
        },
        description="Per-stage execution records"
    )
    artifacts: Dict[str, str] = Field(default_factory=dict, description="Key artifact paths registered across stages")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Aggregated pipeline telemetry and counters")

    def update_stage_status(
        self,
        stage_name: str,
        status: StageStatus,
        duration: float = 0.0,
        error: Optional[str] = None,
        artifacts: Optional[List[str]] = None,
    ) -> None:
        """Updates record for a single stage and refreshes job timestamp."""
        rec = self.stages.get(stage_name)
        if not rec:
            rec = StageExecutionRecord(stage_name=stage_name)
            self.stages[stage_name] = rec

        rec.status = status
        now_iso = datetime.now(timezone.utc).isoformat()
        if status == StageStatus.RUNNING:
            rec.started_at = now_iso
            self.current_stage = stage_name
        elif status in (StageStatus.COMPLETED, StageStatus.FAILED, StageStatus.SKIPPED):
            rec.completed_at = now_iso
            rec.duration_seconds = round(duration, 3)
            rec.error = error
            if artifacts:
                rec.artifacts_produced.extend(artifacts)

        self.updated_at = now_iso

    def mark_stage_running(self, stage_name: str) -> None:
        """Transitions stage to RUNNING and job status to 'running'."""
        self.status = "running"
        self.update_stage_status(stage_name, StageStatus.RUNNING)

    def mark_stage_completed(
        self,
        stage_name: str,
        duration: float = 0.0,
        artifacts: Optional[Dict[str, str]] = None,
    ) -> None:
        """Transitions stage to COMPLETED and registers any produced artifacts."""
        if artifacts:
            self.artifacts.update(artifacts)
        self.update_stage_status(
            stage_name,
            StageStatus.COMPLETED,
            duration=duration,
            artifacts=list(artifacts.values()) if artifacts else None,
        )

    def mark_stage_failed(self, stage_name: str, error: str, duration: float = 0.0) -> None:
        """Transitions stage and job status to 'failed' with error detail."""
        self.status = "failed"
        self.update_stage_status(stage_name, StageStatus.FAILED, duration=duration, error=error)

    def is_stage_completed(self, stage_name: str) -> bool:
        """Returns True if the given stage is recorded as completed."""
        rec = self.stages.get(stage_name)
        return rec is not None and rec.status == StageStatus.COMPLETED

    def get_last_completed_stage(self) -> Optional[str]:
        """Returns the name of the furthest completed stage in order."""
        last = None
        for stage in ORDERED_PIPELINE_STAGES:
            if self.is_stage_completed(stage):
                last = stage
            else:
                break
        return last
