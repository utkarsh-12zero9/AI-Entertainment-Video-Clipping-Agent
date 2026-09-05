"""Transcription package."""
from backend.transcription.base import BaseTranscriber
from backend.transcription.whisper_local import LocalWhisperTranscriber, TranscriptionError

__all__ = ["BaseTranscriber", "LocalWhisperTranscriber", "TranscriptionError"]
