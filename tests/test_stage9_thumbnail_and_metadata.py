"""Comprehensive tests for Stage 9: Thumbnail Generation and Social Metadata Agent."""

import json
from pathlib import Path
import cv2
import numpy as np
import pytest

from backend.config.settings import PipelineSettings
from backend.metadata.social_metadata_generator import SocialMetadataGenerator
from backend.metadata.thumbnail_generator import ThumbnailGenerator
from backend.models.clip import ClipSpecification, SelectedClipsReport
from backend.models.metadata import ClipSocialMetadata, PlatformMetadata, ProjectMetadataReport
from backend.pipeline.workspace import WorkspaceManager


@pytest.fixture
def sample_video_and_workspace(tmp_path: Path):
    """Creates a mock workspace and a test video clip."""
    workspace = WorkspaceManager.create_workspace(tmp_path)

    # Create a dummy 9:16 vertical video (1080x1920, 30fps, 2 seconds = 60 frames)
    # Put some distinct patterns in frames so frame sampling & scoring functions cleanly
    test_clip_path = workspace.edited_clips_dir / "clip_001.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(test_clip_path), fourcc, 30.0, (1080, 1920))

    for i in range(60):
        frame = np.zeros((1920, 1080, 3), dtype=np.uint8)
        # Add varying gradients and shapes to produce different sharpness/contrast
        color_val = int((i / 60.0) * 255)
        cv2.circle(frame, (540, 960), 100 + i * 2, (color_val, 255 - color_val, 200), -1)
        cv2.putText(frame, f"Frame {i}", (200, 500), cv2.FONT_HERSHEY_SIMPLEX, 3.0, (255, 255, 255), 4)
        out.write(frame)
    out.release()

    # Create a selected report with clip_001
    clip_spec = ClipSpecification(
        clip_id="clip_001",
        candidate_id="cand_001",
        start_time=10.0,
        end_time=30.0,
        duration=20.0,
        category="Humor",
        categories=["Humor", "Gaming"],
        score=0.92,
        reason="High comedic timing and viral potential",
        hook="This is the funniest moment ever recorded in gaming history!",
        payoff="Follow for part 2!",
        transcript="You won't believe what happened next right in the middle of the game.",
    )
    selected_report = SelectedClipsReport(
        total_selected=1,
        clips=[clip_spec],
    )

    return workspace, selected_report, test_clip_path


def test_thumbnail_generator_scoring_and_selection(sample_video_and_workspace):
    """Verifies ThumbnailGenerator samples candidate frames, scores sharpness, and selects best frame."""
    workspace, selected_report, test_clip_path = sample_video_and_workspace
    settings = PipelineSettings(thumbnail_overlay_text=False)
    thumb_gen = ThumbnailGenerator(settings=settings)

    clip_spec = selected_report.clips[0]
    thumb_out = workspace.thumbnails_dir / f"{clip_spec.clip_id}.jpg"
    thumb_path = thumb_gen.generate_thumbnail(
        video_path=test_clip_path,
        output_image_path=thumb_out,
        clip_spec=clip_spec,
        overlay_text=False
    )

    assert thumb_path.exists()
    assert thumb_path.name == "clip_001.jpg"
    assert thumb_path.parent == workspace.thumbnails_dir

    # Inspect the generated thumbnail with OpenCV
    img = cv2.imread(str(thumb_path))
    assert img is not None
    assert img.shape == (1920, 1080, 3)  # Height, Width, Channels


