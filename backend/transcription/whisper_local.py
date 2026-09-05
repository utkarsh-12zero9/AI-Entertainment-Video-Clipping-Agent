"""Local speech-to-text transcriber using free, open-source OpenAI Whisper."""

from pathlib import Path
from typing import Optional

import whisper

from backend.config.settings import PipelineSettings, default_settings
from backend.models.transcript import TranscriptResult, TranscriptSegment, WordTimestamp
from backend.transcription.base import BaseTranscriber
from backend.utils.errors import VideoPipelineError
from backend.utils.logger import logger


class TranscriptionError(VideoPipelineError):
    """Raised when audio transcription fails."""
    pass


class LocalWhisperTranscriber(BaseTranscriber):
    """Transcribes audio locally using free open-source Whisper models (tiny, base, small, etc.)."""

    def __init__(self, settings: Optional[PipelineSettings] = None):
        self.settings = settings or default_settings
        self.model_name = self.settings.whisper_model_name
        self.device = self._resolve_device()
        self._model = None

    def _resolve_device(self) -> str:
        """Determines best device for inference."""
        if self.settings.whisper_device != "auto":
            return self.settings.whisper_device
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    @property
    def model(self):
        """Lazy loads the Whisper model on first use."""
        if self._model is None:
            logger.info(
                f"Loading local Whisper model '{self.model_name}' on device '{self.device}' (100% free / local)..."
            )
            try:
                self._model = whisper.load_model(self.model_name, device=self.device)
            except Exception as e:
                raise TranscriptionError(f"Failed to load Whisper model '{self.model_name}': {e}") from e
        return self._model

    def transcribe(self, audio_path: Path) -> TranscriptResult:
        """Performs transcription and extracts segment-level and word-level timestamps."""
        audio_path = Path(audio_path).resolve()
        if not audio_path.exists():
            raise TranscriptionError(f"Audio file not found: {audio_path}")

        logger.info(f"Transcribing audio with local Whisper: {audio_path.name}")

        try:
            # Run local whisper transcription with word timestamps enabled
            result = self.model.transcribe(
                str(audio_path),
                word_timestamps=self.settings.transcribe_word_timestamps,
                verbose=False
            )
        except Exception as e:
            raise TranscriptionError(f"Local Whisper transcription failed: {e}") from e

        segments_data = result.get("segments", [])
        full_text = result.get("text", "").strip()
        language = result.get("language", "en")

        segments = []
        for s in segments_data:
            words = []
            for w in s.get("words", []):
                words.append(
                    WordTimestamp(
                        word=w.get("word", "").strip(),
                        start=round(float(w.get("start", 0.0)), 2),
                        end=round(float(w.get("end", 0.0)), 2),
                        probability=round(float(w.get("probability", 0.0)), 3) if "probability" in w else None
                    )
                )

            seg = TranscriptSegment(
                id=int(s.get("id", len(segments))),
                start=round(float(s.get("start", 0.0)), 2),
                end=round(float(s.get("end", 0.0)), 2),
                text=s.get("text", "").strip(),
                speaker=s.get("speaker"),
                words=words
            )
            segments.append(seg)

        # Estimate duration
        duration = 0.0
        if segments:
            duration = max(seg.end for seg in segments)

        transcript_result = TranscriptResult(
            language=language,
            duration=round(duration, 2),
            text=full_text,
            segments=segments
        )

        logger.info(
            f"Transcription complete: {len(segments)} segments, language='{language}', duration={duration:.1f}s"
        )
        return transcript_result
