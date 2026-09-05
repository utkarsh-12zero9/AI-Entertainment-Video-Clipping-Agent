"""Unit and integration tests for RawClipExtractor and ClipValidator (Stage 6)."""

from pathlib import Path
import subprocess
import pytest

from backend.config.settings import PipelineSettings
from backend.models.clip import ClipSpecification, SelectedClipsReport
from backend.models.qa import ClipQAResult, ProjectQAReport
from backend.models.video import ProjectWorkspace
from backend.pipeline.workspace import WorkspaceManager
from backend.qa.clip_validator import ClipValidator
from backend.video.clip_extractor import RawClipExtractor


@pytest.fixture
def synthetic_video(tmp_path: Path) -> Path:
    """Generates a synthetic 10-second test video with audio tone using FFmpeg."""
    video_path = tmp_path / "source.mp4"
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", "testsrc=duration=10:size=640x360:rate=30",
        "-f", "lavfi",
        "-i", "sine=frequency=440:duration=10",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(video_path),
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return video_path


@pytest.fixture
def sample_report() -> SelectedClipsReport:
    """Creates a sample SelectedClipsReport with 2 clips."""
    return SelectedClipsReport(
        total_selected=2,
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
                reason="High laughter burst and punchline delivery",
                hook="This is hilarious",
                payoff="Punchline here",
                transcript="This is hilarious, wait till you hear this joke punchline here.",
            ),
            ClipSpecification(
                clip_id="storytelling_002",
                candidate_id="cand_102",
                start_time=5.0,
                end_time=8.5,
                duration=3.5,
                category="storytelling",
                categories=["storytelling"],
                score=0.88,
                reason="Compelling narrative arc with resolution",
                hook="Once upon a time",
                payoff="And they lived happily",
                transcript="Once upon a time there was a kingdom and they lived happily.",
            ),
        ],
    )


def test_raw_clip_extraction(tmp_path: Path, synthetic_video: Path, sample_report: SelectedClipsReport):
    """Test extracting clips into category-prefixed folders."""
    workspace = WorkspaceManager.create_workspace(tmp_path / "test_proj")
    extractor = RawClipExtractor(settings=PipelineSettings(clip_preset="ultrafast"))

    extracted_files = extractor.extract_all_clips(synthetic_video, sample_report, workspace)

    assert len(extracted_files) == 2
    for p in extracted_files:
        assert p.exists()
        assert p.stat().st_size > 0

    funny_clip = workspace.raw_clips / "funny" / "funny_001.mp4"
    story_clip = workspace.raw_clips / "storytelling" / "storytelling_002.mp4"
    assert funny_clip.exists()
    assert story_clip.exists()


def test_clip_qa_validator(tmp_path: Path, synthetic_video: Path, sample_report: SelectedClipsReport):
    """Test running QA validation on properly extracted clips."""
    workspace = WorkspaceManager.create_workspace(tmp_path / "test_proj_qa")
    extractor = RawClipExtractor(settings=PipelineSettings(clip_preset="ultrafast"))
    extractor.extract_all_clips(synthetic_video, sample_report, workspace)

    validator = ClipValidator(settings=PipelineSettings(qa_duration_tolerance_sec=0.8))
    qa_report = validator.validate_all_clips(sample_report, workspace)

    assert isinstance(qa_report, ProjectQAReport)
    assert qa_report.total_clips == 2
    assert qa_report.passed_clips == 2
    assert qa_report.all_passed is True

    # Test saving QA report
    qa_file = WorkspaceManager.save_qa_report(qa_report, workspace)
    assert qa_file.exists()
    assert "clip_qa_report.json" in qa_file.name


def test_clip_qa_detects_failure_on_missing_file(tmp_path: Path, sample_report: SelectedClipsReport):
    """Test that QA fails cleanly if clip file is missing."""
    workspace = WorkspaceManager.create_workspace(tmp_path / "test_proj_fail")
    validator = ClipValidator()

    # We do NOT extract any clips, so all files should be missing
    qa_report = validator.validate_all_clips(sample_report, workspace)

    assert qa_report.total_clips == 2
    assert qa_report.passed_clips == 0
    assert qa_report.failed_clips == 2
    assert qa_report.all_passed is False
    assert "does not exist" in qa_report.clip_results[0].issues[0]
