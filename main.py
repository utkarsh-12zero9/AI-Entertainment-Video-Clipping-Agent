#!/usr/bin/env python3
"""CLI Entrypoint for AI Entertainment Video Clipping Agent."""

import argparse
import json
import sys
from pathlib import Path

from backend.analyzers.frame_sampler import FrameSampler
from backend.analyzers.scene_detector import SceneDetector
from backend.analyzers.visual_analyzer import VisualAnalyzer
from backend.audio.extractor import AudioExtractor
from backend.clip_detection.detector import EntertainmentMomentDetector
from backend.config.settings import PipelineSettings
from backend.captions.burner import CaptionBurner
from backend.metadata.social_metadata_generator import SocialMetadataGenerator
from backend.metadata.thumbnail_generator import ThumbnailGenerator
from backend.models.candidate import CandidateReport
from backend.models.clip import SelectedClipsReport
from backend.models.metadata import ProjectMetadataReport
from backend.models.transcript import TranscriptResult
from backend.models.vision import VisualAnalysisResult
from backend.pipeline.workspace import WorkspaceManager
from backend.qa.clip_validator import ClipValidator
from backend.scoring.ranker import ClipRanker
from backend.transcription.whisper_local import LocalWhisperTranscriber
from backend.utils.errors import VideoPipelineError
from backend.utils.logger import logger, setup_logger
from backend.video.clip_editor import ClipEditor
from backend.video.clip_extractor import RawClipExtractor
from backend.video.inspector import VideoInspector


def handle_analyze_video(args: argparse.Namespace) -> int:
    """Executes video inspection and prints metadata."""
    video_path = Path(args.input).resolve()
    settings = PipelineSettings(
        min_video_duration=args.min_duration,
        require_audio=not args.allow_no_audio
    )
    inspector = VideoInspector(settings=settings)

    try:
        metadata = inspector.inspect(video_path)
        
        if args.json:
            print(metadata.model_dump_json(indent=2))
        else:
            print("\n" + "=" * 50)
            print("VIDEO METADATA ANALYSIS")
            print("=" * 50)
            for k, v in metadata.model_dump().items():
                print(f"  {k:<20}: {v}")
            print("=" * 50 + "\n")
        return 0
    except VideoPipelineError as e:
        logger.error(f"Validation failed: {e}")
        return 1
    except Exception as e:
        logger.exception(f"Unexpected error analyzing video: {e}")
        return 2


def handle_extract_audio(args: argparse.Namespace) -> int:
    """Extracts 16kHz mono WAV from video file."""
    video_path = Path(args.input).resolve()
    output_wav = Path(args.output).resolve()

    settings = PipelineSettings()
    extractor = AudioExtractor(settings=settings)

    try:
        extractor.extract(video_path, output_wav)
        print(f"Audio extracted successfully: {output_wav}")
        return 0
    except VideoPipelineError as e:
        logger.error(f"Audio extraction failed: {e}")
        return 1
    except Exception as e:
        logger.exception(f"Unexpected error extracting audio: {e}")
        return 2


def handle_transcribe_video(args: argparse.Namespace) -> int:
    """Transcribes video or audio file using free local Whisper model."""
    input_path = Path(args.input).resolve()
    output_dir = Path(args.output).resolve() if args.output else None

    settings = PipelineSettings(
        whisper_model_name=args.model,
        whisper_device=args.device
    )

    try:
        if input_path.suffix.lower() in [".mp4", ".mov", ".mkv", ".avi", ".webm"]:
            extractor = AudioExtractor(settings=settings)
            temp_wav = input_path.with_suffix(".temp.wav")
            audio_path = extractor.extract(input_path, temp_wav)
        else:
            temp_wav = None
            audio_path = input_path

        transcriber = LocalWhisperTranscriber(settings=settings)
        transcript = transcriber.transcribe(audio_path)

        if temp_wav and temp_wav.exists():
            temp_wav.unlink()

        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            json_file = output_dir / "transcript.json"
            txt_file = output_dir / "transcript.txt"
            json_file.write_text(transcript.model_dump_json(indent=4), encoding="utf-8")
            txt_file.write_text(transcript.text, encoding="utf-8")
            print(f"Transcript saved to: {json_file} and {txt_file}")
        else:
            print("\n" + "=" * 50)
            print("TRANSCRIPTION RESULT")
            print("=" * 50)
            print(f"Language: {transcript.language}")
            print(f"Duration: {transcript.duration}s")
            print(f"Segments: {len(transcript.segments)}")
            print("-" * 50)
            print(transcript.text)
            print("=" * 50 + "\n")
        return 0
    except VideoPipelineError as e:
        logger.error(f"Transcription failed: {e}")
        return 1
    except Exception as e:
        logger.exception(f"Unexpected error during transcription: {e}")
        return 2


