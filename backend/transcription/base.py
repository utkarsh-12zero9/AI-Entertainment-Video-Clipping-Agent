"""Abstract base transcriber interface."""

from abc import ABC, abstractmethod
from pathlib import Path

from backend.models.transcript import TranscriptResult


class BaseTranscriber(ABC):
    """Abstract interface for speech transcription engines."""

    @abstractmethod
    def transcribe(self, audio_path: Path) -> TranscriptResult:
        """Transcribes an audio file into structured TranscriptResult."""
        pass
