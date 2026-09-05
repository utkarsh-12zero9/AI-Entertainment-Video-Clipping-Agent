#!/usr/bin/env python3
"""CLI Entrypoint for AI Entertainment Video Clipping Agent."""

import argparse
import json
import sys
from pathlib import Path

from backend.config.settings import PipelineSettings
from backend.pipeline.workspace import WorkspaceManager
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


def handle_process_video(args: argparse.Namespace) -> int:
    """Executes video ingestion, creates project workspace, saves metadata."""
    video_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    settings = PipelineSettings(
        min_video_duration=args.min_duration,
        require_audio=not args.allow_no_audio
    )

    # Initialize workspace
    workspace = WorkspaceManager.create_workspace(output_path)
    
    # Configure logging to also write into project log file
    setup_logger(log_file=workspace.log_file)

    logger.info(f"Starting ingestion for: {video_path}")
    inspector = VideoInspector(settings=settings)

    try:
        metadata = inspector.inspect(video_path)
        WorkspaceManager.copy_source_video(video_path, workspace)
        meta_file = WorkspaceManager.save_metadata(metadata, workspace)
        
        logger.info(f"Ingestion completed successfully.")
        logger.info(f"Project directory ready at: {workspace.root}")
        logger.info(f"Metadata written to: {meta_file}")
        
        print("\n" + "=" * 50)
        print("STAGE 1: VIDEO INGESTION SUCCESSFUL")
        print("=" * 50)
        print(f"Project Workspace: {workspace.root}")
        print(f"Metadata File:     {meta_file}")
        print(f"Duration:          {metadata.duration}s")
        print(f"Resolution:        {metadata.width}x{metadata.height} ({metadata.aspect_ratio})")
        print(f"FPS:               {metadata.fps}")
        print(f"Audio:             {'Yes (' + str(metadata.audio_codec) + ')' if metadata.has_audio else 'No'}")
        print("=" * 50 + "\n")
        return 0
    except VideoPipelineError as e:
        logger.error(f"Ingestion validation failed: {e}")
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

    # process-video
    process_parser = subparsers.add_parser(
        "process-video",
        help="Ingest video, validate, and scaffold project directory"
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

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "analyze-video":
        exit_code = handle_analyze_video(args)
    elif args.command == "process-video":
        exit_code = handle_process_video(args)
    else:
        parser.print_help()
        exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