def handle_detect_scenes(args: argparse.Namespace) -> int:
    """Runs scene boundary detection."""
    video_path = Path(args.input).resolve()
    settings = PipelineSettings(scene_change_threshold=args.threshold)
    inspector = VideoInspector(settings=settings)
    detector = SceneDetector(settings=settings)

    try:
        metadata = inspector.inspect(video_path)
        scenes = detector.detect_scenes(video_path, metadata.duration)
        if args.output:
            out_file = Path(args.output).resolve()
            out_file.parent.mkdir(parents=True, exist_ok=True)
            data = [s.model_dump() for s in scenes]
            out_file.write_text(json.dumps(data, indent=4), encoding="utf-8")
            print(f"Scenes saved to: {out_file}")
        else:
            print(f"\nDetected {len(scenes)} scenes in {video_path.name}:")
            for s in scenes:
                print(f"  Scene #{s.scene_id}: {s.start:.2f}s -> {s.end:.2f}s (duration: {s.duration:.2f}s)")
        return 0
    except VideoPipelineError as e:
        logger.error(f"Scene detection failed: {e}")
        return 1
    except Exception as e:
        logger.exception(f"Unexpected error detecting scenes: {e}")
        return 2


def handle_sample_frames(args: argparse.Namespace) -> int:
    """Samples frames from video using specified strategy."""
    video_path = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()
    settings = PipelineSettings(
        frame_sampling_strategy=args.strategy,
        frame_sample_interval=args.interval
    )
    inspector = VideoInspector(settings=settings)
    sampler = FrameSampler(settings=settings)
    detector = SceneDetector(settings=settings)

    try:
        metadata = inspector.inspect(video_path)
        scenes = detector.detect_scenes(video_path, metadata.duration)
        frame_index = sampler.sample_frames(
            video_path=video_path,
            frames_dir=output_dir,
            duration=metadata.duration,
            scenes=scenes,
            strategy=args.strategy
        )
        print(f"Sampled {frame_index.total_frames} frames to {output_dir}")
        return 0
    except VideoPipelineError as e:
        logger.error(f"Frame sampling failed: {e}")
        return 1
    except Exception as e:
        logger.exception(f"Unexpected error sampling frames: {e}")
        return 2


def handle_detect_moments(args: argparse.Namespace) -> int:
    """Detects entertainment candidate moments for a given video project or files."""
    settings = PipelineSettings(
        min_candidate_duration=args.min_duration,
        max_candidate_duration=args.max_duration,
        min_candidate_score=args.min_score
    )
    detector = EntertainmentMomentDetector(settings=settings)

    try:
        # Load transcript
        transcript_file = Path(args.transcript).resolve()
        transcript_data = json.loads(transcript_file.read_text(encoding="utf-8"))
        transcript = TranscriptResult.model_validate(transcript_data)

        # Optional audio
        audio_file = Path(args.audio).resolve() if args.audio else None

        # Optional visual analysis
        visual_file = Path(args.visual).resolve() if args.visual else None
        visual_analysis = None
        if visual_file and visual_file.exists():
            visual_data = json.loads(visual_file.read_text(encoding="utf-8"))
            visual_analysis = VisualAnalysisResult.model_validate(visual_data)

        report = detector.detect_candidates(
            transcript=transcript,
            audio_path=audio_file,
            visual_analysis=visual_analysis,
            video_duration=transcript.duration
        )

        md_content = EntertainmentMomentDetector.generate_markdown_summary(report)

        if args.output:
            out_dir = Path(args.output).resolve()
            out_dir.mkdir(parents=True, exist_ok=True)
            json_path = out_dir / "candidates.json"
            md_path = out_dir / "candidates.md"
            json_path.write_text(report.model_dump_json(indent=4), encoding="utf-8")
            md_path.write_text(md_content, encoding="utf-8")
            print(f"Candidates saved to: {json_path} and {md_path}")
        else:
            print(md_content)

        return 0
    except VideoPipelineError as e:
        logger.error(f"Moment detection failed: {e}")
        return 1
    except Exception as e:
        logger.exception(f"Unexpected error detecting moments: {e}")
        return 2


