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
    
    # Stage 3: Visual Frame Sampling & Analysis
    frame_sampling_strategy: str = Field(default="adaptive", description="fixed_interval, scene_change, or adaptive")
    frame_sample_interval: float = Field(default=2.0, description="Fixed interval in seconds between frame samples")
    min_sample_interval: float = Field(default=1.0, description="Minimum interval for adaptive sampling")
    max_sample_interval: float = Field(default=5.0, description="Maximum interval for adaptive sampling")
    scene_change_threshold: float = Field(default=0.35, description="FFmpeg scene detection threshold (0.0 to 1.0)")

    # Stage 4: Multimodal Entertainment Moment Detection
    min_candidate_duration: float = Field(default=15.0, description="Minimum duration for candidate moment in seconds")
    max_candidate_duration: float = Field(default=45.0, description="Maximum duration for candidate moment in seconds")
    min_candidate_score: float = Field(default=0.50, description="Minimum overall social potential score threshold")
    max_candidate_overlap_iou: float = Field(default=0.50, description="Maximum IoU threshold before merging candidates")

    # Stage 5: Clip Ranking & Boundary Optimization
    max_clips: int = Field(default=8, description="Maximum number of top clips to select")
    min_clip_spacing_sec: float = Field(default=15.0, description="Minimum time spacing between different selected clips")
    target_clip_duration: float = Field(default=25.0, description="Ideal target clip duration in seconds")
    boundary_audio_padding_sec: float = Field(default=0.35, description="Breathing room/reaction padding at clip end")

    # Stage 6: Raw Clip Extraction & QA
    clip_crf: int = Field(default=18, description="Constant Rate Factor for high-quality x264 extraction")
    clip_preset: str = Field(default="fast", description="FFmpeg x264 preset")
    clip_audio_bitrate: str = Field(default="192k", description="Audio bitrate for clip extraction")
    qa_duration_tolerance_sec: float = Field(default=0.75, description="Allowed duration deviation in seconds")
    qa_max_allowed_silence_sec: float = Field(default=4.0, description="Max acceptable continuous silence")

    # Stage 7: Vertical Social Media Editing
    target_vertical_width: int = Field(default=1080, description="Target vertical video width in pixels")
    target_vertical_height: int = Field(default=1920, description="Target vertical video height in pixels")
    target_aspect_ratio: str = Field(default="9:16", description="Target aspect ratio for mobile platforms")
    reframing_strategy: str = Field(default="smart_face", description="Smart reframing strategy: 'smart_face' or 'center'")
    audio_loudnorm_target: float = Field(default=-14.0, description="EBU R128 integrated loudness target (LUFS)")
    enable_visual_enhancements: bool = Field(default=True, description="Apply subtle sharpening and contrast optimization")

    # Stage 8: Caption Engine
    caption_style: str = Field(default="bold_highlight", description="Caption style: 'bold_highlight', 'clean', or 'karaoke'")
    caption_font_name: str = Field(default="Arial", description="Font name for rendered subtitles")
    caption_font_size: int = Field(default=18, description="Base font size in ASS units (rendered to 1080x1920)")
    caption_primary_color: str = Field(default="&H00FFFFFF", description="ASS color for standard text (White)")
    caption_highlight_color: str = Field(default="&H0000FFFF", description="ASS color for highlighted keywords (Bright Yellow)")
    caption_outline_color: str = Field(default="&H00000000", description="ASS outline/shadow color (Black)")
    caption_max_words_per_chunk: int = Field(default=4, description="Maximum words per short subtitle chunk")
    caption_max_chars_per_line: int = Field(default=28, description="Maximum characters per subtitle line")

    # Stage 9: Thumbnail & Social Metadata
    thumbnail_overlay_text: bool = Field(default=True, description="Whether to render high-contrast hook text banner onto thumbnail")
    thumbnail_font_size: int = Field(default=52, description="Font size for thumbnail overlay text")
    thumbnail_num_sample_frames: int = Field(default=15, description="Number of candidate frames to sample and score for thumbnail")
    default_platforms: list[str] = Field(
        default=["youtube_shorts", "instagram_reels", "tiktok", "facebook_reels"],
        description="Target social media platforms for metadata generation"
    )

    # Stage 10: Final Multimodal QA
    qa_min_overall_score: float = Field(default=0.75, description="Minimum overall multimodal QA score to pass (0.0 to 1.0)")
    qa_promote_passing_to_final: bool = Field(default=True, description="Automatically copy passing clips, thumbnails, and metadata to final/")
    qa_abrupt_cut_tolerance_sec: float = Field(default=0.25, description="Tolerance buffer in seconds when evaluating word speech boundaries")

    # Tool binaries
    ffmpeg_bin: str = Field(default="ffmpeg", description="Path or command for ffmpeg")
    ffprobe_bin: str = Field(default="ffprobe", description="Path or command for ffprobe")



# Default global settings instance
default_settings = PipelineSettings()


def get_settings() -> PipelineSettings:
    """Returns the default pipeline settings instance."""
    return default_settings

