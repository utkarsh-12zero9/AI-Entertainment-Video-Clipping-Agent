"""Tests for SceneDetector."""

from pathlib import Path
import pytest

from backend.analyzers.scene_detector import SceneDetector, SceneDetectorError


def test_detect_scenes_valid_video(valid_video_path: Path):
    detector = SceneDetector()
    scenes = detector.detect_scenes(valid_video_path, video_duration=5.0)

    assert len(scenes) >= 1
    assert scenes[0].start == 0.0
    assert scenes[-1].end >= 4.8
    assert scenes[0].duration > 0


def test_detect_scenes_missing_video():
    detector = SceneDetector()
    with pytest.raises(SceneDetectorError):
        detector.detect_scenes(Path("non_existent_video.mp4"), video_duration=10.0)
