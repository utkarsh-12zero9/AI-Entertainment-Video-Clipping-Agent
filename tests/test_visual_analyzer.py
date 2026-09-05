"""Tests for VisualAnalyzer metrics and local feature extraction."""

from pathlib import Path
import numpy as np
import cv2
import pytest

from backend.analyzers.visual_analyzer import VisualAnalyzer, VisualAnalyzerError
from backend.models.vision import FrameIndex, FrameInfo, SceneBoundary


def test_visual_analyzer_single_frame(tmp_path: Path):
    # Create a synthetic image
    img_path = tmp_path / "test_frame.jpg"
    img = np.zeros((720, 1280, 3), dtype=np.uint8)
    # Add a white rectangle to test contrast
    cv2.rectangle(img, (100, 100), (400, 400), (255, 255, 255), -1)
    cv2.imwrite(str(img_path), img)

    analyzer = VisualAnalyzer()
    analysis = analyzer.analyze_single_frame(img_path, timestamp=2.5)

    assert analysis.frame == "test_frame.jpg"
    assert analysis.timestamp == 2.5
    assert analysis.brightness > 0
    assert analysis.contrast > 0
    assert analysis.visual_activity in ["low", "moderate", "high"]
    assert analysis.scene_type in ["close_up", "medium_shot", "wide_shot", "unknown"]


def test_visual_analyzer_missing_image():
    analyzer = VisualAnalyzer()
    with pytest.raises(VisualAnalyzerError):
        analyzer.analyze_single_frame(Path("non_existent_frame.jpg"), 0.0)


def test_visual_analyzer_batch(tmp_path: Path):
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    frame_path = frames_dir / "frame_000001.jpg"
    img = np.full((360, 640, 3), 128, dtype=np.uint8)
    cv2.imwrite(str(frame_path), img)

    frame_index = FrameIndex(
        total_frames=1,
        sampling_strategy="fixed_interval",
        frames=[
            FrameInfo(
                frame_index=1,
                filename="frame_000001.jpg",
                timestamp=1.0,
                width=640,
                height=360
            )
        ]
    )
    scenes = [SceneBoundary(scene_id=1, start=0.0, end=5.0, duration=5.0)]

    analyzer = VisualAnalyzer()
    result = analyzer.analyze_sampled_frames(
        frames_dir=frames_dir,
        frame_index=frame_index,
        scenes=scenes,
        video_duration=5.0
    )

    assert result.total_frames_analyzed == 1
    assert len(result.frames) == 1
    assert result.frames[0].frame == "frame_000001.jpg"
