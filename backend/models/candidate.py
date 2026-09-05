"""Data models for candidate entertainment moments and multimodal scores."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class CandidateScores(BaseModel):
    """Normalized multimodal scores from 0.0 to 1.0."""
    hook_strength: float = Field(default=0.0, description="Strength of the initial 3-5 second hook")
    humor: float = Field(default=0.0, description="Humor and comedic timing score")
    surprise: float = Field(default=0.0, description="Unexpected twists, shocks, or punchlines")
    emotion: float = Field(default=0.0, description="Emotional intensity / sentiment shifts")
    visual_interest: float = Field(default=0.0, description="Face presence, motion, and scene transitions")
    context_completeness: float = Field(default=0.0, description="Standalone understandability without prior video")
    social_potential: float = Field(default=0.0, description="Overall virality / engagement rating")


class CandidateMoment(BaseModel):
    """A scored entertainment candidate moment for short-form video."""
    id: str = Field(description="Unique candidate identifier, e.g. candidate_001")
    start_time: float = Field(description="Start timestamp in seconds")
    end_time: float = Field(description="End timestamp in seconds")
    duration: float = Field(description="Duration in seconds")
    categories: List[str] = Field(default_factory=list, description="Categories e.g. funny, reaction, storytelling")
    transcript: str = Field(description="Transcript text for this candidate segment")
    hook: str = Field(description="The opening statement or hook")
    payoff: str = Field(description="The payoff or punchline")
    reason: str = Field(description="Reasoning explaining why this is an engaging moment")
    confidence: float = Field(default=0.85, description="Confidence in moment validity")
    scores: CandidateScores = Field(default_factory=CandidateScores, description="Individual score metrics")


class CandidateReport(BaseModel):
    """Aggregated candidate moments report."""
    total_candidates: int = Field(description="Number of detected candidate moments")
    candidates: List[CandidateMoment] = Field(default_factory=list, description="List of candidates")
