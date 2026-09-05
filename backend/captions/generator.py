"""Subtitle generator module.

Extracts speech within clip boundaries, re-bases timestamps, breaks text into
bite-sized mobile chunks (2-5 words), applies keyword emphasis, and formats both
standard SubRip (.srt) and styled Advanced SubStation Alpha (.ass) files.
"""

from pathlib import Path
import re
from typing import List, Optional, Tuple

from backend.config.settings import PipelineSettings, get_settings
from backend.models.caption import CaptionChunk, CaptionWord
from backend.models.clip import ClipSpecification
from backend.models.transcript import TranscriptResult, TranscriptSegment, WordTimestamp
from backend.utils.logger import get_logger

logger = get_logger("caption_generator")


class CaptionGenerator:
    """Generates timed subtitles (.srt and .ass) for short-form mobile videos."""

    def __init__(self, settings: Optional[PipelineSettings] = None):
        self.settings = settings or get_settings()

    def generate_chunks_for_clip(
        self,
        clip_spec: ClipSpecification,
        transcript: TranscriptResult,
    ) -> List[CaptionChunk]:
        """Extract and chunk spoken text within the clip's time boundary.

        Timestamps are re-based to clip time:
            t_local = max(0.0, min(clip_duration, t_global - clip.start_time))

        Args:
            clip_spec: Clip specification with start/end boundaries.
            transcript: Full transcript with word or segment timestamps.

        Returns:
            List of CaptionChunk objects.
        """
        clip_start = clip_spec.start_time
        clip_end = clip_spec.end_time
        clip_duration = clip_spec.duration if hasattr(clip_spec, "duration") else (clip_end - clip_start)

        # Collect relevant words within boundaries
        raw_words: List[Tuple[float, float, str]] = []

        # Check if any segment has word-level timestamps
        has_words = any(len(s.words) > 0 for s in transcript.segments)

        if has_words:
            for seg in transcript.segments:
                for w in seg.words:
                    if w.end > clip_start and w.start < clip_end:
                        raw_words.append((w.start, w.end, w.word.strip()))
        else:
            # Fallback: estimate word timings evenly across segment
            for seg in transcript.segments:
                if seg.end > clip_start and seg.start < clip_end:
                    words = seg.text.strip().split()
                    if not words:
                        continue
                    seg_dur = max(0.2, seg.end - seg.start)
                    word_dur = seg_dur / len(words)
                    for i, wd in enumerate(words):
                        w_start = seg.start + (i * word_dur)
                        w_end = w_start + word_dur
                        if w_end > clip_start and w_start < clip_end:
                            raw_words.append((w_start, w_end, wd))

        if not raw_words:
            # If transcript had no words in range, use clip transcript or hook
            text = getattr(clip_spec, "transcript", "") or clip_spec.hook
            words = text.split() if text else ["..."]
            dur_per_word = clip_duration / max(1, len(words))
            for i, wd in enumerate(words):
                raw_words.append((clip_start + (i * dur_per_word), clip_start + ((i + 1) * dur_per_word), wd))

        # Re-base to local clip timestamps
        local_words: List[CaptionWord] = []
        # Key high-energy / emphasis words to highlight
        emphasis_pattern = re.compile(
            r"\b(crazy|insane|never|always|best|worst|omg|wow|literally|huge|secret|stop|look|wait|truth|unbelievable|funny|hilarious|watch|now|epic)\b",
            re.IGNORECASE,
        )

        for w_start, w_end, text in raw_words:
            loc_start = max(0.0, round(w_start - clip_start, 3))
            loc_end = min(clip_duration, round(w_end - clip_start, 3))
            if loc_end <= loc_start:
                loc_end = loc_start + 0.2

            is_highlighted = bool(emphasis_pattern.search(text))
            local_words.append(
                CaptionWord(
                    word=text,
                    start=loc_start,
                    end=loc_end,
                    is_highlighted=is_highlighted,
                )
            )

        # Chunk into bite-sized units of 2 to 4 words
        chunks: List[CaptionChunk] = []
        max_words = self.settings.caption_max_words_per_chunk
        max_chars = self.settings.caption_max_chars_per_line

        curr_words: List[CaptionWord] = []
        for word_obj in local_words:
            curr_words.append(word_obj)
            chunk_text = " ".join(w.word for w in curr_words)

            if len(curr_words) >= max_words or len(chunk_text) >= max_chars or word_obj.word.endswith((".", "!", "?", "—")):
                chunk_start = curr_words[0].start
                chunk_end = curr_words[-1].end
                chunks.append(
                    CaptionChunk(
                        start=chunk_start,
                        end=chunk_end,
                        text=chunk_text,
                        words=list(curr_words),
                    )
                )
                curr_words = []

        if curr_words:
            chunks.append(
                CaptionChunk(
                    start=curr_words[0].start,
                    end=curr_words[-1].end,
                    text=" ".join(w.word for w in curr_words),
                    words=list(curr_words),
                )
            )

        return chunks

    def format_srt(self, chunks: List[CaptionChunk]) -> str:
        """Format chunks into SubRip (.srt) subtitle standard."""
        lines: List[str] = []

        def format_timestamp(sec: float) -> str:
            hrs = int(sec // 3600)
            mins = int((sec % 3600) // 60)
            secs = int(sec % 60)
            millis = int(round((sec - int(sec)) * 1000))
            return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"

        for idx, chunk in enumerate(chunks, start=1):
            t_start = format_timestamp(chunk.start)
            t_end = format_timestamp(chunk.end)
            lines.append(str(idx))
            lines.append(f"{t_start} --> {t_end}")
            lines.append(chunk.text)
            lines.append("")

        return "\n".join(lines)

    def format_ass(self, chunks: List[CaptionChunk], style: Optional[str] = None) -> str:
        """Format chunks into styled Advanced SubStation Alpha (.ass) for burning."""
        chosen_style = style or self.settings.caption_style

        def format_ass_time(sec: float) -> str:
            hrs = int(sec // 3600)
            mins = int((sec % 3600) // 60)
            secs = int(sec % 60)
            centis = int(round((sec - int(sec)) * 100))
            return f"{hrs}:{mins:02d}:{secs:02d}.{centis:02d}"

        font = self.settings.caption_font_name
        font_size = self.settings.caption_font_size
        primary = self.settings.caption_primary_color
        highlight = self.settings.caption_highlight_color
        outline = self.settings.caption_outline_color

        # ASS Header & Styles
        # Alignment=2 is Bottom-Center. MarginV=300 places text in lower third above TikTok/Reels UI.
        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{font_size * 4},{primary},&H000000FF,{outline},&H80000000,-1,0,0,0,100,100,0,0,1,6,3,2,60,60,320,1
Style: Highlight,{font},{font_size * 4},{highlight},&H000000FF,{outline},&H80000000,-1,0,0,0,100,100,0,0,1,6,3,2,60,60,320,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events: List[str] = []

        for chunk in chunks:
            t_start = format_ass_time(chunk.start)
            t_end = format_ass_time(chunk.end)

            if chosen_style == "bold_highlight":
                # Highlight words marked as important
                formatted_words: List[str] = []
                for w in chunk.words:
                    if w.is_highlighted:
                        formatted_words.append(f"{{\\c{highlight}}}{w.word}{{\\c{primary}}}")
                    else:
                        formatted_words.append(w.word)
                text = " ".join(formatted_words)
            elif chosen_style == "karaoke":
                # Basic karaoke tags
                parts: List[str] = []
                for w in chunk.words:
                    dur_cs = max(10, int(round((w.end - w.start) * 100)))
                    parts.append(f"{{\\k{dur_cs}}}{w.word}")
                text = " ".join(parts)
            else:
                # Clean style
                text = chunk.text

            events.append(f"Dialogue: 0,{t_start},{t_end},Default,,0,0,0,,{text}")

        return header + "\n".join(events) + "\n"

    def generate_captions_for_clip(
        self,
        clip_spec: ClipSpecification,
        transcript: TranscriptResult,
        srt_output_path: Path,
        ass_output_path: Path,
        style: Optional[str] = None,
    ) -> List[CaptionChunk]:
        """Generate and save both .srt and .ass caption files for a clip."""
        chunks = self.generate_chunks_for_clip(clip_spec, transcript)

        srt_output_path.parent.mkdir(parents=True, exist_ok=True)
        ass_output_path.parent.mkdir(parents=True, exist_ok=True)

        srt_content = self.format_srt(chunks)
        ass_content = self.format_ass(chunks, style=style)

        srt_output_path.write_text(srt_content, encoding="utf-8")
        ass_output_path.write_text(ass_content, encoding="utf-8")

        logger.info(
            f"Generated captions for {clip_spec.clip_id}: {len(chunks)} chunks -> "
            f"{srt_output_path.name}, {ass_output_path.name}"
        )
        return chunks