def test_thumbnail_generator_with_hook_overlay(sample_video_and_workspace):
    """Verifies that Pillow text overlay adds a hook headline banner to the thumbnail."""
    workspace, selected_report, test_clip_path = sample_video_and_workspace
    settings = PipelineSettings(
        thumbnail_overlay_text=True,
        thumbnail_font_size=48
    )
    thumb_gen = ThumbnailGenerator(settings=settings)

    clip_spec = selected_report.clips[0]
    thumb_out = workspace.thumbnails_dir / f"{clip_spec.clip_id}.jpg"
    thumb_path = thumb_gen.generate_thumbnail(
        video_path=test_clip_path,
        output_image_path=thumb_out,
        clip_spec=clip_spec,
        overlay_text=True
    )

    assert thumb_path.exists()
    img = cv2.imread(str(thumb_path))
    assert img is not None
    assert img.shape == (1920, 1080, 3)

    # Generate all thumbnails batch test
    thumb_map = thumb_gen.generate_all_thumbnails(selected_report, workspace)
    assert "clip_001" in thumb_map
    assert Path(thumb_map["clip_001"]).exists()


def test_social_metadata_generator_platform_customization(sample_video_and_workspace):
    """Verifies platform-tailored metadata generation for YouTube Shorts, IG Reels, TikTok, and FB Reels."""
    workspace, selected_report, test_clip_path = sample_video_and_workspace
    settings = PipelineSettings()
    meta_gen = SocialMetadataGenerator(settings=settings)

    clip = selected_report.clips[0]
    meta = meta_gen.generate_clip_metadata(
        clip_spec=clip,
        thumbnail_path=workspace.thumbnails_dir / "clip_001.jpg"
    )

    assert isinstance(meta, ClipSocialMetadata)
    assert meta.clip_id == "clip_001"
    assert meta.category == "Humor"
    assert len(meta.primary_title) > 0
    assert len(meta.platforms) == 4

    # YouTube Shorts requirements
    yt = meta.platforms["youtube_shorts"]
    assert len(yt.title) <= 100
    assert "#Shorts" in yt.title or "#shorts" in yt.title or "#Shorts" in yt.description
    assert "#Shorts" in yt.hashtags or "#shorts" in yt.hashtags

    # Instagram Reels requirements
    ig = meta.platforms["instagram_reels"]
    assert len(ig.hashtags) >= 5
    assert any("reels" in tag.lower() for tag in ig.hashtags)

    # TikTok requirements
    tt = meta.platforms["tiktok"]
    assert any("fyp" in tag.lower() for tag in tt.hashtags)

    # Facebook Reels requirements
    fb = meta.platforms["facebook_reels"]
    assert any("reels" in tag.lower() for tag in fb.hashtags)


def test_social_metadata_batch_and_workspace_persistence(sample_video_and_workspace):
    """Verifies batch generation and saving to workspace metadata/ folder and analysis/metadata_report.json."""
    workspace, selected_report, test_clip_path = sample_video_and_workspace
    settings = PipelineSettings()

    thumb_gen = ThumbnailGenerator(settings=settings)
    meta_gen = SocialMetadataGenerator(settings=settings)

    thumb_map = thumb_gen.generate_all_thumbnails(selected_report, workspace)
    metadata_map = meta_gen.generate_all_metadata(selected_report, workspace, thumb_map)

    assert "clip_001" in metadata_map

    # Save via WorkspaceManager
    meta_file = WorkspaceManager.save_social_metadata(metadata_map["clip_001"], workspace)
    assert meta_file.exists()
    assert meta_file.name == "clip_001.json"

    # Validate saved JSON content
    with open(meta_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["clip_id"] == "clip_001"
    assert "youtube_shorts" in loaded["platforms"]
    assert "tiktok" in loaded["platforms"]

    # Save Project Metadata Report
    from datetime import datetime, timezone
    report = ProjectMetadataReport(
        project_id=workspace.project_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        total_clips=len(metadata_map),
        clips=list(metadata_map.values()),
    )
    report_file = WorkspaceManager.save_metadata_report(report, workspace)
    assert report_file.exists()
    assert report_file.name == "metadata_report.json"

    with open(report_file, "r", encoding="utf-8") as f:
        report_data = json.load(f)
    assert report_data["total_clips"] == 1
    assert report_data["clips"][0]["clip_id"] == "clip_001"

