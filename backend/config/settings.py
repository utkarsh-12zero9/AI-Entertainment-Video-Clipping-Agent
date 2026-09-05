"""Application configuration and default settings."""

from pathlib import Path
from pydantic import BaseModel, Field


class PipelineSettings(BaseModel):
    """Pipeline configuration settings with configurable overrides."""
    
    # Video Ingestion & Validation
    min_video_duration: float = Field(default=5.0, description="Minimum acceptable video duration in seconds")
    require_audio: bool = Field(default=True, description="Enforce usable audio track presence")
    
    # Target Clip Specification
    min_clip_duration: float = Field(default=20.0, description="Minimum clip duration in seconds")
    max_clip_duration: float = Field(default=30.0, description="Maximum clip duration in seconds")
    target_width: int = Field(default=1080, description="Target vertical video width")
    target_height: int = Field(default=1920, description="Target vertical video height")
    target_aspect_ratio: str = Field(default="9:16", description="Target output aspect ratio")
    
    # Audio Extraction & Transcription (Free open-source Whisper)
    audio_sample_rate: int = Field(default=16000, description="Target sample rate in Hz for audio extraction")
    whisper_model_name: str = Field(default="base", description="Free local Whisper model: tiny, base, small, medium")
    whisper_device: str = Field(default="auto", description="Device for Whisper inference: auto, cpu, cuda")
    transcribe_word_timestamps: bool = Field(default=True, description="Enable word-level timestamps")
    
    # Tool binaries
    ffmpeg_bin: str = Field(default="ffmpeg", description="Path or command for ffmpeg")
    ffprobe_bin: str = Field(default="ffprobe", description="Path or command for ffprobe")


# Default global settings instance
default_settings = PipelineSettings()
