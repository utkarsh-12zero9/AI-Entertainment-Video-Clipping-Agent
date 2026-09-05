"""Data models for vertical social media editing."""

from typing import List, Optional
from pydantic import BaseModel, Field


class CropWindow(BaseModel):
    """Calculated 9:16 crop window relative to scaled video dimensions."""
    x: int = Field(description="Horizontal offset X coordinate in pixels")
    y: int = Field(default=0, description="Vertical offset Y coordinate in pixels")
    width: int = Field(default=1080, description="Crop width in pixels (1080 for 9:16)")
    height: int = Field(default=1920, description="Crop height in pixels (1920 for 9:16)")
    strategy_used: str = Field(default="center", description="Strategy used: 'smart_face' or 'center'")
    detected_faces: int = Field(default=0, description="Number of faces detected during analysis")


class EditedClipResult(BaseModel):
    """Execution result for a single vertical edited clip."""
    clip_id: str = Field(description="Clip identifier e.g. funny_001")
    category: str = Field(description="Clip category name e.g. funny")
    raw_clip_path: str = Field(description="Source raw clip file path")
    edited_clip_path: str = Field(description="Destination edited clip file path")
    resolution: str = Field(default="1080x1920", description="Output video resolution")
    aspect_ratio: str = Field(default="9:16", description="Output aspect ratio")
    duration: float = Field(description="Clip duration in seconds")
    file_size_bytes: int = Field(default=0, description="Output file size in bytes")
    crop: CropWindow = Field(description="Applied cropping parameters")
    audio_normalized: bool = Field(default=True, description="Whether audio was normalized to target LUFS")
    visual_enhancement_applied: bool = Field(default=True, description="Whether sharpening/contrast was applied")


class ProjectEditReport(BaseModel):
    """Aggregated report of all vertical edited clips for a project."""
    project_id: str = Field(description="Project identifier")
    created_at: str = Field(description="Generation timestamp")
    total_clips: int = Field(description="Total number of clips edited")
    target_resolution: str = Field(default="1080x1920", description="Standard output resolution")
    target_aspect_ratio: str = Field(default="9:16", description="Standard output aspect ratio")
    clips: List[EditedClipResult] = Field(default_factory=list, description="List of individual edited clip results")
