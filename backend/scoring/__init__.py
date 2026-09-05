"""Scoring package."""
from backend.scoring.deduplicator import SemanticClipDeduplicator
from backend.scoring.ranker import ClipRanker

__all__ = ["ClipRanker", "SemanticClipDeduplicator"]
