"""Platform-aware social media metadata generator module.

Generates tailored, non-blind, platform-specific metadata packages for:
- YouTube Shorts
- Instagram Reels
- TikTok
- Facebook Reels
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Dict, List, Optional

from backend.config.settings import PipelineSettings, get_settings
from backend.models.clip import ClipSpecification, SelectedClipsReport
from backend.models.metadata import ClipSocialMetadata, PlatformMetadata, ProjectMetadataReport
from backend.models.video import ProjectWorkspace
from backend.utils.logger import get_logger

logger = get_logger("social_metadata_generator")


class SocialMetadataGenerator:
    """Generates curiosity-driven, platform-adapted titles, captions, hashtags, and CTAs."""

    def __init__(self, settings: Optional[PipelineSettings] = None):
        self.settings = settings or get_settings()

    def _generate_candidate_titles(self, clip_spec: ClipSpecification) -> List[str]:
        """Generates candidate curiosity-driven titles and returns sorted list."""
        hook = clip_spec.hook.strip().rstrip(".!?")
        cat = clip_spec.category.lower()

        candidates = [
            f"Wait Until You Hear This... ({hook})",
            f"The Moment Everything Changed: {hook}",
            f"I Can't Believe This Happened! #{cat.capitalize()}",
            f"Nobody Expected This Reaction ({cat})",
            f"{hook} 🤯",
        ]
        # Filter candidate length <= 60 characters for mobile display
        valid_candidates = [c for c in candidates if len(c) <= 60]
        return valid_candidates if valid_candidates else [hook[:55] + "..."]

    def _generate_hashtags(self, clip_spec: ClipSpecification, platform: str) -> List[str]:
        """Generates platform-specific hashtags."""
        cat = clip_spec.category.lower()
        base_tags = [f"#{cat}", "#entertainment", "#mustwatch", "#trending"]

        if platform == "youtube_shorts":
            return ["#Shorts", "#ShortsFeed", f"#{cat}Shorts"] + base_tags[:3]
        elif platform == "tiktok":
            return ["#fyp", "#foryou", "#viral", f"#{cat}tiktok"] + base_tags[:2]
        elif platform == "instagram_reels":
            return ["#reels", "#reelsinstagram", "#explorepage", f"#{cat}reels"] + base_tags
        elif platform == "facebook_reels":
            return ["#reelsfb", "#fbreels", f"#{cat}clip"] + base_tags[:3]
        return base_tags

    def _generate_cta(self, clip_spec: ClipSpecification, platform: str) -> str:
        """Generates tailored engagement Call To Action."""
        cat = clip_spec.category.lower()
        if "funny" in cat:
            return "Tag someone who needs a laugh today! 😂"
        elif "storytelling" in cat or "insightful" in cat:
            return "What would you have done in this situation? Let me know below!"
        elif "surprising" in cat or "shocking" in cat:
            return "Did you see that coming? Drop your reaction below! 👇"
        return "Hit follow for more daily entertainment clips!"

    def generate_clip_metadata(
        self,
        clip_spec: ClipSpecification,
        thumbnail_path: Path,
    ) -> ClipSocialMetadata:
        """Generates complete platform-aware social metadata for a clip.

        Args:
            clip_spec: Clip specification.
            thumbnail_path: Path to associated thumbnail image.

        Returns:
            ClipSocialMetadata object with tailored platform records.
        """
        titles = self._generate_candidate_titles(clip_spec)
        primary_title = titles[0]

        hook = clip_spec.hook
        payoff = clip_spec.payoff
        cat = clip_spec.category
        summary = getattr(clip_spec, "reason", "") or f"High impact {cat} entertainment moment."

        platforms_data: Dict[str, PlatformMetadata] = {}

        # 1. YouTube Shorts
        yt_tags = self._generate_hashtags(clip_spec, "youtube_shorts")
        platforms_data["youtube_shorts"] = PlatformMetadata(
            title=f"{primary_title} #Shorts"[:60],
            caption=f"{hook}\n\n{payoff}\n\nSubscribe for daily clips! #Shorts",
            description=f"{summary}\n\nHook: {hook}\nPayoff: {payoff}\n\n" + " ".join(yt_tags),
            hashtags=yt_tags,
            keywords=[cat, "shorts", "viral clip", "entertainment", "podcast highlight"],
            cta="Subscribe for more highlights!",
        )

        # 2. Instagram Reels
        ig_tags = self._generate_hashtags(clip_spec, "instagram_reels")
        ig_cta = self._generate_cta(clip_spec, "instagram_reels")
        platforms_data["instagram_reels"] = PlatformMetadata(
            title=primary_title,
            caption=f"{hook} 🍿\n.\n{payoff}\n.\n{ig_cta}\n.\n" + " ".join(ig_tags),
            description="",
            hashtags=ig_tags,
            keywords=[cat, "reels", "explore"],
            cta=ig_cta,
        )

        # 3. TikTok
        tt_tags = self._generate_hashtags(clip_spec, "tiktok")
        tt_cta = self._generate_cta(clip_spec, "tiktok")
        platforms_data["tiktok"] = PlatformMetadata(
            title=primary_title,
            caption=f"{hook} 😳 wait for the end! {tt_cta} " + " ".join(tt_tags[:5]),
            description="",
            hashtags=tt_tags,
            keywords=[cat, "fyp", "viral"],
            cta=tt_cta,
        )

        # 4. Facebook Reels
        fb_tags = self._generate_hashtags(clip_spec, "facebook_reels")
        fb_cta = self._generate_cta(clip_spec, "facebook_reels")
        platforms_data["facebook_reels"] = PlatformMetadata(
            title=primary_title,
            caption=f"{primary_title}\n\n{hook}\n\n{fb_cta}\n\n" + " ".join(fb_tags),
            description="",
            hashtags=fb_tags,
            keywords=[cat, "reels"],
            cta=fb_cta,
        )

        return ClipSocialMetadata(
            clip_id=str(clip_spec.clip_id),
            category=cat,
            primary_title=primary_title,
            hook=hook,
            payoff=payoff,
            summary=summary,
            thumbnail_path=str(thumbnail_path),
            hashtags=self._generate_hashtags(clip_spec, "base"),
            keywords=[cat, "clip", "highlight", "entertainment"],
            platforms=platforms_data,
        )

    def generate_all_metadata(
        self,
        report: SelectedClipsReport,
        workspace: ProjectWorkspace,
        thumbnails_map: Optional[Dict[str, Path]] = None,
    ) -> Dict[str, ClipSocialMetadata]:
        """Generates metadata for all selected clips in report.

        Returns:
            Dict mapping clip_id to ClipSocialMetadata.
        """
        results: Dict[str, ClipSocialMetadata] = {}
        thumbs = thumbnails_map or {}

        for clip_spec in report.clips:
            thumb_path = thumbs.get(clip_spec.clip_id) or (workspace.thumbnails_dir / f"{clip_spec.clip_id}.jpg")
            meta = self.generate_clip_metadata(clip_spec, thumb_path)
            results[clip_spec.clip_id] = meta

        return results

    def process_all_clips(
        self,
        report: SelectedClipsReport,
        workspace: ProjectWorkspace,
    ) -> ProjectMetadataReport:
        """Generates metadata for all selected clips and saves JSON packages."""
        from backend.metadata.thumbnail_generator import ThumbnailGenerator
        thumb_gen = ThumbnailGenerator(settings=self.settings)

        results: List[ClipSocialMetadata] = []

        workspace.thumbnails.mkdir(parents=True, exist_ok=True)
        workspace.metadata.mkdir(parents=True, exist_ok=True)

        for clip_spec in report.clips:
            filename = getattr(clip_spec, "output_filename", None) or f"{clip_spec.clip_id}.mp4"
            thumb_filename = f"{clip_spec.clip_id}.jpg"
            thumb_path = workspace.thumbnails / thumb_filename

            # Locate video to source thumbnail from (prefer captioned > edited > raw)
            src_video = None
            for cand_dir in [workspace.captioned_clips, workspace.edited_clips_dir, workspace.raw_clips_dir]:
                p1 = cand_dir / clip_spec.category / filename
                p2 = cand_dir / filename
                if p1.exists():
                    src_video = p1
                    break
                elif p2.exists():
                    src_video = p2
                    break

            # Generate thumbnail if source video exists
            if src_video and src_video.exists():
                try:
                    thumb_gen.generate_thumbnail(src_video, thumb_path, clip_spec)
                except Exception as e:
                    logger.warning(f"Failed to generate thumbnail for {clip_spec.clip_id}: {e}")

            # Generate platform social metadata
            metadata_obj = self.generate_clip_metadata(clip_spec, thumb_path)

            # Save individual metadata JSON file: metadata/<clip_id>.json
            meta_file = workspace.metadata / f"{clip_spec.clip_id}.json"
            with open(meta_file, "w", encoding="utf-8") as f:
                f.write(metadata_obj.model_dump_json(indent=4))

            results.append(metadata_obj)

        proj_report = ProjectMetadataReport(
            project_id=workspace.project_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            total_clips=len(results),
            clips=results,
        )

        logger.info(f"Generated social metadata and thumbnails for {len(results)} clips in {workspace.project_id}.")
        return proj_report

