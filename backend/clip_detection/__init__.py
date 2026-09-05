"""Clip detection package."""
from backend.clip_detection.contextual_window import ContextualWindow, ContextualWindowExtractor
from backend.clip_detection.detector import EntertainmentMomentDetector, calculate_iou
from backend.clip_detection.multimodal_scorer import MultimodalScorer

__all__ = [
    "ContextualWindow",
    "ContextualWindowExtractor",
    "MultimodalScorer",
    "EntertainmentMomentDetector",
    "calculate_iou",
]
