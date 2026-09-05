"""Tests for VideoInspector metadata extraction and validation logic."""

from pathlib import Path
import pytest

from backend.config.settings import PipelineSettings
from backend.utils.errors import (
    CorruptedVideoError,
    MissingVideoError,
    NoAudioError,
    VideoTooShortError,
)
from backend.video.inspector import VideoInspector, calculate_aspect_ratio, parse_fps


def test_calculate_aspect_ratio():
    assert calculate_aspect_ratio(1920, 1080) == "16:9"
    assert calculate_aspect_ratio(1080, 1920) == "9:16"
    assert calculate_aspect_ratio(1280, 720) == "16:9"
    assert calculate_aspect_ratio(1080, 1080) == "1:1"
    assert calculate_aspect_ratio(640, 480) == "4:3"


def test_parse_fps():
    assert parse_fps("30/1") == 30.0
    assert parse_fps("60/1") == 60.0
    assert parse_fps("30000/1001") == 29.97
    assert parse_fps("invalid") == 0.0


def test_inspect_valid_video(valid_video_path: Path):
    inspector = VideoInspector()
    meta = inspector.inspect(valid_video_path)

    assert meta.filename == valid_video_path.name
    assert meta.width == 1280
    assert meta.height == 720
    assert meta.aspect_ratio == "16:9"
    assert 29.0 <= meta.fps <= 31.0
    assert 4.8 <= meta.duration <= 5.2
    assert meta.has_audio is True
    assert meta.audio_codec in ("aac", "mp4a-40-2")
    assert meta.file_size > 0


def test_inspect_missing_video():
    inspector = VideoInspector()
    missing_path = Path("does_not_exist_xyz.mp4")
    with pytest.raises(MissingVideoError):
        inspector.inspect(missing_path)


def test_inspect_corrupted_video(corrupted_video_path: Path):
    inspector = VideoInspector()
    with pytest.raises(CorruptedVideoError):
        inspector.inspect(corrupted_video_path)


def test_inspect_no_audio_video_rejected_by_default(no_audio_video_path: Path):
    inspector = VideoInspector()
    with pytest.raises(NoAudioError):
        inspector.inspect(no_audio_video_path)


def test_inspect_no_audio_allowed_via_settings(no_audio_video_path: Path):
    settings = PipelineSettings(require_audio=False)
    inspector = VideoInspector(settings=settings)
    meta = inspector.inspect(no_audio_video_path)
    assert meta.has_audio is False
    assert meta.audio_codec is None


def test_inspect_too_short_video(short_video_path: Path):
    # Minimum required is 5.0s, short_test is 1.0s
    inspector = VideoInspector(settings=PipelineSettings(min_video_duration=5.0))
    with pytest.raises(VideoTooShortError):
        inspector.inspect(short_video_path)
