"""Audio signal and energy dynamics analyzer."""

import wave
from pathlib import Path
from typing import List, Tuple
import numpy as np

from backend.utils.errors import VideoPipelineError
from backend.utils.logger import logger


class AudioSignalAnalyzer:
    """Analyzes 16kHz mono WAV audio to extract RMS energy profile, silence pauses, and volume spikes."""

    def __init__(self, window_size_sec: float = 0.5):
        self.window_size_sec = window_size_sec

    def analyze_audio_energy(self, wav_path: Path) -> Tuple[np.ndarray, float]:
        """Calculates RMS energy array across time windows and returns (energy_profile, sample_rate)."""
        wav_path = Path(wav_path).resolve()
        if not wav_path.exists():
            raise VideoPipelineError(f"Audio file not found: {wav_path}")

        with wave.open(str(wav_path), "rb") as wf:
            n_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            raw_bytes = wf.readframes(n_frames)

        if sample_width == 2:
            dtype = np.int16
        else:
            dtype = np.int32

        samples = np.frombuffer(raw_bytes, dtype=dtype).astype(np.float32)
        if n_channels > 1:
            samples = samples.reshape(-1, n_channels).mean(axis=1)

        # Normalize samples between -1.0 and 1.0
        max_val = np.iinfo(dtype).max
        if max_val > 0:
            samples = samples / max_val

        window_size = int(framerate * self.window_size_sec)
        if window_size == 0 or len(samples) == 0:
            return np.zeros(1), float(framerate)

        num_windows = max(1, len(samples) // window_size)
        rms_profile = np.zeros(num_windows)

        for i in range(num_windows):
            chunk = samples[i * window_size : (i + 1) * window_size]
            rms_profile[i] = np.sqrt(np.mean(chunk**2)) if len(chunk) > 0 else 0.0

        return rms_profile, float(framerate)

    def get_energy_in_range(
        self,
        rms_profile: np.ndarray,
        start_sec: float,
        end_sec: float
    ) -> float:
        """Returns normalized mean RMS energy in a specific time window."""
        if len(rms_profile) == 0:
            return 0.0

        start_idx = int(start_sec / self.window_size_sec)
        end_idx = int(end_sec / self.window_size_sec)

        start_idx = max(0, min(start_idx, len(rms_profile) - 1))
        end_idx = max(start_idx + 1, min(end_idx, len(rms_profile)))

        sub_energy = rms_profile[start_idx:end_idx]
        if len(sub_energy) == 0:
            return 0.0

        mean_rms = float(np.mean(sub_energy))
        # Scale to 0.0 - 1.0 range (with typical speech ceiling of 0.20)
        return min(1.0, mean_rms / 0.15)
