"""Multimodal candidate scorer fusing linguistic, audio, and visual intelligence."""

import re
from typing import List, Optional, Set, Tuple
import numpy as np

from backend.audio.analyzer import AudioSignalAnalyzer
from backend.clip_detection.contextual_window import ContextualWindow
from backend.models.candidate import CandidateScores
from backend.models.vision import VisualAnalysisResult


# Linguistic patterns indicative of entertainment & narrative hooks
QUESTION_PATTERNS = re.compile(r"(\bwhy\b|\bhow\b|\bwhat\b|\bwho\b|\bcan you\b|\bdid you\b|\bwould you\b|\?)", re.I)
SURPRISE_PATTERNS = re.compile(r"(\bunbelievable\b|\bnever\b|\bactually\b|\bshocking\b|\bno way\b|\bsecret\b|\btruth\b|\bturned out\b|\bsuddenly\b|\bmistake\b|\bwrong\b|\bcrazy\b)", re.I)
HUMOR_PATTERNS = re.compile(r"(\bjoke\b|\blaugh\b|\bfunny\b|\bridi\w+|\bhilarious\b|\bkidding\b|\bseriously\b|\broast\b)", re.I)
EMOTION_PATTERNS = re.compile(r"(\blove\b|\bhate\b|\bfear\b|\bscared\b|\bcried\b|\bheart\b|\bfeel\b|\bterrible\b|\binsane\b|\banger\b|\bobsess\w+)", re.I)
STORY_PATTERNS = re.compile(r"(\bso I was\b|\bone day\b|\bthen he\b|\bthen she\b|\band I said\b|\bthe moment\b|\bback when\b|\bI remember\b)", re.I)
HIGH_ENERGY_PATTERNS = re.compile(r"(\bwait\b|\blisten\b|\blook at this\b|\byou won't believe\b|\bwatch this\b|\bstop\b|\bcheck this out\b|!)", re.I)


class MultimodalScorer:
    """Evaluates candidate speech windows across text, audio energy, and visual signals."""

    def __init__(
        self,
        audio_analyzer: Optional[AudioSignalAnalyzer] = None,
        rms_profile: Optional[np.ndarray] = None
    ):
        self.audio_analyzer = audio_analyzer or AudioSignalAnalyzer()
        self.rms_profile = rms_profile if rms_profile is not None else np.zeros(0)

    def score_window(
        self,
        window: ContextualWindow,
        visual_analysis: Optional[VisualAnalysisResult] = None
    ) -> Tuple[CandidateScores, List[str], str]:
        """Calculates granular candidate scores, assigned categories, and reasoning."""
        text = window.full_text
        hook = window.hook_text
        payoff = window.payoff_text

        categories: Set[str] = set()

        # 1. Linguistic Scoring
        # Hook strength: questions, high-energy openers, direct address
        hook_score = 0.40
        if QUESTION_PATTERNS.search(hook):
            hook_score += 0.30
            categories.add("insightful")
        if HIGH_ENERGY_PATTERNS.search(hook):
            hook_score += 0.25
            categories.add("high_energy")
        hook_score = min(1.0, hook_score)

        # Humor & punchline
        humor_score = 0.20
        humor_matches = len(HUMOR_PATTERNS.findall(text))
        if humor_matches > 0:
            humor_score += min(0.60, humor_matches * 0.25)
            categories.add("funny")
            if "?" in hook or "." in payoff:
                categories.add("punchline")
        humor_score = min(1.0, humor_score)

        # Surprise & shock
        surprise_score = 0.20
        surprise_matches = len(SURPRISE_PATTERNS.findall(text))
        if surprise_matches > 0:
            surprise_score += min(0.65, surprise_matches * 0.22)
            categories.add("surprising")
            if surprise_matches > 2:
                categories.add("shocking")
        surprise_score = min(1.0, surprise_score)

        # Emotional intensity
        emotion_score = 0.20
        emotion_matches = len(EMOTION_PATTERNS.findall(text))
        if emotion_matches > 0:
            emotion_score += min(0.60, emotion_matches * 0.20)
            categories.add("emotional")
        emotion_score = min(1.0, emotion_score)

        # Storytelling
        if STORY_PATTERNS.search(text):
            categories.add("storytelling")

        # 2. Audio Energy Scoring
        audio_energy = 0.50
        if len(self.rms_profile) > 0:
            audio_energy = self.audio_analyzer.get_energy_in_range(
                self.rms_profile, window.start_time, window.end_time
            )
            if audio_energy > 0.65:
                categories.add("high_energy")

        # 3. Visual Interest Scoring
        visual_score = 0.50
        if visual_analysis and visual_analysis.frames:
            # Find frames overlapping with this window
            overlapping_frames = [
                f for f in visual_analysis.frames
                if window.start_time <= f.timestamp <= window.end_time
            ]
            if overlapping_frames:
                # Fraction of frames with faces detected
                faces_present = sum(1 for f in overlapping_frames if f.num_faces > 0)
                face_ratio = faces_present / len(overlapping_frames)
                
                # Active motion / scene transitions
                active_frames = sum(1 for f in overlapping_frames if f.visual_activity in ["moderate", "high"])
                activity_ratio = active_frames / len(overlapping_frames)

                visual_score = 0.30 + (0.40 * face_ratio) + (0.30 * activity_ratio)
                if face_ratio > 0.50:
                    categories.add("reaction")
        visual_score = min(1.0, visual_score)

        # 4. Context Completeness (length & punctuation termination)
        context_score = 0.60
        if payoff.strip().endswith((".", "!", "?")):
            context_score += 0.25
        if window.duration >= 20.0:
            context_score += 0.15
        context_score = min(1.0, context_score)

        # 5. Composite Social Potential Score
        social_potential = (
            (hook_score * 0.25) +
            (max(humor_score, surprise_score, emotion_score) * 0.25) +
            (visual_score * 0.20) +
            (audio_energy * 0.15) +
            (context_score * 0.15)
        )
        social_potential = round(min(1.0, max(0.10, social_potential)), 3)

        if not categories:
            categories.add("insightful")
            categories.add("relatable")

        # Synthesize explanatory reason
        top_cats = ", ".join(sorted(categories))
        reason = (
            f"Moment demonstrates strong hook ({hook_score:.2f}) and {top_cats} characteristics, "
            f"backed by positive visual presence ({visual_score:.2f}) and consistent audio dynamics ({audio_energy:.2f})."
        )

        scores = CandidateScores(
            hook_strength=round(hook_score, 2),
            humor=round(humor_score, 2),
            surprise=round(surprise_score, 2),
            emotion=round(emotion_score, 2),
            visual_interest=round(visual_score, 2),
            context_completeness=round(context_score, 2),
            social_potential=social_potential,
        )

        return scores, sorted(list(categories)), reason
