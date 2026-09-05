"""Data models for visual frames, scene boundaries, and frame visual analysis."""

from typing import List, Optional
from pydantic import BaseModel, Field


class SceneBoundary(BaseModel):
    """Timestamped scene or shot boundary in seconds."""
    scene_id: int = Field(description="Sequential index of the scene")
    start: float = Field(description="Start time in seconds")
    end: float = Field(description="End time in seconds")
    duration: float = Field(description="Duration in seconds")


class FrameInfo(BaseModel):
    """Metadata for an extracted representative frame."""
    frame_index: int = Field(description="Index number of the extracted frame")
    filename: str = Field(description="Filename e.g. frame_000001.jpg")
    timestamp: float = Field(description="Exact timestamp in seconds in the video")
    width: int = Field(description="Frame width in pixels")
    height: int = Field(description="Frame height in pixels")


class FrameIndex(BaseModel):
    """Index of sampled frames."""
    total_frames: int = Field(description="Total number of frames sampled")
    sampling_strategy: str = Field(description="Strategy used (fixed_interval, scene_change, adaptive)")
    frames: List[FrameInfo] = Field(default_factory=list, description="List of sampled frame metadata")


class FaceBoundingBox(BaseModel):
    """Bounding box coordinates for detected faces."""
    x: int
    y: int
    w: int
    h: int


class FrameVisualAnalysis(BaseModel):
    """Multimodal visual assessment metrics for a single frame."""
    frame: str = Field(description="Filename of the analyzed frame")
    timestamp: float = Field(description="Timestamp in seconds")
    num_faces: int = Field(default=0, description="Detected human faces count")
    faces: List[FaceBoundingBox] = Field(default_factory=list, description="Face bounding boxes")
    brightness: float = Field(description="Average frame brightness (0.0 to 255.0)")
    contrast: float = Field(description="Frame contrast metric (standard deviation)")
    sharpness: float = Field(description="Laplacian variance sharpness metric")
    is_blurry: bool = Field(description="Whether frame is deemed blurry")
    visual_activity: str = Field(description="low, moderate, high")
    scene_type: str = Field(description="close_up, medium_shot, wide_shot, unknown")
    confidence: float = Field(default=0.85, description="Confidence score for visual classification (0.0 to 1.0)")


class VisualAnalysisResult(BaseModel):
    """Aggregated visual analysis report for candidate moment ranking."""
    video_duration: float = Field(description="Total video duration in seconds")
    total_frames_analyzed: int = Field(description="Total number of frames analyzed")
    scenes: List[SceneBoundary] = Field(default_factory=list, description="Detected scene boundaries")
    frames: List[FrameVisualAnalysis] = Field(default_factory=list, description="Per-frame visual analyses")
