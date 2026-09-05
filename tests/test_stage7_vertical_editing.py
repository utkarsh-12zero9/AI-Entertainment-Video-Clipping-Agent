"""Unit and integration tests for Stage 7: Vertical Social Media Editing."""

from pathlib import Path
import subprocess
import pytest

from backend.config.settings import PipelineSettings
from backend.models.clip import ClipSpecification, SelectedClipsReport
from backend.models.editing import CropWindow, EditedClipResult, ProjectEditReport
from backend.pipeline.workspace import WorkspaceManager
from backend.video.clip_editor import ClipEditor
from backend.video.inspector import VideoInspector
from backend.video.smart_cropper import SmartCropper


@pytest.fixture
def synthetic_raw_clip(tmp_path: Path) -> Path:
    """Generates a synthetic 3-second 16:9 test video (640x360) with audio tone."""
    clip_path = tmp_path / "funny_001.mp4"
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", "testsrc=duration=3:size=640x360:rate=30",
        "-f", "lavfi",
        "-i", "sine=frequency=440:duration=3",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(clip_path),
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return clip_path


@pytest.fixture
def single_clip_report() -> SelectedClipsReport:
    """Creates a SelectedClipsReport with a single test clip."""
    return SelectedClipsReport(
        total_selected=1,
        clips=[
            ClipSpecification(
                clip_id="funny_001",
                candidate_id="cand_101",
                start_time=1.0,
                end_time=4.0,
                duration=3.0,
                category="funny",
                categories=["funny"],
                score=0.92,
                reason="Laughter moment",
                hook="Look at this",
                payoff="Hilarious punchline",
                transcript="Look at this, hilarious punchline.",
            )
        ],
    )


def test_smart_cropper_center_calculation(tmp_path: Path, synthetic_raw_clip: Path):
    """Test smart cropper 9:16 crop calculation for 640x360 input."""
    cropper = SmartCropper()
    # 640x360 scaled to height 1920 -> width = round(640 * (1920 / 360)) = 3413 px.
    # Max horizontal offset = 3413 - 1080 = 2333 px.
    # Center X = 2333 // 2 = 1166 px.
    crop = cropper.calculate_crop(
        video_path=synthetic_raw_clip,
        original_width=640,
        original_height=360,
        strategy="center",
    )

    assert isinstance(crop, CropWindow)
    assert crop.width == 1080
    assert crop.height == 1920
    assert crop.strategy_used == "center"
    assert crop.x == 1166


def test_vertical_clip_editor_render(tmp_path: Path, synthetic_raw_clip: Path, single_clip_report: SelectedClipsReport):
    """Test editing a raw clip into a 1080x1920 vertical video."""
    out_dir = tmp_path / "test_project"
    workspace = WorkspaceManager.create_workspace(out_dir)

    # Place raw clip into workspace.raw_clips / funny / funny_001.mp4
    category_dir = workspace.raw_clips / "funny"
    category_dir.mkdir(parents=True, exist_ok=True)
    raw_dest = category_dir / "funny_001.mp4"
    import shutil
    shutil.copy2(synthetic_raw_clip, raw_dest)

    editor = ClipEditor(settings=PipelineSettings(clip_preset="ultrafast"))
    edit_report = editor.edit_all_clips(single_clip_report, workspace, strategy="center")

    assert isinstance(edit_report, ProjectEditReport)
    assert edit_report.total_clips == 1

    edited_file = workspace.edited_clips / "funny" / "funny_001.mp4"
    assert edited_file.exists()
    assert edited_file.stat().st_size > 0

    # Inspect rendered vertical video
    inspector = VideoInspector(settings=PipelineSettings(min_video_duration=0.5))
    metadata = inspector.inspect(edited_file)

    assert metadata.width == 1080
    assert metadata.height == 1920
    assert metadata.aspect_ratio == "9:16"
    assert metadata.has_audio is True

    # Test saving edit report
    saved_report = WorkspaceManager.save_edit_report(edit_report, workspace)
    assert saved_report.exists()
    assert "edit_report.json" in saved_report.name
