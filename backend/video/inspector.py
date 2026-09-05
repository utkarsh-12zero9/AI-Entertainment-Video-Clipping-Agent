"""Video Inspector module wrapping ffprobe for validation and metadata extraction."""

import json
import math
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from backend.config.settings import PipelineSettings, default_settings
from backend.models.video import VideoMetadata
from backend.utils.errors import (
    CorruptedVideoError,
    FFprobeExecutionError,
    MissingVideoError,
    NoAudioError,
    VideoTooShortError,
)
from backend.utils.logger import logger


def calculate_aspect_ratio(width: int, height: int) -> str:
    """Calculates a clean aspect ratio representation (e.g. 16:9, 9:16, 4:3, 1:1)."""
    if width <= 0 or height <= 0:
        return "unknown"
    
    gcd = math.gcd(width, height)
    num = width // gcd
    den = height // gcd
    
    # Check for standard known ratios within a small tolerance
    ratio = width / height
    standard_ratios = [
        (16 / 9, "16:9"),
        (9 / 16, "9:16"),
        (4 / 3, "4:3"),
        (3 / 4, "3:4"),
        (1 / 1, "1:1"),
        (21 / 9, "21:9"),
    ]
    for std_val, std_label in standard_ratios:
        if abs(ratio - std_val) < 0.02:
            return std_label
            
    return f"{num}:{den}"


def parse_fps(r_frame_rate: str) -> float:
    """Safely converts ffprobe frame rate fractional string (e.g. '30/1' or '30000/1001') to float."""
    try:
        if "/" in r_frame_rate:
            num, den = r_frame_rate.split("/")
            if float(den) == 0:
                return 0.0
            return round(float(num) / float(den), 3)
        return round(float(r_frame_rate), 3)
    except Exception:
        return 0.0


class VideoInspector:
    """Inspects video files using ffprobe and validates media stream characteristics."""

    def __init__(self, settings: Optional[PipelineSettings] = None):
        self.settings = settings or default_settings
        self._validate_ffprobe_exists()

    def _validate_ffprobe_exists(self) -> None:
        """Verifies that ffprobe binary is accessible."""
        if not shutil.which(self.settings.ffprobe_bin):
            raise FFprobeExecutionError(
                f"ffprobe executable '{self.settings.ffprobe_bin}' not found on system PATH."
            )

    def run_ffprobe(self, video_path: Path) -> Dict[str, Any]:
        """Runs ffprobe with JSON output format."""
        cmd = [
            self.settings.ffprobe_bin,
            "-v", "error",
            "-show_format",
            "-show_streams",
            "-print_format", "json",
            str(video_path)
        ]
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
        except Exception as e:
            raise FFprobeExecutionError(f"Failed to execute ffprobe: {e}") from e

        if result.returncode != 0:
            raise CorruptedVideoError(
                f"ffprobe failed to parse video '{video_path}': {result.stderr.strip()}"
            )

        try:
            probe_data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise CorruptedVideoError(f"Failed to decode ffprobe output as JSON: {e}") from e

        return probe_data

    def inspect(self, video_path: Path) -> VideoMetadata:
        """Extracts and validates video metadata from the given video file path."""
        video_path = Path(video_path).resolve()
        
        logger.info(f"Inspecting video: {video_path}")

        if not video_path.exists():
            raise MissingVideoError(f"Video file does not exist: {video_path}")

        if not video_path.is_file() or video_path.stat().st_size == 0:
            raise CorruptedVideoError(f"File is empty or not a valid regular file: {video_path}")

        file_size = video_path.stat().st_size
        probe_data = self.run_ffprobe(video_path)

        streams = probe_data.get("streams", [])
        format_info = probe_data.get("format", {})

        video_stream = None
        audio_stream = None

        for stream in streams:
            codec_type = stream.get("codec_type")
            if codec_type == "video" and video_stream is None:
                video_stream = stream
            elif codec_type == "audio" and audio_stream is None:
                audio_stream = stream

        if not video_stream:
            raise CorruptedVideoError(f"No valid video stream found in: {video_path}")

        # Parse duration
        duration_str = format_info.get("duration") or video_stream.get("duration")
        if not duration_str:
            raise CorruptedVideoError(f"Could not determine video duration for: {video_path}")
        
        try:
            duration = float(duration_str)
        except (ValueError, TypeError) as e:
            raise CorruptedVideoError(f"Invalid duration value '{duration_str}': {e}") from e

        if duration < self.settings.min_video_duration:
            raise VideoTooShortError(
                f"Video duration ({duration:.2f}s) is shorter than minimum required ({self.settings.min_video_duration:.2f}s)"
            )

        # Video stream parameters
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        if width <= 0 or height <= 0:
            raise CorruptedVideoError(f"Invalid video dimensions {width}x{height} in {video_path}")

        fps = parse_fps(video_stream.get("r_frame_rate", "0/0"))
        if fps <= 0:
            fps = parse_fps(video_stream.get("avg_frame_rate", "0/0"))

        video_codec = video_stream.get("codec_name", "unknown")
        
        # Bitrate
        bitrate = None
        if "bit_rate" in format_info and format_info["bit_rate"].isdigit():
            bitrate = int(format_info["bit_rate"])
        elif "bit_rate" in video_stream and str(video_stream["bit_rate"]).isdigit():
            bitrate = int(video_stream["bit_rate"])

        # Audio stream validation
        has_audio = audio_stream is not None
        audio_codec = None
        sample_rate = None
        channels = None

        if has_audio:
            audio_codec = audio_stream.get("codec_name")
            if "sample_rate" in audio_stream and str(audio_stream["sample_rate"]).isdigit():
                sample_rate = int(audio_stream["sample_rate"])
            if "channels" in audio_stream and str(audio_stream["channels"]).isdigit():
                channels = int(audio_stream["channels"])

        if self.settings.require_audio and not has_audio:
            raise NoAudioError(f"Video does not contain any usable audio stream: {video_path}")

        aspect_ratio = calculate_aspect_ratio(width, height)

        metadata = VideoMetadata(
            filename=video_path.name,
            duration=round(duration, 3),
            width=width,
            height=height,
            fps=fps,
            codec=video_codec,
            bitrate=bitrate,
            has_audio=has_audio,
            audio_codec=audio_codec,
            sample_rate=sample_rate,
            channels=channels,
            aspect_ratio=aspect_ratio,
            file_size=file_size,
        )

        logger.info(
            f"Video inspected successfully: {metadata.width}x{metadata.height} @ {metadata.fps}fps, "
            f"duration={metadata.duration}s, aspect_ratio={metadata.aspect_ratio}, audio={metadata.has_audio}"
        )
        return metadata