def handle_rank_clips(args: argparse.Namespace) -> int:
    """Ranks candidates, optimizes boundaries, enforces diversity, and outputs selected_clips.json."""
    settings = PipelineSettings(
        max_clips=args.max_clips,
        min_clip_spacing_sec=args.min_spacing
    )
    ranker = ClipRanker(settings=settings)

    try:
        cand_file = Path(args.candidates).resolve()
        cand_data = json.loads(cand_file.read_text(encoding="utf-8"))
        candidate_report = CandidateReport.model_validate(cand_data)

        transcript_file = Path(args.transcript).resolve()
        transcript_data = json.loads(transcript_file.read_text(encoding="utf-8"))
        transcript = TranscriptResult.model_validate(transcript_data)

        selected_report = ranker.rank_and_select_clips(
            report=candidate_report,
            transcript=transcript,
            video_duration=transcript.duration,
            max_clips=args.max_clips
        )

        if args.output:
            out_file = Path(args.output).resolve()
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(selected_report.model_dump_json(indent=4), encoding="utf-8")
            print(f"Selected clips saved to: {out_file}")
        else:
            print("\n" + "=" * 65)
            print("SELECTED CLIPS SPECIFICATION (RANKED & BOUNDARY-OPTIMIZED)")
            print("=" * 65)
            for c in selected_report.clips:
                print(f"[{c.clip_id}] {c.start_time:.1f}s - {c.end_time:.1f}s ({c.duration:.1f}s) | Score: {c.score:.2f} | Category: #{c.category}")
                print(f"  Hook:   \"{c.hook}\"")
                print(f"  Payoff: \"{c.payoff}\"")
                print("-" * 65)
            print("=" * 65 + "\n")

        return 0
    except VideoPipelineError as e:
        logger.error(f"Clip ranking failed: {e}")
        return 1
    except Exception as e:
        logger.exception(f"Unexpected error ranking clips: {e}")
        return 2


def handle_extract_clips(args: argparse.Namespace) -> int:
    """Extracts raw candidate clips from video according to selected_clips.json."""
    video_path = Path(args.input).resolve()
    selected_file = Path(args.selected).resolve()
    output_dir = Path(args.output).resolve()

    settings = PipelineSettings(
        clip_crf=args.crf,
        clip_preset=args.preset,
        clip_audio_bitrate=args.audio_bitrate
    )
    extractor = RawClipExtractor(settings=settings)

    try:
        selected_data = json.loads(selected_file.read_text(encoding="utf-8"))
        selected_report = SelectedClipsReport.model_validate(selected_data)

        # Create temporary workspace mock pointing to output_dir
        workspace = WorkspaceManager.create_workspace(output_dir)
        extracted = extractor.extract_all_clips(video_path, selected_report, workspace)

        print("\n" + "=" * 65)
        print(f"RAW CLIP EXTRACTION SUCCESSFUL ({len(extracted)} CLIPS)")
        print("=" * 65)
        for p in extracted:
            print(f"  Extracted: {p.relative_to(workspace.root)} ({p.stat().st_size / 1024 / 1024:.2f} MB)")
        print("=" * 65 + "\n")
        return 0
    except VideoPipelineError as e:
        logger.error(f"Clip extraction failed: {e}")
        return 1
    except Exception as e:
        logger.exception(f"Unexpected error extracting clips: {e}")
        return 2


def handle_qa_clips(args: argparse.Namespace) -> int:
    """Validates extracted raw clips against specifications and audio/video QA criteria."""
    selected_file = Path(args.selected).resolve()
    project_dir = Path(args.project_dir).resolve()

    settings = PipelineSettings(
        qa_duration_tolerance_sec=args.duration_tolerance,
        qa_max_allowed_silence_sec=args.max_silence
    )
    validator = ClipValidator(settings=settings)

    try:
        selected_data = json.loads(selected_file.read_text(encoding="utf-8"))
        selected_report = SelectedClipsReport.model_validate(selected_data)
        workspace = WorkspaceManager.create_workspace(project_dir)

        qa_report = validator.validate_all_clips(selected_report, workspace)
        qa_file = WorkspaceManager.save_qa_report(qa_report, workspace)

        print("\n" + "=" * 65)
        print("AUTOMATED CLIP QUALITY ASSURANCE (QA) REPORT")
        print("=" * 65)
        print(f"Total Clips Tested:  {qa_report.total_clips}")
        print(f"Clips Passed:        {qa_report.passed_clips}")
        print(f"Clips Failed:        {qa_report.failed_clips}")
        print(f"QA Status:           {'PASSED' if qa_report.all_passed else 'FAILED'}")
        print(f"QA Report File:      {qa_file}")
        print("-" * 65)
        for r in qa_report.clip_results:
            status = "PASS" if r.passed else "FAIL"
            print(f"[{status}] Clip {r.clip_id}: {r.actual_duration:.2f}s (exp: {r.expected_duration:.2f}s, diff: {r.duration_diff:.2f}s)")
            if r.issues:
                for issue in r.issues:
                    print(f"       ! {issue}")
        print("=" * 65 + "\n")

        return 0 if qa_report.all_passed else 1
    except VideoPipelineError as e:
        logger.error(f"QA verification failed: {e}")
        return 1
    except Exception as e:
        logger.exception(f"Unexpected error running QA: {e}")
        return 2


