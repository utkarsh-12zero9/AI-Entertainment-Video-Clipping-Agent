"""Intelligent frame sampler supporting fixed interval, scene-change, and adaptive sampling."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from backend.config.settings import PipelineSettings, default_settings
from backend.models.vision import FrameIndex, FrameInfo, SceneBoundary
from backend.utils.errors import VideoPipelineError
from backend.utils.logger import logger


class FrameSamplerError(VideoPipelineError):
    """Raised when frame sampling fails."""
    pass


class FrameSampler:
    """Intelligently samples representative video frames with accurate timestamps."""

    def __init__(self, settings: Optional[PipelineSettings] = None):
        self.settings = settings or default_settings
        self._validate_ffmpeg_exists()

    def _validate_ffmpeg_exists(self) -> None:
        if not shutil.which(self.settings.ffmpeg_bin):
            raise FrameSamplerError(f"ffmpeg binary '{self.settings.ffmpeg_bin}' not found on PATH.")

    def compute_sample_timestamps(
        self,
        duration: float,
        strategy: str,
        scenes: Optional[List[SceneBoundary]] = None
    ) -> List[float]:
        """Calculates precise timestamps for sampling based on strategy."""
        timestamps: List[float] = []

        if strategy == "fixed_interval":
            interval = self.settings.frame_sample_interval
            t = 0.0
            while t < duration:
                timestamps.append(round(t, 2))
                t += interval

        elif strategy == "scene_change" and scenes:
            for scene in scenes:
                # Midpoint of the scene
                midpoint = (scene.start + scene.end) / 2.0
                timestamps.append(round(midpoint, 2))

        else:  # "adaptive" (default)
            # Combine scene midpoints with min/max interval bounds
            if scenes:
                for scene in scenes:
                    midpoint = (scene.start + scene.end) / 2.0
                    timestamps.append(round(midpoint, 2))
                    # If scene is long, sample inside it as well
                    if scene.duration > self.settings.max_sample_interval:
                        sub_t = scene.start + self.settings.frame_sample_interval
                        while sub_t < scene.end:
                            timestamps.append(round(sub_t, 2))
                            sub_t += self.settings.frame_sample_interval
            else:
                interval = self.settings.frame_sample_interval
                t = 0.0
                while t < duration:
                    timestamps.append(round(t, 2))
                    t += interval

        # Sort, deduplicate, and enforce within [0, duration]
        cleaned = []
        for t in sorted(timestamps):
            t_val = max(0.0, min(round(t, 2), max(0.0, duration - 0.1)))
            if not cleaned or (t_val - cleaned[-1] >= self.settings.min_sample_interval):
                cleaned.append(t_val)

        if not cleaned:
            cleaned = [0.0]

        return cleaned

    def sample_frames(
        self,
        video_path: Path,
        frames_dir: Path,
        duration: float,
        scenes: Optional[List[SceneBoundary]] = None,
        strategy: Optional[str] = None
    ) -> FrameIndex:
        """Extracts high quality JPEG frames and builds the FrameIndex."""
        video_path = Path(video_path).resolve()
        frames_dir = Path(frames_dir).resolve()
        frames_dir.mkdir(parents=True, exist_ok=True)

        chosen_strategy = strategy or self.settings.frame_sampling_strategy
        sample_times = self.compute_sample_timestamps(duration, chosen_strategy, scenes)

        logger.info(
            f"Sampling {len(sample_times)} frames from {video_path.name} using strategy '{chosen_strategy}'"
        )

        extracted_frames: List[FrameInfo] = []

        for idx, ts in enumerate(sample_times, start=1):
            frame_filename = f"frame_{idx:06d}.jpg"
            out_file = frames_dir / frame_filename

            # Extract exact frame using ffmpeg -ss before -i for fast accurate seek
            cmd = [
                self.settings.ffmpeg_bin,
                "-y",
                "-ss", str(ts),
                "-i", str(video_path),
                "-frames:v", "1",
                "-q:v", "2",
                str(out_file)
            ]

            try:
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            except Exception as e:
                logger.warning(f"Could not sample frame at {ts}s: {e}")
                continue

            if out_file.exists() and out_file.stat().st_size > 0:
                # Read dimensions using Pillow or OpenCV
                try:
                    from PIL import Image
                    with Image.open(out_file) as img:
                        w, h = img.size
                except Exception:
                    w, h = 1920, 1080

                extracted_frames.append(
                    FrameInfo(
                        frame_index=idx,
                        filename=frame_filename,
                        timestamp=ts,
                        width=w,
                        height=h
                    )
                )

        frame_index = FrameIndex(
            total_frames=len(extracted_frames),
            sampling_strategy=chosen_strategy,
            frames=extracted_frames
        )

        # Save frames/index.json
        index_path = frames_dir / "index.json"
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(frame_index.model_dump_json(indent=4))

        logger.info(f"Frame sampling complete. Saved {len(extracted_frames)} frames and {index_path.name}")
        return frame_index
