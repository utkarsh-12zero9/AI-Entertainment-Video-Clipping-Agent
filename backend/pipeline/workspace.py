"""Project workspace and directory structure management."""

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Tuple

from backend.models.video import ProjectWorkspace, VideoMetadata
from backend.utils.logger import logger

if TYPE_CHECKING:
    from backend.models.candidate import CandidateReport
    from backend.models.transcript import TranscriptResult
    from backend.models.vision import SceneBoundary, VisualAnalysisResult


class WorkspaceManager:
    """Manages the lifecycle of project directories and intermediate artifacts."""

    @staticmethod
    def create_workspace(output_dir: Path) -> ProjectWorkspace:
        """Creates the standardized folder structure for a video clipping project."""
        root = Path(output_dir).resolve()
        
        workspace = ProjectWorkspace(
            root=root,
            input_dir=root / "input",
            audio_dir=root / "audio",
            transcript_dir=root / "transcript",
            frames_dir=root / "frames",
            analysis_dir=root / "analysis",
            candidates_dir=root / "candidates",
            selected_dir=root / "selected",
            raw_clips_dir=root / "raw_clips",
            edited_clips_dir=root / "edited_clips",
            captions_dir=root / "captions",
            thumbnails_dir=root / "thumbnails",
            metadata_dir=root / "metadata",
            qa_dir=root / "qa",
            final_dir=root / "final",
        )

        # Create all subdirectories
        for dir_path in [
            workspace.root,
            workspace.input_dir,
            workspace.audio_dir,
            workspace.transcript_dir,
            workspace.frames_dir,
            workspace.analysis_dir,
            workspace.candidates_dir,
            workspace.selected_dir,
            workspace.raw_clips_dir,
            workspace.edited_clips_dir,
            workspace.captions_dir,
            workspace.thumbnails_dir,
            workspace.metadata_dir,
            workspace.qa_dir,
            workspace.final_dir,
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Initialized workspace at: {workspace.root}")
        return workspace

    @staticmethod
    def copy_source_video(source_path: Path, workspace: ProjectWorkspace) -> Path:
        """Copies source video into project input folder if not already inside it."""
        source = Path(source_path).resolve()
        target = workspace.input_dir / source.name

        if source != target:
            logger.info(f"Copying source video to project input: {target}")
            shutil.copy2(source, target)
        return target

    @staticmethod
    def save_metadata(metadata: VideoMetadata, workspace: ProjectWorkspace) -> Path:
        """Saves video_metadata.json into the root of the project workspace."""
        meta_path = workspace.metadata_file
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write(metadata.model_dump_json(indent=4))
        logger.info(f"Saved video metadata to: {meta_path}")
        return meta_path

    @staticmethod
    def save_transcript(transcript: "TranscriptResult", workspace: ProjectWorkspace) -> Tuple[Path, Path]:
        """Saves transcript.json and transcript.txt inside workspace transcript_dir."""
        json_path = workspace.transcript_dir / "transcript.json"
        txt_path = workspace.transcript_dir / "transcript.txt"

        with open(json_path, "w", encoding="utf-8") as f:
            f.write(transcript.model_dump_json(indent=4))

        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(transcript.text)

        logger.info(f"Saved transcript artifacts to: {json_path} and {txt_path}")
        return json_path, txt_path

    @staticmethod
    def save_scenes(scenes: "List[SceneBoundary]", workspace: ProjectWorkspace) -> Path:
        """Saves analysis/scenes.json inside workspace analysis_dir."""
        scenes_file = workspace.analysis_dir / "scenes.json"
        with open(scenes_file, "w", encoding="utf-8") as f:
            data = [s.model_dump() for s in scenes]
            json.dump(data, f, indent=4)
        logger.info(f"Saved scenes artifact to: {scenes_file}")
        return scenes_file

    @staticmethod
    def save_visual_analysis(analysis: "VisualAnalysisResult", workspace: ProjectWorkspace) -> Path:
        """Saves analysis/visual_analysis.json inside workspace analysis_dir."""
        analysis_file = workspace.analysis_dir / "visual_analysis.json"
        with open(analysis_file, "w", encoding="utf-8") as f:
            f.write(analysis.model_dump_json(indent=4))
        logger.info(f"Saved visual analysis artifact to: {analysis_file}")
        return analysis_file

    @staticmethod
    def save_candidates(
        report: "CandidateReport",
        markdown_content: str,
        workspace: ProjectWorkspace
    ) -> Tuple[Path, Path]:
        """Saves candidates/candidates.json and candidates/candidates.md inside workspace."""
        json_path = workspace.candidates_dir / "candidates.json"
        md_path = workspace.candidates_dir / "candidates.md"

        with open(json_path, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=4))

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        logger.info(f"Saved candidate moments to: {json_path} and {md_path}")
        return json_path, md_path
