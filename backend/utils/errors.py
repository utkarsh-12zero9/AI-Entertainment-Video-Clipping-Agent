"""Custom exception definitions for Video Ingestion and Validation."""


class VideoPipelineError(Exception):
    """Base exception for all video processing pipeline errors."""
    pass


class VideoValidationError(VideoPipelineError):
    """Raised when a video fails validation rules."""
    pass


class MissingVideoError(VideoValidationError):
    """Raised when the specified video file does not exist."""
    pass


class CorruptedVideoError(VideoValidationError):
    """Raised when video file cannot be probed or decoded."""
    pass


class NoAudioError(VideoValidationError):
    """Raised when a video lacks a usable audio stream."""
    pass


class VideoTooShortError(VideoValidationError):
    """Raised when video duration is less than the minimum required duration."""
    pass


class FFprobeExecutionError(VideoPipelineError):
    """Raised when ffprobe execution fails."""
    pass
