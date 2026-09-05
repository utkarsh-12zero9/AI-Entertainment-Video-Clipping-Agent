"""Scene and shot boundary detection using FFmpeg scene filters."""

import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from backend.config.settings import PipelineSettings, default_settings
from backend.models.vision import SceneBoundary
from backend.utils.errors import VideoPipelineError
from backend.utils.logger import logger


class SceneDetectorError(VideoPipelineError):
    """Raised when scene detection fails."""
    pass


class SceneDetector:
    """Detects scene cuts and shot boundaries using FFmpeg's scene detection filter."""

    def __init__(self, settings: Optional[PipelineSettings] = None):
        self.settings = settings or default_settings
        self._validate_ffmpeg_exists()

    def _validate_ffmpeg_exists(self) -> None:
        if not shutil.which(self.settings.ffmpeg_bin):
            raise SceneDetectorError(f"ffmpeg binary '{self.settings.ffmpeg_bin}' not found on PATH.")

    def detect_scenes(self, video_path: Path, video_duration: float) -> List[SceneBoundary]:
        """Runs fast scene change detection without full video decoding."""
        video_path = Path(video_path).resolve()
        if not video_path.exists():
            raise SceneDetectorError(f"Video file not found: {video_path}")

        logger.info(f"Detecting scene changes in: {video_path.name} (threshold={self.settings.scene_change_threshold})")

        # FFmpeg filter to detect scene changes and print timestamps to stderr
        # -filter:v "select='gt(scene,THRESHOLD)',showinfo" -f null -
        cmd = [
            self.settings.ffmpeg_bin,
            "-i", str(video_path),
            "-filter:v", f"select='gt(scene,{self.settings.scene_change_threshold})',showinfo",
            "-f", "null",
            "-"
        ]

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
        except Exception as e:
            raise SceneDetectorError(f"Failed to execute FFmpeg for scene detection: {e}") from e

        # Parse timestamps from showinfo lines in stderr: "pts_time:12.345"
        timestamps = [0.0]
        pts_regex = re.compile(r"pts_time:([0-9.]+)")
        for line in result.stderr.splitlines():
            if "showinfo" in line:
                match = pts_regex.search(line)
                if match:
                    pts = float(match.group(1))
                    if pts > timestamps[-1] + 0.5:  # Debounce cuts closer than 0.5s
                        timestamps.append(pts)

        if not timestamps or timestamps[-1] < video_duration:
            timestamps.append(video_duration)

        # Build clean SceneBoundary objects
        scenes = []
        for i in range(len(timestamps) - 1):
            start = round(timestamps[i], 2)
            end = round(timestamps[i + 1], 2)
            scenes.append(
                SceneBoundary(
                    scene_id=i + 1,
                    start=start,
                    end=end,
                    duration=round(end - start, 2)
                )
            )

        logger.info(f"Detected {len(scenes)} scene segments in {video_path.name}")
        return scenes
