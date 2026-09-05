"""Project workspace and directory structure management."""

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Tuple

from backend.models.video import ProjectWorkspace, VideoMetadata
from backend.utils.logger import logger

if TYPE_CHECKING:
    from backend.models.candidate import CandidateReport
    from backend.models.caption import ProjectCaptionReport
    from backend.models.clip import SelectedClipsReport
    from backend.models.editing import ProjectEditReport
    from backend.models.job import JobState
    from backend.models.metadata import ClipSocialMetadata, ProjectMetadataReport
    from backend.models.qa import FinalProjectQAReport, ProjectQAReport
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

    @staticmethod
    def save_selected_clips(
        report: "SelectedClipsReport",
        workspace: ProjectWorkspace
    ) -> Path:
        """Saves selected/selected_clips.json inside workspace."""
        selected_file = workspace.selected_dir / "selected_clips.json"
        with open(selected_file, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=4))
        logger.info(f"Saved selected clips specification to: {selected_file}")
        return selected_file

    @staticmethod
    def load_selected_clips(workspace: ProjectWorkspace) -> Optional["SelectedClipsReport"]:
        """Loads selected/selected_clips.json from workspace if present."""
        selected_file = workspace.selected_dir / "selected_clips.json"
        if not selected_file.exists():
            return None
        from backend.models.clip import SelectedClipsReport
        with open(selected_file, "r", encoding="utf-8") as f:
            return SelectedClipsReport.model_validate(json.load(f))

    @staticmethod
    def save_qa_report(
        report: "ProjectQAReport",
        workspace: ProjectWorkspace,
    ) -> Path:
        """Saves qa/clip_qa_report.json inside workspace."""
        qa_file = workspace.qa_dir / "clip_qa_report.json"
        with open(qa_file, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=4))
        logger.info(f"Saved QA report to: {qa_file}")
        return qa_file

    @staticmethod
    def save_edit_report(
        report: "ProjectEditReport",
        workspace: ProjectWorkspace,
    ) -> Path:
        """Saves analysis/edit_report.json inside workspace."""
        edit_file = workspace.analysis_dir / "edit_report.json"
        with open(edit_file, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=4))
        logger.info(f"Saved edit report to: {edit_file}")
        return edit_file

    @staticmethod
    def save_caption_report(
        report: "ProjectCaptionReport",
        workspace: ProjectWorkspace,
    ) -> Path:
        """Saves analysis/caption_report.json inside workspace."""
        cap_file = workspace.analysis_dir / "caption_report.json"
        with open(cap_file, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=4))
        logger.info(f"Saved caption report to: {cap_file}")
        return cap_file

    @staticmethod
    def save_social_metadata(
        metadata: "ClipSocialMetadata",
        workspace: ProjectWorkspace,
    ) -> Path:
        """Saves metadata/<clip_id>.json inside workspace."""
        meta_file = workspace.metadata_dir / f"{metadata.clip_id}.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            f.write(metadata.model_dump_json(indent=4))
        logger.info(f"Saved social metadata for {metadata.clip_id} to: {meta_file}")
        return meta_file

    @staticmethod
    def save_metadata_report(
        report: "ProjectMetadataReport",
        workspace: ProjectWorkspace,
    ) -> Path:
        """Saves analysis/metadata_report.json inside workspace."""
        meta_report_file = workspace.analysis_dir / "metadata_report.json"
        with open(meta_report_file, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=4))
        logger.info(f"Saved metadata report to: {meta_report_file}")
        return meta_report_file

    @staticmethod
    def save_final_qa_report(
        report: "FinalProjectQAReport",
        workspace: ProjectWorkspace,
    ) -> Path:
        """Saves qa/final_report.json inside workspace."""
        final_qa_file = workspace.qa_dir / "final_report.json"
        with open(final_qa_file, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=4))
        logger.info(f"Saved final multimodal QA report to: {final_qa_file}")
        return final_qa_file

    @staticmethod
    def save_job_state(
        job_state: "JobState",
        workspace: ProjectWorkspace,
    ) -> Path:
        """Saves job_state.json directly inside project root."""
        job_file = workspace.root / "job_state.json"
        with open(job_file, "w", encoding="utf-8") as f:
            f.write(job_state.model_dump_json(indent=4))
        logger.debug(f"Saved job state checkpoint to: {job_file}")
        return job_file

    @staticmethod
    def load_job_state(
        workspace: ProjectWorkspace,
    ) -> Optional["JobState"]:
        """Loads job_state.json from project root if it exists."""
        from backend.models.job import JobState
        job_file = workspace.root / "job_state.json"
        if not job_file.exists():
            return None
        try:
            with open(job_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return JobState.model_validate(data)
        except Exception as e:
            logger.warning(f"Failed to load job_state.json from {job_file}: {e}")
            return None





