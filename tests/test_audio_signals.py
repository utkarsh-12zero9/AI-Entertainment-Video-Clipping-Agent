"""Tests for AudioSignalAnalyzer energy profile extraction."""

import subprocess
from pathlib import Path
import numpy as np

from backend.audio.analyzer import AudioSignalAnalyzer


def test_audio_signal_analyzer_energy(tmp_path: Path):
    wav_path = tmp_path / "test_tone.wav"
    # Generate 4-second sine wave audio
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=4",
        "-ar", "16000", "-ac", "1",
        str(wav_path)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    analyzer = AudioSignalAnalyzer(window_size_sec=0.5)
    rms_profile, sr = analyzer.analyze_audio_energy(wav_path)

    assert sr == 16000
    assert len(rms_profile) == 8  # 4 seconds / 0.5s windows = 8
    assert np.all(rms_profile > 0.0)

    # Test energy in range
    energy = analyzer.get_energy_in_range(rms_profile, 1.0, 3.0)
    assert energy > 0.0
