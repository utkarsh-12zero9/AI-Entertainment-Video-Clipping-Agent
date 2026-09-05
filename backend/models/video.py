"""Video metadata and workspace models."""

from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field


class VideoMetadata(BaseModel):
    """Structured video metadata extracted via ffprobe."""
    
    filename: str = Field(description="Original filename or path of the video")
    duration: float = Field(description="Duration in seconds")
    width: int = Field(description="Video width in pixels")
    height: int = Field(description="Video height in pixels")
    fps: float = Field(description="Frames per second")
    codec: str = Field(description="Video codec name")
    bitrate: Optional[int] = Field(default=None, description="Bitrate in bits per second")
    has_audio: bool = Field(description="Whether a valid audio stream is present")
    audio_codec: Optional[str] = Field(default=None, description="Audio codec name")
    sample_rate: Optional[int] = Field(default=None, description="Audio sample rate in Hz")
    channels: Optional[int] = Field(default=None, description="Audio channel count")
    aspect_ratio: str = Field(description="Calculated or reported aspect ratio (e.g. 16:9)")
    file_size: int = Field(description="File size in bytes")


class ProjectWorkspace(BaseModel):
    """Encapsulates all directories and standard paths for a video processing project."""
    
    root: Path
    input_dir: Path
    audio_dir: Path
    transcript_dir: Path
    frames_dir: Path
    analysis_dir: Path
    candidates_dir: Path
    selected_dir: Path
    raw_clips_dir: Path
    edited_clips_dir: Path
    captions_dir: Path
    thumbnails_dir: Path
    metadata_dir: Path
    qa_dir: Path
    final_dir: Path
    
    @property
    def metadata_file(self) -> Path:
        return self.root / "video_metadata.json"

    @property
    def log_file(self) -> Path:
        return self.root / "pipeline.log"
