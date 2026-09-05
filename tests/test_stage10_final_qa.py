"""Comprehensive tests for Stage 10: Final Multimodal QA Agent."""

import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import pytest

from backend.config.settings import PipelineSettings
from backend.models.clip import ClipSpecification, SelectedClipsReport
from backend.models.metadata import ClipSocialMetadata, PlatformMetadata
from backend.models.qa import (
    FinalClipQAResult,
    FinalProjectQAReport,
    MultimodalQAChecks,
    RepairAction,
)
from backend.models.transcript import TranscriptResult, TranscriptSegment, WordTimestamp
from backend.pipeline.workspace import WorkspaceManager
from backend.qa.multimodal_qa_agent import MultimodalQAAgent


@pytest.fixture
def mock_complete_clip_workspace(tmp_path: Path):
    """Creates a mock workspace with rendered vertical clip, captions, thumbnail, and social metadata."""
    workspace = WorkspaceManager.create_workspace(tmp_path)

    # 1. Create a dummy vertical 9:16 video (1080x1920, 30fps, 3s)
    cat_dir = workspace.captioned_clips / "Humor"
    cat_dir.mkdir(parents=True, exist_ok=True)
    video_path = cat_dir / "funny_001.mp4"

    # Use FFmpeg to generate compliant 1080x1920 vertical video with audio stream
    import subprocess
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", "testsrc=duration=3:size=1080x1920:rate=30",
        "-f", "lavfi",
        "-i", "sine=frequency=440:duration=3",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(video_path),
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    # 2. Create mock ASS and SRT subtitle files
    ass_path = workspace.captions_dir / "funny_001.ass"
    ass_path.write_text(
        "[Script Info]\nTitle: Test\n\n[V4+ Styles]\nFormat: Name, MarginV\nStyle: Default,320\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\nDialogue: 0,0:00:00.00,0:00:03.00,Default,,0,0,320,,Hello world funniest clip!\n",
        encoding="utf-8"
    )
    srt_path = workspace.captions_dir / "funny_001.srt"
    srt_path.write_text("1\n00:00:00,000 --> 00:00:03,000\nHello world funniest clip!\n", encoding="utf-8")

    # 3. Create mock 1080x1920 thumbnail with varied content
    thumb_path = workspace.thumbnails_dir / "funny_001.jpg"
    thumb_arr = np.zeros((1920, 1080, 3), dtype=np.uint8)
    cv2.circle(thumb_arr, (540, 960), 300, (0, 255, 200), -1)
    cv2.putText(thumb_arr, "HOOK TEXT", (200, 400), cv2.FONT_HERSHEY_SIMPLEX, 3.0, (255, 255, 255), 4)
    cv2.imwrite(str(thumb_path), thumb_arr)

    # 4. Create mock social metadata package
    meta_path = workspace.metadata_dir / "funny_001.json"
    meta_obj = ClipSocialMetadata(
        clip_id="funny_001",
        category="Humor",
        primary_title="The Funniest Gaming Moment Ever",
        hook="You will not believe what just happened",
        payoff="He completely failed the jump!",
        summary="Funniest gaming fail recorded live.",
        thumbnail_path=str(thumb_path),
        hashtags=["#gaming", "#humor", "#funny"],
        keywords=["game", "comedy", "epic fail"],
        platforms={
            "youtube_shorts": PlatformMetadata(
                title="The Funniest Gaming Moment #Shorts",
                caption="Watch until the end!",
                description="Funniest gaming fail recorded live.",
                hashtags=["#Shorts", "#gaming"],
                keywords=["gaming", "shorts"],
                cta="Subscribe for more!",
            ),
            "instagram_reels": PlatformMetadata(
                title="The Funniest Gaming Moment",
                caption="Tag a friend who would do this!",
                description="",
                hashtags=["#reels", "#gamingreels"],
                keywords=["reels"],
                cta="Follow for more!",
            ),
            "tiktok": PlatformMetadata(
                title="The Funniest Gaming Moment",
                caption="Wait for the ending! 😂 #fyp",
                description="",
                hashtags=["#fyp", "#viral"],
                keywords=["fyp"],
                cta="Follow for part 2!",
            ),
            "facebook_reels": PlatformMetadata(
                title="The Funniest Gaming Moment",
                caption="Can you believe this happened?",
                description="",
                hashtags=["#reels", "#funny"],
                keywords=["reels"],
                cta="Share with your friends!",
            ),
        }
    )
    meta_path.write_text(meta_obj.model_dump_json(indent=4), encoding="utf-8")

    # 5. Clip specification
    clip_spec = ClipSpecification(
        clip_id="funny_001",
        candidate_id="cand_001",
        start_time=10.0,
        end_time=13.0,
        duration=3.0,
        category="Humor",
        categories=["Humor", "Gaming"],
        score=0.95,
        reason="Peak viral comedy",
        hook="You will not believe what just happened",
        payoff="He completely failed the jump!",
        transcript="Hello world funniest clip! You will not believe what just happened.",
    )

    selected_report = SelectedClipsReport(
        total_selected=1,
        clips=[clip_spec],
    )

    # 6. Transcript with aligned word timestamps
    transcript = TranscriptResult(
        language="en",
        duration=60.0,
        text="Hello world funniest clip!",
        segments=[
            TranscriptSegment(
                id=0,
                start=10.0,
                end=13.0,
                text="Hello world funniest clip!",
                words=[
                    WordTimestamp(word="Hello", start=10.0, end=10.5),
                    WordTimestamp(word="world", start=10.6, end=11.2),
                    WordTimestamp(word="funniest", start=11.3, end=12.1),
                    WordTimestamp(word="clip", start=12.2, end=12.9),
                ]
            )
        ]
    )

    return workspace, selected_report, transcript, video_path


