"""Audio extraction module using ffmpeg."""

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from backend.config.settings import PipelineSettings, default_settings
from backend.utils.errors import VideoPipelineError
from backend.utils.logger import logger


class AudioExtractionError(VideoPipelineError):
    """Raised when audio extraction fails."""
    pass


class AudioExtractor:
    """Extracts normalized 16kHz mono WAV audio from video files using ffmpeg."""

    def __init__(self, settings: Optional[PipelineSettings] = None):
        self.settings = settings or default_settings
        self._validate_ffmpeg_exists()

    def _validate_ffmpeg_exists(self) -> None:
        if not shutil.which(self.settings.ffmpeg_bin):
            raise AudioExtractionError(
                f"ffmpeg executable '{self.settings.ffmpeg_bin}' not found on system PATH."
            )

    def extract(self, video_path: Path, output_wav_path: Path) -> Path:
        """Extracts audio to 16kHz mono WAV (optimal for speech-to-text models)."""
        video_path = Path(video_path).resolve()
        output_wav_path = Path(output_wav_path).resolve()

        if not video_path.exists():
            raise AudioExtractionError(f"Input video does not exist: {video_path}")

        output_wav_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Extracting audio from {video_path.name} to {output_wav_path.name} (16kHz mono)")

        cmd = [
            self.settings.ffmpeg_bin,
            "-y",                     # Overwrite output
            "-i", str(video_path),    # Input file
            "-vn",                    # Disable video stream
            "-acodec", "pcm_s16le",   # Uncompressed 16-bit PCM
            "-ar", str(self.settings.audio_sample_rate), # 16000 Hz
            "-ac", "1",               # Mono channel
            str(output_wav_path)
        ]

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
        except Exception as e:
            raise AudioExtractionError(f"Failed to execute ffmpeg for audio extraction: {e}") from e

        if result.returncode != 0:
            raise AudioExtractionError(
                f"ffmpeg audio extraction failed for '{video_path.name}': {result.stderr.strip()}"
            )

        if not output_wav_path.exists() or output_wav_path.stat().st_size == 0:
            raise AudioExtractionError(
                f"Audio extraction output is empty or missing: {output_wav_path}"
            )

        logger.info(f"Audio extracted successfully ({output_wav_path.stat().st_size} bytes)")
        return output_wav_path
