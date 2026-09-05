"""Unit tests for AudioExtractor."""

import subprocess
from pathlib import Path
import pytest

from backend.audio.extractor import AudioExtractionError, AudioExtractor
from backend.video.inspector import VideoInspector


def test_extract_audio_success(valid_video_path: Path, tmp_path: Path):
    output_wav = tmp_path / "audio.wav"
    extractor = AudioExtractor()
    result = extractor.extract(valid_video_path, output_wav)

    assert result.exists()
    assert result == output_wav
    assert result.stat().st_size > 0

    # Inspect the generated wav file using ffprobe
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_streams",
        "-select_streams", "a",
        "-print_format", "json",
        str(result)
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, text=True, check=True)
    import json
    data = json.loads(res.stdout)
    assert len(data["streams"]) == 1
    stream = data["streams"][0]
    assert stream["codec_name"] == "pcm_s16le"
    assert stream["sample_rate"] == "16000"
    assert stream["channels"] == 1


def test_extract_audio_missing_video(tmp_path: Path):
    extractor = AudioExtractor()
    with pytest.raises(AudioExtractionError):
        extractor.extract(Path("non_existent_video.mp4"), tmp_path / "audio.wav")


def test_extract_audio_from_no_audio_video(no_audio_video_path: Path, tmp_path: Path):
    extractor = AudioExtractor()
    with pytest.raises(AudioExtractionError):
        extractor.extract(no_audio_video_path, tmp_path / "audio.wav")
