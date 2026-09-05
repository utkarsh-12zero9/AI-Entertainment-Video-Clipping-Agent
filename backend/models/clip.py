"""Data models for selected and boundary-optimized clips."""

from typing import List, Optional
from pydantic import BaseModel, Field


class ClipSpecification(BaseModel):
    """Refined specification for a final render-ready clip."""
    clip_id: str = Field(description="Unique clip identifier e.g. funny_001, surprising_001")
    candidate_id: str = Field(description="Original source candidate identifier e.g. candidate_001")
    start_time: float = Field(description="Optimized start timestamp in seconds")
    end_time: float = Field(description="Optimized end timestamp in seconds")
    duration: float = Field(description="Duration in seconds (typically 20-30s)")
    category: str = Field(description="Primary category name e.g. funny, surprising, emotional")
    categories: List[str] = Field(default_factory=list, description="All associated category tags")
    score: float = Field(description="Final ranked composite quality score (0.0 to 1.0)")
    reason: str = Field(description="Reasoning explaining why this clip was chosen and ranked")
    hook: str = Field(description="Opening hook line")
    payoff: str = Field(description="Closing payoff line")
    transcript: str = Field(description="Full coherent transcript of the optimized clip")


class SelectedClipsReport(BaseModel):
    """Collection of ranked and boundary-optimized clips."""
    total_selected: int = Field(description="Number of selected clips")
    clips: List[ClipSpecification] = Field(default_factory=list, description="List of clip specifications")
