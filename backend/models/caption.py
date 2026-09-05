"""Data models for subtitle generation and burned-in captions."""

from typing import List, Optional
from pydantic import BaseModel, Field


class CaptionWord(BaseModel):
    """Word-level timing information relative to the clip start."""
    word: str = Field(description="The spoken word")
    start: float = Field(description="Word start timestamp relative to clip start (seconds)")
    end: float = Field(description="Word end timestamp relative to clip start (seconds)")
    is_highlighted: bool = Field(default=False, description="Whether word is emphasized/highlighted")


class CaptionChunk(BaseModel):
    """Short bite-sized caption unit (2-5 words) for mobile display."""
    start: float = Field(description="Chunk start timestamp relative to clip start (seconds)")
    end: float = Field(description="Chunk end timestamp relative to clip start (seconds)")
    text: str = Field(description="Full text for this chunk")
    words: List[CaptionWord] = Field(default_factory=list, description="Word timings within chunk")


class ClipCaptionResult(BaseModel):
    """Result of caption generation and rendering for an individual clip."""
    clip_id: str = Field(description="Unique clip identifier")
    category: str = Field(description="Clip category name")
    srt_path: str = Field(description="File path to generated .srt subtitle file")
    ass_path: str = Field(description="File path to styled .ass subtitle file")
    captioned_clip_path: str = Field(description="File path to rendered video with burned-in captions")
    total_chunks: int = Field(description="Number of caption chunks generated")
    style_used: str = Field(default="bold_highlight", description="Caption visual style used")
    duration: float = Field(description="Duration in seconds")


class ProjectCaptionReport(BaseModel):
    """Aggregated report of captioning across all project clips."""
    project_id: str = Field(description="Project identifier")
    created_at: str = Field(description="Generation timestamp")
    total_clips: int = Field(description="Total clips processed for captions")
    caption_style: str = Field(description="Caption style configured")
    clips: List[ClipCaptionResult] = Field(default_factory=list, description="Per-clip caption results")
