"""Comprehensive unit and integration test suite for Stage 11: End-to-End Orchestrator & State Machine Agent."""

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import pytest

from backend.config.settings import PipelineSettings
from backend.models.candidate import CandidateMoment, CandidateReport
from backend.models.clip import ClipSpecification, SelectedClipsReport
from backend.models.job import (
    JobState,
    ORDERED_PIPELINE_STAGES,
    PipelineStages,
    StageExecutionRecord,
    StageStatus,
)
from backend.models.transcript import TranscriptResult, TranscriptSegment, WordTimestamp
from backend.models.video import VideoMetadata
from backend.pipeline.orchestrator import PipelineOrchestrator
from backend.pipeline.workspace import WorkspaceManager


def create_dummy_video(path: Path, duration: int = 4, width: int = 1280, height: int = 720) -> None:
    """Generates a small valid test video with synthetic audio using FFmpeg."""
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", f"testsrc=duration={duration}:size={width}x{height}:rate=30",
        "-f", "lavfi",
        "-i", f"sine=frequency=440:duration={duration}",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(path),
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def test_job_state_transitions_and_persistence(tmp_path: Path):
    """Verifies JobState state machine transitions, stage execution records, and JSON serialization."""
    workspace = WorkspaceManager.create_workspace(tmp_path)
    video_path = tmp_path / "test.mp4"
    video_path.touch()

    job = JobState(
        job_id=workspace.project_id,
        project_dir=str(workspace.root),
        source_video=str(video_path),
    )

    # Initial state
    assert job.status == "pending"
    assert len(job.stages) == len(ORDERED_PIPELINE_STAGES)
    for stage_name in ORDERED_PIPELINE_STAGES:
        assert job.stages[stage_name].status == StageStatus.PENDING

    # Transition to running and complete a stage
    job.mark_stage_running(PipelineStages.INGESTION.value)
    assert job.status == "running"
    assert job.current_stage == PipelineStages.INGESTION.value
    assert job.stages[PipelineStages.INGESTION.value].status == StageStatus.RUNNING

    job.mark_stage_completed(
        PipelineStages.INGESTION.value,
        duration=1.25,
        artifacts={"metadata": "metadata.json"}
    )
    assert job.stages[PipelineStages.INGESTION.value].status == StageStatus.COMPLETED
    assert job.stages[PipelineStages.INGESTION.value].duration_seconds == 1.25
    assert job.artifacts["metadata"] == "metadata.json"

    # Fail another stage
    job.mark_stage_running(PipelineStages.AUDIO_EXTRACTION.value)
    job.mark_stage_failed(PipelineStages.AUDIO_EXTRACTION.value, error="Audio decode error")
    assert job.status == "failed"
    assert job.stages[PipelineStages.AUDIO_EXTRACTION.value].status == StageStatus.FAILED
    assert job.stages[PipelineStages.AUDIO_EXTRACTION.value].error == "Audio decode error"

    # Persist and reload
    state_file = WorkspaceManager.save_job_state(job, workspace)
    assert state_file.exists()

    loaded_job = WorkspaceManager.load_job_state(workspace)
    assert loaded_job is not None
    assert loaded_job.job_id == job.job_id
    assert loaded_job.status == "failed"
    assert loaded_job.stages[PipelineStages.INGESTION.value].status == StageStatus.COMPLETED
    assert loaded_job.stages[PipelineStages.AUDIO_EXTRACTION.value].status == StageStatus.FAILED


def test_orchestrator_artifact_reuse(tmp_path: Path):
    """Tests that the orchestrator skips stages when valid artifacts already exist (caching)."""
    workspace = WorkspaceManager.create_workspace(tmp_path)
    video_path = tmp_path / "sample.mp4"
    create_dummy_video(video_path, duration=3)

    settings = PipelineSettings(
        min_video_duration=1.0,
        require_audio=True,
    )
    orchestrator = PipelineOrchestrator(settings=settings)

    # 1. Run Stage 1 via _execute_stage
    job = orchestrator.get_or_create_job_state(workspace, video_path)
    job = orchestrator._execute_stage(
        job, workspace, PipelineStages.INGESTION.value,
        lambda: orchestrator._step_ingestion(video_path, workspace)
    )
    assert job.stages[PipelineStages.INGESTION.value].status == StageStatus.COMPLETED
    duration_first_run = job.stages[PipelineStages.INGESTION.value].duration_seconds

    # 2. Check that re-executing the stage reuses the completed artifact and skips re-execution
    job_recheck = orchestrator._execute_stage(
        job, workspace, PipelineStages.INGESTION.value,
        lambda: orchestrator._step_ingestion(video_path, workspace)
    )
    assert job_recheck.stages[PipelineStages.INGESTION.value].status == StageStatus.COMPLETED
    assert job_recheck.stages[PipelineStages.INGESTION.value].duration_seconds == duration_first_run


