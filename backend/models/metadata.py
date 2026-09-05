"""Data models for platform-specific social media metadata and thumbnails."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class PlatformMetadata(BaseModel):
    """Platform-specific title, caption, hashtags, and CTA."""
    title: str = Field(description="Platform-adapted headline or title")
    caption: str = Field(description="Full caption text tailored for platform feed")
    description: str = Field(description="Platform description if applicable")
    hashtags: List[str] = Field(default_factory=list, description="Relevant platform hashtags")
    keywords: List[str] = Field(default_factory=list, description="Searchable keyword tags")
    cta: str = Field(default="", description="Call to action text")


class ClipSocialMetadata(BaseModel):
    """Aggregated social media package and thumbnail reference for an individual clip."""
    clip_id: str = Field(description="Unique clip identifier")
    category: str = Field(description="Clip category name")
    primary_title: str = Field(description="Primary curiosity-driven headline")
    hook: str = Field(description="Hook line from clip")
    payoff: str = Field(description="Payoff line from clip")
    summary: str = Field(description="Brief conceptual synopsis of the moment")
    thumbnail_path: str = Field(description="Path to generated thumbnail image")
    hashtags: List[str] = Field(default_factory=list, description="General hashtag list")
    keywords: List[str] = Field(default_factory=list, description="General keywords")
    platforms: Dict[str, PlatformMetadata] = Field(
        default_factory=dict,
        description="Platform-specific metadata for youtube_shorts, instagram_reels, tiktok, facebook_reels",
    )


class ProjectMetadataReport(BaseModel):
    """Aggregated metadata generation report for all clips in a project."""
    project_id: str = Field(description="Associated project identifier")
    created_at: str = Field(description="Generation timestamp")
    total_clips: int = Field(description="Total clips processed")
    clips: List[ClipSocialMetadata] = Field(default_factory=list, description="Per-clip metadata packages")
