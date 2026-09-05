"""Semantic text deduplication and category diversity balancer.

Eliminates repetitive candidate moments, near-duplicate jokes/dialogue, and
enforces multi-category variety for production video clipping.
"""

from collections import defaultdict
import re
from typing import Any, Dict, List, Set, Tuple

from backend.config.settings import PipelineSettings, get_settings
from backend.utils.logger import get_logger

logger = get_logger("deduplicator")


class SemanticClipDeduplicator:
    """Detects and filters near-duplicate transcripts and enforces category diversity."""

    def __init__(self, settings: PipelineSettings = None):
        self.settings = settings or get_settings()

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Normalizes and tokenizes text into lowercase words, ignoring punctuation."""
        clean = re.sub(r"[^\w\s]", "", text.lower())
        return [w for w in clean.split() if len(w) > 2]

    @classmethod
    def calculate_token_jaccard(cls, text_a: str, text_b: str) -> float:
        """Calculates Jaccard similarity across unique word tokens (0.0 to 1.0)."""
        tokens_a = set(cls.tokenize(text_a))
        tokens_b = set(cls.tokenize(text_b))
        if not tokens_a or not tokens_b:
            return 0.0
        intersection = tokens_a.intersection(tokens_b)
        union = tokens_a.union(tokens_b)
        return len(intersection) / len(union)

    @classmethod
    def calculate_bigram_similarity(cls, text_a: str, text_b: str) -> float:
        """Calculates bi-gram overlap similarity to detect identical phrases or jokes."""
        words_a = cls.tokenize(text_a)
        words_b = cls.tokenize(text_b)
        if len(words_a) < 2 or len(words_b) < 2:
            return cls.calculate_token_jaccard(text_a, text_b)

        bigrams_a = set(zip(words_a[:-1], words_a[1:]))
        bigrams_b = set(zip(words_b[:-1], words_b[1:]))
        if not bigrams_a or not bigrams_b:
            return 0.0
        return len(bigrams_a.intersection(bigrams_b)) / len(bigrams_a.union(bigrams_b))

    def are_transcripts_duplicate(self, text_a: str, text_b: str) -> Tuple[bool, float]:
        """Determines whether two transcripts are semantic duplicates based on threshold."""
        jaccard = self.calculate_token_jaccard(text_a, text_b)
        bigram = self.calculate_bigram_similarity(text_a, text_b)
        # Combined semantic similarity
        sim = max(jaccard, bigram)
        threshold = self.settings.dedup_similarity_threshold
        return (sim >= threshold, round(sim, 3))

    def filter_and_diversify(
        self,
        scored_candidates: List[Dict[str, Any]],
        max_clips: int,
    ) -> List[Dict[str, Any]]:
        """Filters out duplicates, enforces category quotas, and selects top diverse clips.

        Each candidate dict is expected to contain:
          - "candidate": CandidateMoment
          - "score": float
          - "start": float
          - "end": float
          - "transcript": str
        """
        selected: List[Dict[str, Any]] = []
        category_counts: Dict[str, int] = defaultdict(int)
        max_per_cat = self.settings.category_max_clips_per_type

        for item in scored_candidates:
            if len(selected) >= max_clips:
                break

            cand = item["candidate"]
            category = cand.categories[0] if cand.categories else "highlight"
            transcript = item.get("transcript", "")
            start = item["start"]

            # 1. Check category quota
            if category_counts[category] >= max_per_cat:
                logger.debug(f"Skipping candidate {cand.id}: category '{category}' quota ({max_per_cat}) reached.")
                continue

            # 2. Check temporal proximity against already selected clips
            temporal_conflict = False
            for sel in selected:
                if abs(start - sel["start"]) < self.settings.min_clip_spacing_sec:
                    temporal_conflict = True
                    break
            if temporal_conflict:
                continue

            # 3. Check semantic duplicate against already selected clips
            is_dup = False
            for sel in selected:
                dup, sim = self.are_transcripts_duplicate(transcript, sel.get("transcript", ""))
                if dup:
                    is_dup = True
                    logger.info(
                        f"Deduplicated candidate {cand.id} (sim={sim:.2f}) against {sel['candidate'].id}."
                    )
                    break

            if is_dup:
                continue

            # Accepted
            selected.append(item)
            category_counts[category] += 1

        return selected