def handle_edit_clips(args: argparse.Namespace) -> int:
    """Transforms raw clips into 9:16 vertical social media clips."""
    selected_file = Path(args.selected).resolve()
    project_dir = Path(args.project_dir).resolve()

    settings = PipelineSettings(
        reframing_strategy=args.strategy,
        enable_visual_enhancements=not args.no_enhancements,
        audio_loudnorm_target=args.loudness
    )
    editor = ClipEditor(settings=settings)

    try:
        selected_data = json.loads(selected_file.read_text(encoding="utf-8"))
        selected_report = SelectedClipsReport.model_validate(selected_data)
        workspace = WorkspaceManager.create_workspace(project_dir)

        edit_report = editor.edit_all_clips(selected_report, workspace, strategy=args.strategy)
        report_file = WorkspaceManager.save_edit_report(edit_report, workspace)

        print("\n" + "=" * 65)
        print(f"VERTICAL SOCIAL MEDIA EDITING COMPLETE ({len(edit_report.clips)} CLIPS)")
        print("=" * 65)
        print(f"Target Format:       {edit_report.target_resolution} ({edit_report.target_aspect_ratio})")
        print(f"Reframing Strategy:  {settings.reframing_strategy}")
        print(f"Edit Report File:    {report_file}")
        print("-" * 65)
        for c in edit_report.clips:
            print(f"[{c.clip_id}] {c.resolution} ({c.aspect_ratio}) | Crop: X={c.crop.x} ({c.crop.strategy_used})")
            print(f"  Saved to: {Path(c.edited_clip_path).relative_to(workspace.root)} ({c.file_size_bytes / 1024 / 1024:.2f} MB)")
        print("=" * 65 + "\n")

        return 0
    except VideoPipelineError as e:
        logger.error(f"Clip editing failed: {e}")
        return 1
    except Exception as e:
        logger.exception(f"Unexpected error editing clips: {e}")
        return 2


def handle_generate_captions(args: argparse.Namespace) -> int:
    """Generates synchronized subtitles and burns them onto vertical clips."""
    selected_file = Path(args.selected).resolve()
    transcript_file = Path(args.transcript).resolve()
    project_dir = Path(args.project_dir).resolve()

    settings = PipelineSettings(
        caption_style=args.style
    )
    burner = CaptionBurner(settings=settings)

    try:
        selected_data = json.loads(selected_file.read_text(encoding="utf-8"))
        selected_report = SelectedClipsReport.model_validate(selected_data)

        transcript_data = json.loads(transcript_file.read_text(encoding="utf-8"))
        transcript = TranscriptResult.model_validate(transcript_data)

        workspace = WorkspaceManager.create_workspace(project_dir)

        caption_report = burner.process_all_clips(selected_report, transcript, workspace, style=args.style)
        report_file = WorkspaceManager.save_caption_report(caption_report, workspace)

        print("\n" + "=" * 65)
        print(f"CAPTION GENERATION & RENDERING COMPLETE ({len(caption_report.clips)} CLIPS)")
        print("=" * 65)
        print(f"Caption Style:       {caption_report.caption_style}")
        print(f"Caption Report File: {report_file}")
        print("-" * 65)
        for c in caption_report.clips:
            print(f"[{c.clip_id}] ({c.category}) | {c.total_chunks} caption chunks")
            print(f"  SRT:   {Path(c.srt_path).relative_to(workspace.root)}")
            print(f"  ASS:   {Path(c.ass_path).relative_to(workspace.root)}")
            print(f"  Video: {Path(c.captioned_clip_path).relative_to(workspace.root)}")
        print("=" * 65 + "\n")

        return 0
    except VideoPipelineError as e:
        logger.error(f"Caption generation failed: {e}")
        return 1
    except Exception as e:
        logger.exception(f"Unexpected error generating captions: {e}")
        return 2


def handle_generate_metadata(args: argparse.Namespace) -> int:
    """Generates AI thumbnails and social metadata packages for clips."""
    project_dir = Path(args.project_dir).resolve()
    selected_file = Path(args.selected).resolve()

    if not project_dir.exists():
        logger.error(f"Project directory not found: {project_dir}")
        return 1
    if not selected_file.exists():
        logger.error(f"Selected clips file not found: {selected_file}")
        return 1

    settings = PipelineSettings(
        thumbnail_overlay_text=not args.no_overlay,
    )
    thumb_gen = ThumbnailGenerator(settings=settings)
    meta_gen = SocialMetadataGenerator(settings=settings)

    try:
        selected_data = json.loads(selected_file.read_text(encoding="utf-8"))
        selected_report = SelectedClipsReport.model_validate(selected_data)
        workspace = WorkspaceManager.create_workspace(project_dir)

        # 1. Generate thumbnails
        thumb_map = thumb_gen.generate_all_thumbnails(selected_report, workspace)

        # 2. Generate multi-platform social metadata
        metadata_map = meta_gen.generate_all_metadata(selected_report, workspace, thumb_map)

        # 3. Save each clip's metadata JSON and overall report
        for clip_id, meta in metadata_map.items():
            WorkspaceManager.save_social_metadata(meta, workspace)

        from datetime import datetime, timezone
        meta_report = ProjectMetadataReport(
            project_id=workspace.project_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            total_clips=len(metadata_map),
            clips=list(metadata_map.values()),
        )
        report_file = WorkspaceManager.save_metadata_report(meta_report, workspace)

        print("\n" + "=" * 65)
        print(f"THUMBNAIL & SOCIAL METADATA GENERATION COMPLETE ({len(metadata_map)} CLIPS)")
        print("=" * 65)
        print(f"Metadata Report:   {report_file}")
        print("-" * 65)
        for clip_id, meta in metadata_map.items():
            print(f"[{clip_id}]")
            print(f"  Thumbnail:     {Path(meta.thumbnail_path).relative_to(workspace.root) if meta.thumbnail_path else 'N/A'}")
            print(f"  Primary Title: {meta.primary_title}")
            for plat, p_meta in meta.platforms.items():
                print(f"  -> {plat:<15}: {p_meta.title[:45]}... ({len(p_meta.hashtags)} tags)")
        print("=" * 65 + "\n")

        return 0
    except VideoPipelineError as e:
        logger.error(f"Metadata generation failed: {e}")
        return 1
    except Exception as e:
        logger.exception(f"Unexpected error generating metadata: {e}")
        return 2


