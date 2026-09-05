"""Unit and integration tests for Stage 8: Caption Engine."""

from pathlib import Path
import subprocess
import pytest

from backend.config.settings import PipelineSettings
from backend.captions.burner import CaptionBurner
from backend.captions.generator import CaptionGenerator
from backend.models.caption import CaptionChunk, ClipCaptionResult, ProjectCaptionReport
from backend.models.clip import ClipSpecification, SelectedClipsReport
from backend.models.transcript import TranscriptResult, TranscriptSegment, WordTimestamp
from backend.pipeline.workspace import WorkspaceManager


@pytest.fixture
def sample_transcript() -> TranscriptResult:
    """Creates a mock transcript with word timestamps."""
    return TranscriptResult(
        language="en",
        duration=10.0,
        text="This is an insane hilarious joke that you will never forget.",
        segments=[
            TranscriptSegment(
                id=1,
                start=0.5,
                end=4.5,
                text="This is an insane hilarious joke that you will never forget.",
                words=[
                    WordTimestamp(word="This", start=0.5, end=0.8),
                    WordTimestamp(word="is", start=0.8, end=1.0),
                    WordTimestamp(word="an", start=1.0, end=1.2),
                    WordTimestamp(word="insane", start=1.2, end=1.8),
                    WordTimestamp(word="hilarious", start=1.8, end=2.4),
                    WordTimestamp(word="joke", start=2.4, end=2.8),
                    WordTimestamp(word="that", start=2.8, end=3.1),
                    WordTimestamp(word="you", start=3.1, end=3.4),
                    WordTimestamp(word="will", start=3.4, end=3.7),
                    WordTimestamp(word="never", start=3.7, end=4.1),
                    WordTimestamp(word="forget.", start=4.1, end=4.5),
                ],
            )
        ],
    )


@pytest.fixture
def sample_clip_spec() -> ClipSpecification:
    """Creates a sample ClipSpecification."""
    return ClipSpecification(
        clip_id="funny_001",
        candidate_id="cand_001",
        start_time=1.0,
        end_time=4.5,
        duration=3.5,
        category="funny",
        categories=["funny"],
        score=0.95,
        reason="Peak comedic delivery",
        hook="This is an insane hilarious joke",
        payoff="You will never forget",
        transcript="This is an insane hilarious joke that you will never forget.",
    )


@pytest.fixture
def synthetic_vertical_clip(tmp_path: Path) -> Path:
    """Generates a synthetic 3.5s 9:16 vertical video (1080x1920) with audio tone."""
    video_path = tmp_path / "vertical_clip.mp4"
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", "testsrc=duration=3.5:size=1080x1920:rate=30",
        "-f", "lavfi",
        "-i", "sine=frequency=440:duration=3.5",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(video_path),
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return video_path


def test_caption_generator_chunks_and_formats(sample_clip_spec: ClipSpecification, sample_transcript: TranscriptResult, tmp_path: Path):
    """Test generating, chunking, and formatting .srt and .ass subtitles."""
    generator = CaptionGenerator()
    srt_file = tmp_path / "funny_001.srt"
    ass_file = tmp_path / "funny_001.ass"

    chunks = generator.generate_captions_for_clip(
        clip_spec=sample_clip_spec,
        transcript=sample_transcript,
        srt_output_path=srt_file,
        ass_output_path=ass_file,
        style="bold_highlight",
    )

    assert len(chunks) > 0
    assert srt_file.exists()
    assert ass_file.exists()

    srt_text = srt_file.read_text(encoding="utf-8")
    assert "-->" in srt_text
    assert "1" in srt_text

    ass_text = ass_file.read_text(encoding="utf-8")
    assert "[Script Info]" in ass_text
    assert "PlayResX: 1080" in ass_text
    assert "PlayResY: 1920" in ass_text
    assert "Dialogue:" in ass_text

    # Re-based timestamps check: chunk 1 start time should be >= 0.0 and <= 3.5
    for c in chunks:
        assert 0.0 <= c.start <= 3.5
        assert 0.0 <= c.end <= 4.0
        assert len(c.words) <= 5


def test_caption_burner_render(tmp_path: Path, synthetic_vertical_clip: Path, sample_clip_spec: ClipSpecification, sample_transcript: TranscriptResult):
    """Test burning generated subtitles onto vertical video with FFmpeg."""
    out_dir = tmp_path / "proj"
    workspace = WorkspaceManager.create_workspace(out_dir)

    # Place clip into workspace.edited_clips / funny / funny_001.mp4
    clip_dir = workspace.edited_clips / "funny"
    clip_dir.mkdir(parents=True, exist_ok=True)
    clip_path = clip_dir / "funny_001.mp4"
    import shutil
    shutil.copy2(synthetic_vertical_clip, clip_path)

    report = SelectedClipsReport(total_selected=1, clips=[sample_clip_spec])
    burner = CaptionBurner(settings=PipelineSettings(clip_preset="ultrafast"))

    caption_report = burner.process_all_clips(report, sample_transcript, workspace, style="bold_highlight")

    assert isinstance(caption_report, ProjectCaptionReport)
    assert caption_report.total_clips == 1

    captioned_video = workspace.captioned_clips / "funny" / "funny_001.mp4"
    assert captioned_video.exists()
    assert captioned_video.stat().st_size > 0

    # Save caption report
    saved_report = WorkspaceManager.save_caption_report(caption_report, workspace)
    assert saved_report.exists()
    assert "caption_report.json" in saved_report.name
