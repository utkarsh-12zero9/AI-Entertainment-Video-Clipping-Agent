"""Tests for WorkspaceManager folder structure and metadata persistence."""

import json
from pathlib import Path
from backend.models.video import VideoMetadata
from backend.pipeline.workspace import WorkspaceManager


def test_create_workspace(tmp_path: Path):
    target_dir = tmp_path / "project_001"
    workspace = WorkspaceManager.create_workspace(target_dir)

    expected_dirs = [
        workspace.input_dir,
        workspace.audio_dir,
        workspace.transcript_dir,
        workspace.frames_dir,
        workspace.analysis_dir,
        workspace.candidates_dir,
        workspace.selected_dir,
        workspace.raw_clips_dir,
        workspace.edited_clips_dir,
        workspace.captions_dir,
        workspace.thumbnails_dir,
        workspace.metadata_dir,
        workspace.qa_dir,
        workspace.final_dir,
    ]

    for d in expected_dirs:
        assert d.exists()
        assert d.is_dir()


def test_save_metadata(tmp_path: Path):
    workspace = WorkspaceManager.create_workspace(tmp_path / "project_002")
    meta = VideoMetadata(
        filename="test.mp4",
        duration=30.5,
        width=1920,
        height=1080,
        fps=30.0,
        codec="h264",
        bitrate=2500000,
        has_audio=True,
        audio_codec="aac",
        sample_rate=48000,
        channels=2,
        aspect_ratio="16:9",
        file_size=1024000
    )

    meta_file = WorkspaceManager.save_metadata(meta, workspace)
    assert meta_file.exists()
    
    with open(meta_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["filename"] == "test.mp4"
    assert data["duration"] == 30.5
    assert data["width"] == 1920
    assert data["height"] == 1080
    assert data["aspect_ratio"] == "16:9"
