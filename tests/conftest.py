"""Pytest configuration and test media generation helpers."""

import subprocess
from pathlib import Path
import pytest


def generate_synthetic_video(
    output_path: Path,
    duration: float = 5.0,
    width: int = 1280,
    height: int = 720,
    fps: int = 30,
    with_audio: bool = True
) -> Path:
    """Generates a synthetic MP4 test video using ffmpeg color and sine audio sources."""
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", f"color=c=blue:s={width}x{height}:r={fps}:d={duration}",
    ]

    if with_audio:
        cmd.extend([
            "-f", "lavfi",
            "-i", f"sine=frequency=1000:duration={duration}",
            "-c:a", "aac",
            "-b:a", "128k",
        ])

    cmd.extend([
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-t", str(duration),
        str(output_path)
    ])

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return output_path


@pytest.fixture(scope="session")
def test_media_dir(tmp_path_factory) -> Path:
    """Session-scoped temporary directory for synthetic media files."""
    media_dir = tmp_path_factory.mktemp("media")
    return media_dir


@pytest.fixture(scope="session")
def valid_video_path(test_media_dir) -> Path:
    """A valid 1280x720 30fps 5.0s video with stereo audio."""
    path = test_media_dir / "valid_test.mp4"
    return generate_synthetic_video(path, duration=5.0, width=1280, height=720, fps=30, with_audio=True)


@pytest.fixture(scope="session")
def no_audio_video_path(test_media_dir) -> Path:
    """A 5.0s video with NO audio stream."""
    path = test_media_dir / "no_audio_test.mp4"
    return generate_synthetic_video(path, duration=5.0, width=1280, height=720, fps=30, with_audio=False)


@pytest.fixture(scope="session")
def short_video_path(test_media_dir) -> Path:
    """A 1.0s video that is shorter than standard minimum duration."""
    path = test_media_dir / "short_test.mp4"
    return generate_synthetic_video(path, duration=1.0, width=640, height=360, fps=30, with_audio=True)


@pytest.fixture(scope="session")
def corrupted_video_path(test_media_dir) -> Path:
    """A non-video file pretending to be an mp4."""
    path = test_media_dir / "corrupted_test.mp4"
    path.write_bytes(b"THIS IS NOT A VALID MP4 VIDEO FILE HEADER RAW BYTES 123456789")
    return path