def test_final_qa_passing_evaluation_and_promotion(mock_complete_clip_workspace):
    """Verifies that a fully rendered, compliant clip passes final QA and is promoted to final/."""
    workspace, selected_report, transcript, video_path = mock_complete_clip_workspace

    # Inspector requires video duration threshold allowance for 3.0s clip
    settings = PipelineSettings(
        min_video_duration=0.5,
        qa_min_overall_score=0.70,
        qa_promote_passing_to_final=True,
    )
    qa_agent = MultimodalQAAgent(settings=settings)

    clip_spec = selected_report.clips[0]
    result = qa_agent.evaluate_clip(clip_spec, workspace, transcript)

    assert isinstance(result, FinalClipQAResult)
    assert result.clip_id == "funny_001"
    assert result.category == "Humor"
    assert result.passed is True
    assert result.overall_score >= 0.70

    # Verify promoted deliverables in final/Humor/
    final_humor_dir = workspace.final_dir / "Humor"
    assert final_humor_dir.exists()
    assert (final_humor_dir / "funny_001.mp4").exists()
    assert (final_humor_dir / "funny_001.jpg").exists()
    assert (final_humor_dir / "funny_001.json").exists()


def test_final_qa_abrupt_cut_detection_and_retrim_recommendation(mock_complete_clip_workspace):
    """Verifies that starting mid-word triggers an abrupt start issue and a RETRIM recommendation."""
    workspace, selected_report, transcript, video_path = mock_complete_clip_workspace

    # Intentionally misalign clip start into the middle of the word 'Hello' (which runs 10.0 to 10.5)
    misaligned_clip = selected_report.clips[0].model_copy(update={"start_time": 10.25})

    settings = PipelineSettings(
        min_video_duration=0.5,
        qa_abrupt_cut_tolerance_sec=0.10,
    )
    qa_agent = MultimodalQAAgent(settings=settings)

    result = qa_agent.evaluate_clip(misaligned_clip, workspace, transcript)

    assert result.checks.no_abrupt_start is False
    assert any("Abrupt start" in issue for issue in result.issues)

    # Must contain a structured RETRIM repair recommendation
    retrim_recs = [r for r in result.recommendations if r.action == RepairAction.RETRIM]
    assert len(retrim_recs) == 1
    assert retrim_recs[0].suggested_start is not None
    assert retrim_recs[0].suggested_start <= 10.0  # Expands backward before 'Hello'


def test_final_qa_missing_artifact_detection_and_regeneration(mock_complete_clip_workspace):
    """Verifies that missing companion artifacts (e.g. missing thumbnail) trigger a REGENERATE recommendation."""
    workspace, selected_report, transcript, video_path = mock_complete_clip_workspace

    # Remove thumbnail
    thumb_file = workspace.thumbnails_dir / "funny_001.jpg"
    if thumb_file.exists():
        thumb_file.unlink()

    settings = PipelineSettings(min_video_duration=0.5)
    qa_agent = MultimodalQAAgent(settings=settings)

    result = qa_agent.evaluate_clip(selected_report.clips[0], workspace, transcript)

    assert result.checks.thumbnail_valid is False
    assert result.passed is False
    assert any("Thumbnail missing" in issue for issue in result.issues)

    # Must recommend REGENERATE
    regen_recs = [r for r in result.recommendations if r.action == RepairAction.REGENERATE]
    assert len(regen_recs) >= 1


def test_final_qa_project_report_and_json_serialization(mock_complete_clip_workspace):
    """Verifies batch clip evaluation and saving to qa/final_report.json."""
    workspace, selected_report, transcript, video_path = mock_complete_clip_workspace

    settings = PipelineSettings(min_video_duration=0.5, qa_min_overall_score=0.70)
    qa_agent = MultimodalQAAgent(settings=settings)

    proj_report = qa_agent.evaluate_all_clips(selected_report, workspace, transcript)
    assert isinstance(proj_report, FinalProjectQAReport)
    assert proj_report.total_clips == 1
    assert proj_report.passed_clips == 1
    assert proj_report.all_passed is True

    # Save via WorkspaceManager
    report_file = WorkspaceManager.save_final_qa_report(proj_report, workspace)
    assert report_file.exists()
    assert report_file.name == "final_report.json"

    with open(report_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["total_clips"] == 1
    assert loaded["all_passed"] is True
    assert loaded["clips"][0]["clip_id"] == "funny_001"
    assert loaded["clips"][0]["checks"]["technical_valid"] is True
