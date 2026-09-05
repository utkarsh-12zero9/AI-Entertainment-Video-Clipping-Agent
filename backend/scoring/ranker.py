"""Weighted multimodal clip ranker with temporal diversity enforcement."""

from collections import defaultdict
from typing import Dict, List, Optional

from backend.clip_detection.boundary_optimizer import ClipBoundaryOptimizer
from backend.config.settings import PipelineSettings, default_settings
from backend.models.candidate import CandidateMoment, CandidateReport
from backend.models.clip import ClipSpecification, SelectedClipsReport
from backend.models.transcript import TranscriptResult
from backend.utils.logger import logger


class ClipRanker:
    """Ranks candidate moments using weighted multimodal scoring and enforces temporal diversity."""

    def __init__(self, settings: Optional[PipelineSettings] = None):
        self.settings = settings or default_settings
        self.boundary_optimizer = ClipBoundaryOptimizer(settings=self.settings)

    def calculate_weighted_score(self, candidate: CandidateMoment) -> float:
        """Calculates final ranked score using weighted dimensions specified in requirements:

        Hook: 20%
        Entertainment / Humor: 20%
        Standalone context: 15%
        Payoff: 15%
        Emotional impact: 10%
        Visual interest: 10%
        Audio quality: 5%
        Uniqueness / Social: 5%
        """
        s = candidate.scores
        payoff_score = 0.85 if len(candidate.payoff.strip()) > 5 else 0.50

        score = (
            (s.hook_strength * 0.20) +
            (s.humor * 0.20) +
            (s.context_completeness * 0.15) +
            (payoff_score * 0.15) +
            (s.emotion * 0.10) +
            (s.visual_interest * 0.10) +
            (0.85 * 0.05) + # Audio quality baseline
            (s.social_potential * 0.05)
        )
        return round(min(1.0, max(0.0, score)), 3)

    def rank_and_select_clips(
        self,
        report: CandidateReport,
        transcript: TranscriptResult,
        video_duration: float,
        max_clips: Optional[int] = None
    ) -> SelectedClipsReport:
        """Optimizes boundaries, scores, enforces diversity, and names top clips."""
        limit = max_clips or self.settings.max_clips
        logger.info(f"Ranking and selecting top clips (limit={limit})...")

        # First calculate weighted score and optimize boundaries for each candidate
        scored_candidates = []
        for cand in report.candidates:
            final_score = self.calculate_weighted_score(cand)
            opt_start, opt_end, opt_hook, opt_payoff, opt_transcript = (
                self.boundary_optimizer.optimize_boundaries(cand, transcript, video_duration)
            )
            duration = round(opt_end - opt_start, 2)

            scored_candidates.append({
                "candidate": cand,
                "score": final_score,
                "start": opt_start,
                "end": opt_end,
                "duration": duration,
                "hook": opt_hook,
                "payoff": opt_payoff,
                "transcript": opt_transcript
            })

        # Sort descending by composite score
        scored_candidates.sort(key=lambda x: x["score"], reverse=True)

        selected_items = []
        category_counters: Dict[str, int] = defaultdict(int)

        for item in scored_candidates:
            if len(selected_items) >= limit:
                break

            # Enforce temporal diversity (must not start within min_clip_spacing_sec of an already picked clip)
            conflict = False
            for sel in selected_items:
                time_diff = abs(item["start"] - sel.start_time)
                if time_diff < self.settings.min_clip_spacing_sec:
                    conflict = True
                    break

            if conflict:
                continue

            # Assign category-prefixed ID e.g. funny_001, surprising_001
            cand = item["candidate"]
            primary_cat = cand.categories[0] if cand.categories else "highlight"
            category_counters[primary_cat] += 1
            clip_id = f"{primary_cat}_{category_counters[primary_cat]:03d}"

            spec = ClipSpecification(
                clip_id=clip_id,
                candidate_id=cand.id,
                start_time=item["start"],
                end_time=item["end"],
                duration=item["duration"],
                category=primary_cat,
                categories=cand.categories,
                score=item["score"],
                reason=f"Ranked #{len(selected_items)+1} with score {item['score']:.2f}. {cand.reason}",
                hook=item["hook"],
                payoff=item["payoff"],
                transcript=item["transcript"]
            )
            selected_items.append(spec)

        logger.info(f"Selected {len(selected_items)} optimal clips out of {len(report.candidates)} candidates.")
        return SelectedClipsReport(
            total_selected=len(selected_items),
            clips=selected_items
        )
