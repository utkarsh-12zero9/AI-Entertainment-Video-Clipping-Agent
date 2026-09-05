"""Data models for audio transcription and timestamps."""

from typing import List, Optional
from pydantic import BaseModel, Field


class WordTimestamp(BaseModel):
    """Word-level timestamp details."""
    word: str = Field(description="The spoken word")
    start: float = Field(description="Start time in seconds")
    end: float = Field(description="End time in seconds")
    probability: Optional[float] = Field(default=None, description="Model confidence score")


class TranscriptSegment(BaseModel):
    """Timestamped segment/sentence of speech."""
    id: int = Field(description="Unique segment index")
    start: float = Field(description="Start time in seconds")
    end: float = Field(description="End time in seconds")
    text: str = Field(description="Transcribed text content")
    speaker: Optional[str] = Field(default=None, description="Speaker identification if available")
    words: List[WordTimestamp] = Field(default_factory=list, description="Word-level timestamps")


class TranscriptResult(BaseModel):
    """Full transcription result with metadata and segment list."""
    language: str = Field(default="en", description="Detected or specified spoken language")
    duration: float = Field(description="Total audio duration in seconds")
    text: str = Field(description="Full concatenated transcript text")
    segments: List[TranscriptSegment] = Field(default_factory=list, description="List of timed segments")
