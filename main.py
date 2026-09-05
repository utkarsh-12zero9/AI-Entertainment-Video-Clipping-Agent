#!/usr/bin/env python3
"""CLI Entrypoint for AI Entertainment Video Clipping Agent."""

import argparse
import json
import sys
from pathlib import Path

from backend.audio.extractor import AudioExtractor
from backend.config.settings import PipelineSettings
from backend.pipeline.workspace import WorkspaceManager
from backend.transcription.whisper_local import LocalWhisperTranscriber
from backend.utils.errors import VideoPipelineError
from backend.utils.logger import logger, setup_logger
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
        # Check if input is a video or already audio
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


def handle_process_video(args: argparse.Namespace) -> int:
    """Executes full pipeline (Stage 1 Ingestion + Stage 2 Audio & Transcription)."""
    video_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    settings = PipelineSettings(
        min_video_duration=args.min_duration,
        require_audio=not args.allow_no_audio,
        whisper_model_name=args.model,
        whisper_device=args.device
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

        logger.info("Stage 1 & Stage 2 pipeline completed successfully.")

        print("\n" + "=" * 50)
        print("PIPELINE EXECUTION SUCCESSFUL (STAGE 1 & 2)")
        print("=" * 50)
        print(f"Project Workspace: {workspace.root}")
        print(f"Metadata File:     {meta_file}")
        print(f"Audio File:        {audio_file}")
        print(f"Transcript JSON:   {json_path}")
        print(f"Transcript TXT:    {txt_path}")
        print(f"Duration:          {metadata.duration}s")
        print(f"Resolution:        {metadata.width}x{metadata.height} ({metadata.aspect_ratio})")
        print(f"Segments Spoken:   {len(transcript.segments)}")
        print(f"Language:          {transcript.language}")
        print("=" * 50 + "\n")
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
    analyze_parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to source video file"
    )
    analyze_parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of formatted text"
    )
    analyze_parser.add_argument(
        "--min-duration",
        type=float,
        default=5.0,
        help="Minimum allowed video duration in seconds (default: 5.0)"
    )
    analyze_parser.add_argument(
        "--allow-no-audio",
        action="store_true",
        help="Do not reject video if it has no audio stream"
    )

    # extract-audio
    extract_audio_parser = subparsers.add_parser(
        "extract-audio",
        help="Extract 16kHz mono audio WAV from video"
    )
    extract_audio_parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to source video file"
    )
    extract_audio_parser.add_argument(
        "--output", "-o",
        required=True,
        help="Path for output audio WAV file (e.g. audio.wav)"
    )

    # transcribe-video
    transcribe_parser = subparsers.add_parser(
        "transcribe-video",
        help="Transcribe speech in video or audio using free local Whisper model"
    )
    transcribe_parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to video or audio file"
    )
    transcribe_parser.add_argument(
        "--output", "-o",
        default=None,
        help="Optional directory to save transcript.json and transcript.txt"
    )
    transcribe_parser.add_argument(
        "--model", "-m",
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size (default: base)"
    )
    transcribe_parser.add_argument(
        "--device",
        default="auto",
        choices=["auto", "cpu", "cuda"],
        help="Inference device (default: auto)"
    )

    # process-video
    process_parser = subparsers.add_parser(
        "process-video",
        help="Ingest video, extract audio, transcribe speech, and scaffold project directory"
    )
    process_parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to source video file"
    )
    process_parser.add_argument(
        "--output", "-o",
        required=True,
        help="Target project directory path (e.g. ./projects/video_001)"
    )
    process_parser.add_argument(
        "--min-duration",
        type=float,
        default=5.0,
        help="Minimum allowed video duration in seconds (default: 5.0)"
    )
    process_parser.add_argument(
        "--allow-no-audio",
        action="store_true",
        help="Do not reject video if it has no audio stream"
    )
    process_parser.add_argument(
        "--model", "-m",
        default="base",
        choices=["tiny", "base", "small", "medium", "large"],
        help="Whisper model size (default: base)"
    )
    process_parser.add_argument(
        "--device",
        default="auto",
        choices=["auto", "cpu", "cuda"],
        help="Inference device (default: auto)"
    )

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
    elif args.command == "process-video":
        exit_code = handle_process_video(args)
    else:
        parser.print_help()
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