def handle_process_video(args: argparse.Namespace) -> int:
    """Executes full multi-stage pipeline (Stage 1 to Stage 8)."""
    video_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    settings = PipelineSettings(
        min_video_duration=args.min_duration,
        require_audio=not args.allow_no_audio,
        whisper_model_name=args.model,
        whisper_device=args.device,
        frame_sampling_strategy=args.strategy,
        frame_sample_interval=args.interval,
        min_candidate_duration=args.min_candidate_duration,
        max_candidate_duration=args.max_candidate_duration,
        min_candidate_score=args.min_candidate_score,
        max_clips=args.max_clips,
        min_clip_spacing_sec=args.min_spacing
    )

    # Initialize workspace
    workspace = WorkspaceManager.create_workspace(output_path)
    
    # Configure logging to also write into project log file
    setup_logger(log_file=workspace.log_file)

    logger.info(f"Starting processing pipeline for: {video_path}")
    inspector = VideoInspector(settings=settings)

    try:
        # --- Stage 1: Video Ingestion & Metadata ---
        metadata = inspector.inspect(video_path)
        copied_video = WorkspaceManager.copy_source_video(video_path, workspace)
        meta_file = WorkspaceManager.save_metadata(metadata, workspace)

        # --- Stage 2: Audio Extraction & Transcription ---
        audio_file = workspace.audio_dir / "audio.wav"
        extractor = AudioExtractor(settings=settings)
        extractor.extract(copied_video, audio_file)

        transcriber = LocalWhisperTranscriber(settings=settings)
        transcript = transcriber.transcribe(audio_file)
        json_path, txt_path = WorkspaceManager.save_transcript(transcript, workspace)

        # --- Stage 3: Visual Frame Sampling & Content Analysis ---
        detector = SceneDetector(settings=settings)
        scenes = detector.detect_scenes(copied_video, metadata.duration)
        scenes_file = WorkspaceManager.save_scenes(scenes, workspace)

        sampler = FrameSampler(settings=settings)
        frame_index = sampler.sample_frames(
            video_path=copied_video,
            frames_dir=workspace.frames_dir,
            duration=metadata.duration,
            scenes=scenes,
            strategy=settings.frame_sampling_strategy
        )

        visual_analyzer = VisualAnalyzer(settings=settings)
        visual_report = visual_analyzer.analyze_sampled_frames(
            frames_dir=workspace.frames_dir,
            frame_index=frame_index,
            scenes=scenes,
            video_duration=metadata.duration
        )
        visual_analysis_file = WorkspaceManager.save_visual_analysis(visual_report, workspace)

        # --- Stage 4: Multimodal Entertainment Moment Detection ---
        moment_detector = EntertainmentMomentDetector(settings=settings)
        candidate_report = moment_detector.detect_candidates(
            transcript=transcript,
            audio_path=audio_file,
            visual_analysis=visual_report,
            video_duration=metadata.duration
        )
        md_summary = EntertainmentMomentDetector.generate_markdown_summary(candidate_report)
        cand_json, cand_md = WorkspaceManager.save_candidates(candidate_report, md_summary, workspace)

        # --- Stage 5: Candidate Ranking & Boundary Optimization ---
        ranker = ClipRanker(settings=settings)
        selected_report = ranker.rank_and_select_clips(
            report=candidate_report,
            transcript=transcript,
            video_duration=metadata.duration,
            max_clips=settings.max_clips
        )
        selected_file = WorkspaceManager.save_selected_clips(selected_report, workspace)

        # --- Stage 6: Raw Clip Extraction & Automated QA Validation ---
        clip_extractor = RawClipExtractor(settings=settings)
        extracted_clips = clip_extractor.extract_all_clips(copied_video, selected_report, workspace)

        qa_validator = ClipValidator(settings=settings)
        qa_report = qa_validator.validate_all_clips(selected_report, workspace)
        qa_file = WorkspaceManager.save_qa_report(qa_report, workspace)

        # --- Stage 7: Vertical Social Media Editing ---
        clip_editor = ClipEditor(settings=settings)
        edit_report = clip_editor.edit_all_clips(selected_report, workspace, strategy=settings.reframing_strategy)
        edit_report_file = WorkspaceManager.save_edit_report(edit_report, workspace)

        # --- Stage 8: Caption Generation & Rendering ---
        caption_burner = CaptionBurner(settings=settings)
        caption_report = caption_burner.process_all_clips(selected_report, transcript, workspace, style=settings.caption_style)
        caption_report_file = WorkspaceManager.save_caption_report(caption_report, workspace)

        # --- Stage 9: Thumbnail Generation & Multi-Platform Social Metadata ---
        thumb_gen = ThumbnailGenerator(settings=settings)
        meta_gen = SocialMetadataGenerator(settings=settings)
        thumb_map = thumb_gen.generate_all_thumbnails(selected_report, workspace)
        metadata_map = meta_gen.generate_all_metadata(selected_report, workspace, thumb_map)
        for clip_id, meta in metadata_map.items():
            WorkspaceManager.save_social_metadata(meta, workspace)
        from datetime import datetime, timezone
        meta_report = ProjectMetadataReport(
            project_id=workspace.project_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            total_clips=len(metadata_map),
            clips=list(metadata_map.values()),
        )
        meta_report_file = WorkspaceManager.save_metadata_report(meta_report, workspace)

        logger.info("Stage 1 through 9 pipeline completed successfully.")

        print("\n" + "=" * 65)
        print("PIPELINE EXECUTION SUCCESSFUL (STAGES 1, 2, 3, 4, 5, 6, 7, 8 & 9)")
        print("=" * 65)
        print(f"Project Workspace:    {workspace.root}")
        print(f"Metadata File:        {meta_file}")
        print(f"Audio File:           {audio_file}")
        print(f"Transcript JSON:      {json_path}")
        print(f"Scenes JSON:          {scenes_file}")
        print(f"Frames Sampled:       {frame_index.total_frames} (in {workspace.frames_dir})")
        print(f"Visual Analysis JSON: {visual_analysis_file}")
        print(f"Candidate JSON:       {cand_json}")
        print(f"Selected Clips JSON:  {selected_file}")
        print(f"Raw Clips Extracted:  {len(extracted_clips)} (in {workspace.raw_clips})")
        print(f"QA Validation Report: {qa_file}")
        print(f"QA Overall Status:    {'PASSED' if qa_report.all_passed else 'WARNING / ISSUES DETECTED'}")
        print(f"Edited 9:16 Clips:    {len(edit_report.clips)} (in {workspace.edited_clips})")
        print(f"Captioned Clips:      {len(caption_report.clips)} (in {workspace.captioned_clips})")
        print(f"Caption Report File:  {caption_report_file}")
        print(f"Thumbnails Created:   {len(thumb_map)} (in {workspace.thumbnails_dir})")
        print(f"Social Metadata:      {len(metadata_map)} packages (in {workspace.metadata_dir})")
        print(f"Metadata Report:      {meta_report_file}")
        print(f"Duration:             {metadata.duration}s")
        print(f"Original Resolution:  {metadata.width}x{metadata.height} ({metadata.aspect_ratio})")
        print(f"Vertical Target:      {settings.target_vertical_width}x{settings.target_vertical_height} (9:16)")
        print(f"Candidate Moments:    {candidate_report.total_candidates}")
        print(f"Final Selected Clips: {selected_report.total_selected}")
        print("=" * 65 + "\n")
        return 0
    except VideoPipelineError as e:
        logger.error(f"Pipeline failed: {e}")
        return 1
    except Exception as e:
        logger.exception(f"Unexpected error processing video: {e}")
        return 2