def test_orchestrator_candidate_review_and_filtering(tmp_path: Path):
    """Tests human-in-the-loop review mechanism to approve or filter candidate moments."""
    workspace = WorkspaceManager.create_workspace(tmp_path)
    
    # Create mock selected_clips.json
    selected_report = SelectedClipsReport(
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
                hook="Did you know this crazy secret?",
                payoff="And that is how it works!",
                transcript="Did you know this crazy secret? Let me tell you how it works!",
                reason="High speech density and question hook",
                category="Insightful",
            ),
            ClipSpecification(
                clip_id="clip_002",
                candidate_id="cand_002",
                start_time=40.0,
                end_time=65.0,
                duration=25.0,
                score=0.85,
                hook="Wait for the twist at the end!",
                payoff="Nobody saw that coming at all!",
                transcript="Wait for the twist at the end! Nobody saw that coming at all!",
                reason="Laughter audio spike detected",
                category="Humor",
            ),
            ClipSpecification(
                clip_id="clip_003",
                candidate_id="cand_003",
                start_time=80.0,
                end_time=105.0,
                duration=25.0,
                score=0.75,
                hook="The shocking revelation!",
                payoff="It was right in front of us.",
                transcript="The shocking revelation! It was right in front of us.",
                reason="Dramatic speech cadence",
                category="Dramatic",
            ),
        ]
    )
    WorkspaceManager.save_selected_clips(selected_report, workspace)

    orchestrator = PipelineOrchestrator()

    # Filter down to only clip_001 and clip_003
    filtered = orchestrator.review_candidates(workspace.root, approved_ids=["clip_001", "clip_003"])
    assert filtered.total_selected == 2
    assert [c.clip_id for c in filtered.clips] == ["clip_001", "clip_003"]

    # Verify persisted selected_clips.json has been updated
    reloaded = WorkspaceManager.load_selected_clips(workspace)
    assert reloaded is not None
    assert reloaded.total_selected == 2
    assert [c.clip_id for c in reloaded.clips] == ["clip_001", "clip_003"]


def test_orchestrator_pipeline_step_execution(tmp_path: Path):
    """Verifies that orchestrator coordinates sequential steps and produces state checkpoint."""
    workspace = WorkspaceManager.create_workspace(tmp_path)
    video_path = tmp_path / "test_pipe.mp4"
    create_dummy_video(video_path, duration=4)

    settings = PipelineSettings(
        min_video_duration=1.0,
        require_audio=True,
    )
    orchestrator = PipelineOrchestrator(settings=settings)
    job = orchestrator.get_or_create_job_state(workspace, video_path)

    # Execute Stage 1 step
    artifacts_1 = orchestrator._step_ingestion(video_path, workspace)
    job.mark_stage_completed(PipelineStages.INGESTION.value, duration=0.5, artifacts={"metadata": artifacts_1[1]})
    WorkspaceManager.save_job_state(job, workspace)
    assert (workspace.root / artifacts_1[1]).exists()

    # Execute Stage 2 audio step
    artifacts_2 = orchestrator._step_audio_extraction(workspace, None)
    job.mark_stage_completed(PipelineStages.AUDIO_EXTRACTION.value, duration=0.5, artifacts={"audio": artifacts_2[0]})
    WorkspaceManager.save_job_state(job, workspace)
    audio_path = workspace.audio_dir / "audio.wav"
    assert audio_path.exists()

    # Verify job state on disk
    loaded_job = WorkspaceManager.load_job_state(workspace)
    assert loaded_job is not None
    assert loaded_job.stages[PipelineStages.INGESTION.value].status == StageStatus.COMPLETED
    assert loaded_job.stages[PipelineStages.AUDIO_EXTRACTION.value].status == StageStatus.COMPLETED
