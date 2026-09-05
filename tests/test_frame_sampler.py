"""Tests for FrameSampler strategies and index creation."""

import json
from pathlib import Path
import pytest

from backend.analyzers.frame_sampler import FrameSampler, FrameSamplerError
from backend.models.vision import SceneBoundary


def test_frame_sampler_compute_timestamps():
    sampler = FrameSampler()
    
    # Fixed interval
    ts_fixed = sampler.compute_sample_timestamps(duration=10.0, strategy="fixed_interval")
    assert len(ts_fixed) >= 5
    assert ts_fixed[0] == 0.0

    # Scene change
    scenes = [
        SceneBoundary(scene_id=1, start=0.0, end=4.0, duration=4.0),
        SceneBoundary(scene_id=2, start=4.0, end=10.0, duration=6.0)
    ]
    ts_scenes = sampler.compute_sample_timestamps(duration=10.0, strategy="scene_change", scenes=scenes)
    assert len(ts_scenes) == 2
    assert ts_scenes[0] == 2.0
    assert ts_scenes[1] == 7.0


def test_frame_sampler_extraction(valid_video_path: Path, tmp_path: Path):
    frames_dir = tmp_path / "frames"
    sampler = FrameSampler()
    frame_index = sampler.sample_frames(
        video_path=valid_video_path,
        frames_dir=frames_dir,
        duration=5.0,
        strategy="fixed_interval"
    )

    assert frame_index.total_frames >= 2
    assert (frames_dir / "index.json").exists()
    assert (frames_dir / "frame_000001.jpg").exists()

    with open(frames_dir / "index.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["total_frames"] == frame_index.total_frames
    assert data["frames"][0]["filename"] == "frame_000001.jpg"