def build_parser() -> argparse.ArgumentParser:
    """Builds CLI argument parser supporting subcommands."""
    parser = argparse.ArgumentParser(
        prog="video-agent",
        description="AI Entertainment Video Clipping Agent - CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # analyze-video
    analyze_parser = subparsers.add_parser(
        "analyze-video",
        help="Inspect video metadata without creating a full project directory"
    )
    analyze_parser.add_argument("--input", "-i", required=True, help="Path to source video file")
    analyze_parser.add_argument("--json", action="store_true", help="Output raw JSON instead of formatted text")
    analyze_parser.add_argument("--min-duration", type=float, default=5.0, help="Minimum allowed video duration in seconds")
    analyze_parser.add_argument("--allow-no-audio", action="store_true", help="Do not reject video if it has no audio stream")

    # extract-audio
    extract_audio_parser = subparsers.add_parser(
        "extract-audio",
        help="Extract 16kHz mono audio WAV from video"
    )
    extract_audio_parser.add_argument("--input", "-i", required=True, help="Path to source video file")
    extract_audio_parser.add_argument("--output", "-o", required=True, help="Path for output audio WAV file")

    # transcribe-video
    transcribe_parser = subparsers.add_parser(
        "transcribe-video",
        help="Transcribe speech in video or audio using free local Whisper model"
    )
    transcribe_parser.add_argument("--input", "-i", required=True, help="Path to video or audio file")
    transcribe_parser.add_argument("--output", "-o", default=None, help="Optional directory to save transcript files")
    transcribe_parser.add_argument("--model", "-m", default="base", choices=["tiny", "base", "small", "medium", "large"], help="Whisper model size")
    transcribe_parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"], help="Inference device")

    # detect-scenes
    scenes_parser = subparsers.add_parser(
        "detect-scenes",
        help="Detect scene and shot boundaries in video"
    )
    scenes_parser.add_argument("--input", "-i", required=True, help="Path to source video file")
    scenes_parser.add_argument("--output", "-o", default=None, help="Optional output JSON path")
    scenes_parser.add_argument("--threshold", "-t", type=float, default=0.35, help="Scene detection threshold (0.0 to 1.0)")

    # sample-frames
    sample_parser = subparsers.add_parser(
        "sample-frames",
        help="Extract representative video frames using intelligent sampling"
    )
    sample_parser.add_argument("--input", "-i", required=True, help="Path to source video file")
    sample_parser.add_argument("--output", "-o", required=True, help="Target directory for sampled frames")
    sample_parser.add_argument("--strategy", "-s", default="adaptive", choices=["fixed_interval", "scene_change", "adaptive"], help="Sampling strategy")
    sample_parser.add_argument("--interval", type=float, default=2.0, help="Interval in seconds for sampling")

    # detect-moments
    moments_parser = subparsers.add_parser(
        "detect-moments",
        help="Detect entertainment candidate moments from transcript, audio, and visual artifacts"
    )
    moments_parser.add_argument("--transcript", required=True, help="Path to transcript.json")
    moments_parser.add_argument("--audio", default=None, help="Path to audio.wav")
    moments_parser.add_argument("--visual", default=None, help="Path to visual_analysis.json")
    moments_parser.add_argument("--output", "-o", default=None, help="Directory to save candidates.json and candidates.md")
    moments_parser.add_argument("--min-duration", type=float, default=15.0, help="Minimum candidate duration in seconds")
    moments_parser.add_argument("--max-duration", type=float, default=45.0, help="Maximum candidate duration in seconds")
    moments_parser.add_argument("--min-score", type=float, default=0.50, help="Minimum social potential score")

    # rank-clips
    rank_parser = subparsers.add_parser(
        "rank-clips",
        help="Rank candidates, optimize boundaries, and select top clip specifications"
    )
    rank_parser.add_argument("--candidates", required=True, help="Path to candidates.json")
    rank_parser.add_argument("--transcript", required=True, help="Path to transcript.json")
    rank_parser.add_argument("--output", "-o", default=None, help="Path to save selected_clips.json")
    rank_parser.add_argument("--max-clips", type=int, default=8, help="Maximum number of clips to select (default: 8)")
    rank_parser.add_argument("--min-spacing", type=float, default=15.0, help="Minimum spacing in seconds between selected clips")

    # extract-clips
    extract_clips_parser = subparsers.add_parser(
        "extract-clips",
        help="Extract raw candidate clips from video according to selected_clips.json"
    )
    extract_clips_parser.add_argument("--input", "-i", required=True, help="Path to source video file")
    extract_clips_parser.add_argument("--selected", "-s", required=True, help="Path to selected_clips.json")
    extract_clips_parser.add_argument("--output", "-o", required=True, help="Target project/output directory")
    extract_clips_parser.add_argument("--crf", type=int, default=18, help="Constant Rate Factor for video quality (default: 18)")
    extract_clips_parser.add_argument("--preset", default="fast", choices=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow"], help="FFmpeg encoding preset")
    extract_clips_parser.add_argument("--audio-bitrate", default="192k", help="Audio bitrate (default: 192k)")

    # qa-clips
    qa_parser = subparsers.add_parser(
        "qa-clips",
        help="Run automated quality assurance validation on extracted raw clips"
    )
    qa_parser.add_argument("--project-dir", "-p", required=True, help="Path to project directory containing raw_clips/")
    qa_parser.add_argument("--selected", "-s", required=True, help="Path to selected_clips.json")
    qa_parser.add_argument("--duration-tolerance", type=float, default=0.75, help="Maximum allowable duration discrepancy in seconds")
    qa_parser.add_argument("--max-silence", type=float, default=4.0, help="Maximum allowable continuous silence in seconds")

    # edit-clips
    edit_parser = subparsers.add_parser(
        "edit-clips",
        help="Transform raw clips into 9:16 vertical social media clips (1080x1920) with smart reframing"
    )
    edit_parser.add_argument("--project-dir", "-p", required=True, help="Path to project directory containing raw_clips/")
    edit_parser.add_argument("--selected", "-s", required=True, help="Path to selected_clips.json")
    edit_parser.add_argument("--strategy", default="smart_face", choices=["smart_face", "center"], help="Reframing strategy (default: smart_face)")
    edit_parser.add_argument("--loudness", type=float, default=-14.0, help="EBU R128 loudness target in LUFS (default: -14.0)")
    edit_parser.add_argument("--no-enhancements", action="store_true", help="Disable visual sharpening and contrast optimization")

    # generate-captions
    caption_parser = subparsers.add_parser(
        "generate-captions",
        help="Generate styled subtitles (.srt, .ass) and burn them onto vertical clips"
    )
    caption_parser.add_argument("--project-dir", "-p", required=True, help="Path to project directory containing edited_clips/")
    caption_parser.add_argument("--selected", "-s", required=True, help="Path to selected_clips.json")
    caption_parser.add_argument("--transcript", "-t", required=True, help="Path to transcript.json")
    caption_parser.add_argument("--style", default="bold_highlight", choices=["bold_highlight", "clean", "karaoke"], help="Subtitle styling template (default: bold_highlight)")

    # generate-metadata
    meta_parser = subparsers.add_parser(
        "generate-metadata",
        help="Generate AI-selected thumbnails with hook overlays and multi-platform social metadata packages"
    )
    meta_parser.add_argument("--project-dir", "-p", required=True, help="Path to project directory containing clips/")
    meta_parser.add_argument("--selected", "-s", required=True, help="Path to selected_clips.json")
    meta_parser.add_argument("--no-overlay", action="store_true", help="Disable hook text overlay on generated thumbnails")

    # process-video
    process_parser = subparsers.add_parser(
        "process-video",
        help="Execute full pipeline (Stages 1 to 9: Ingestion, Audio/Transcript, Visuals, Moments, Ranking, Extraction, QA, Editing, Captions & Metadata/Thumbnails)"
    )
    process_parser.add_argument("--input", "-i", required=True, help="Path to source video file")
    process_parser.add_argument("--output", "-o", required=True, help="Target project directory path")
    process_parser.add_argument("--min-duration", type=float, default=5.0, help="Minimum allowed video duration in seconds")
    process_parser.add_argument("--allow-no-audio", action="store_true", help="Do not reject video if it has no audio stream")
    process_parser.add_argument("--model", "-m", default="base", choices=["tiny", "base", "small", "medium", "large"], help="Whisper model size")
    process_parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"], help="Inference device")
    process_parser.add_argument("--strategy", "-s", default="adaptive", choices=["fixed_interval", "scene_change", "adaptive"], help="Frame sampling strategy")
    process_parser.add_argument("--interval", type=float, default=2.0, help="Frame sampling interval in seconds")
    process_parser.add_argument("--min-candidate-duration", type=float, default=15.0, help="Minimum candidate duration in seconds")
    process_parser.add_argument("--max-candidate-duration", type=float, default=45.0, help="Maximum candidate duration in seconds")
    process_parser.add_argument("--min-candidate-score", type=float, default=0.50, help="Minimum candidate social potential score")
    process_parser.add_argument("--max-clips", type=int, default=8, help="Maximum number of final clips to select")
    process_parser.add_argument("--min-spacing", type=float, default=15.0, help="Minimum spacing in seconds between selected clips")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "analyze-video":
        exit_code = handle_analyze_video(args)
    elif args.command == "extract-audio":
        exit_code = handle_extract_audio(args)
    elif args.command == "transcribe-video":
        exit_code = handle_transcribe_video(args)
    elif args.command == "detect-scenes":
        exit_code = handle_detect_scenes(args)
    elif args.command == "sample-frames":
        exit_code = handle_sample_frames(args)
    elif args.command == "detect-moments":
        exit_code = handle_detect_moments(args)
    elif args.command == "rank-clips":
        exit_code = handle_rank_clips(args)
    elif args.command == "extract-clips":
        exit_code = handle_extract_clips(args)
    elif args.command == "qa-clips":
        exit_code = handle_qa_clips(args)
    elif args.command == "edit-clips":
        exit_code = handle_edit_clips(args)
    elif args.command == "generate-captions":
        exit_code = handle_generate_captions(args)
    elif args.command == "generate-metadata":
        exit_code = handle_generate_metadata(args)
    elif args.command == "process-video":
        exit_code = handle_process_video(args)
    else:
        parser.print_help()
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
