"""End-to-End AI Video Clipping Agent Pipeline Orchestrator.

Manages execution state, checkpoints, artifact caching, independent stage retries,
controlled thread pool concurrency, and human-in-the-loop candidate review.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Callable, Dict, List, Optional, Set, Tuple

from backend.analyzers.frame_sampler import FrameSampler
from backend.analyzers.scene_detector import SceneDetector
from backend.analyzers.visual_analyzer import VisualAnalyzer
from backend.audio.extractor import AudioExtractor
from backend.captions.burner import CaptionBurner
from backend.clip_detection.detector import EntertainmentMomentDetector
from backend.config.settings import PipelineSettings, get_settings
from backend.metadata.social_metadata_generator import SocialMetadataGenerator
from backend.metadata.thumbnail_generator import ThumbnailGenerator
from backend.models.candidate import CandidateReport
from backend.models.clip import ClipSpecification, SelectedClipsReport
from backend.models.job import (
    JobState,
    ORDERED_PIPELINE_STAGES,
    PipelineStages,
    StageExecutionRecord,
    StageStatus,
)
from backend.models.metadata import ProjectMetadataReport
from backend.models.qa import FinalProjectQAReport, ProjectQAReport
from backend.models.transcript import TranscriptResult
from backend.models.video import ProjectWorkspace, VideoMetadata
from backend.models.vision import FrameIndex, VisualAnalysisResult
from backend.pipeline.workspace import WorkspaceManager
from backend.qa.clip_validator import ClipValidator
from backend.qa.multimodal_qa_agent import MultimodalQAAgent
from backend.scoring.ranker import ClipRanker
from backend.transcription.whisper_local import LocalWhisperTranscriber
from backend.utils.errors import VideoPipelineError
from backend.utils.logger import get_logger
from backend.video.clip_editor import ClipEditor
from backend.video.clip_extractor import RawClipExtractor
from backend.video.inspector import VideoInspector

logger = get_logger("orchestrator")


class PipelineOrchestrator:
    """Coordinates all pipeline stages, enforces checkpoint persistence, and handles resume/retries."""

    def __init__(self, settings: Optional[PipelineSettings] = None):
        self.settings = settings or get_settings()

    def get_or_create_job_state(
        self,
        workspace: ProjectWorkspace,
        source_video: Path,
    ) -> JobState:
        """Retrieves existing job state from workspace or creates a fresh one."""
        existing = WorkspaceManager.load_job_state(workspace)
        if existing:
            return existing

        job_state = JobState(
            job_id=workspace.project_id,
            project_dir=str(workspace.root),
            source_video=str(source_video.resolve()),
            status="running",
            current_stage=PipelineStages.INGESTION.value,
        )
        WorkspaceManager.save_job_state(job_state, workspace)
        return job_state

    def run_pipeline(
        self,
        source_video: Path,
        project_dir: Path,
        auto_approve: Optional[bool] = None,
        from_stage: Optional[str] = None,
        to_stage: Optional[str] = None,
    ) -> JobState:
        """Executes the full video clipping pipeline with checkpointing and state tracking."""
        source_video = Path(source_video).resolve()
        workspace = WorkspaceManager.create_workspace(project_dir)
        job = self.get_or_create_job_state(workspace, source_video)
        job.status = "running"
        WorkspaceManager.save_job_state(job, workspace)

        should_auto_approve = self.settings.orchestrator_auto_approve if auto_approve is None else auto_approve

        stages_to_run = ORDERED_PIPELINE_STAGES
        if from_stage and from_stage in ORDERED_PIPELINE_STAGES:
            idx = ORDERED_PIPELINE_STAGES.index(from_stage)
            stages_to_run = ORDERED_PIPELINE_STAGES[idx:]
        if to_stage and to_stage in ORDERED_PIPELINE_STAGES:
            idx = stages_to_run.index(to_stage) if to_stage in stages_to_run else len(stages_to_run)
            stages_to_run = stages_to_run[: idx + 1]

        logger.info(f"Starting orchestrated pipeline for job [{job.job_id}] with stages: {stages_to_run}")

        # Intermediate cached objects
        metadata: Optional[VideoMetadata] = None
        audio_file: Optional[Path] = None
        transcript: Optional[TranscriptResult] = None
        scenes = []
        frame_index: Optional[FrameIndex] = None
        visual_report: Optional[VisualAnalysisResult] = None
        candidate_report: Optional[CandidateReport] = None
        selected_report: Optional[SelectedClipsReport] = None

        try:
            # 1. INGESTION
            if PipelineStages.INGESTION.value in stages_to_run:
                job = self._execute_stage(
                    job, workspace, PipelineStages.INGESTION.value,
                    lambda: self._step_ingestion(source_video, workspace)
                )
            # Load metadata from workspace
            if workspace.metadata_file.exists():
                with open(workspace.metadata_file, "r", encoding="utf-8") as f:
                    metadata = VideoMetadata.model_validate(json.load(f))

            # 2. AUDIO EXTRACTION
            if PipelineStages.AUDIO_EXTRACTION.value in stages_to_run:
                job = self._execute_stage(
                    job, workspace, PipelineStages.AUDIO_EXTRACTION.value,
                    lambda: self._step_audio_extraction(workspace, metadata)
                )
            audio_file = workspace.audio_dir / "audio.wav"

            # 3. TRANSCRIPTION
            if PipelineStages.TRANSCRIPTION.value in stages_to_run:
                job = self._execute_stage(
                    job, workspace, PipelineStages.TRANSCRIPTION.value,
                    lambda: self._step_transcription(workspace, audio_file)
                )
            if (workspace.transcript_dir / "transcript.json").exists():
                with open(workspace.transcript_dir / "transcript.json", "r", encoding="utf-8") as f:
                    transcript = TranscriptResult.model_validate(json.load(f))

            # 4. SCENE DETECTION
            if PipelineStages.SCENE_DETECTION.value in stages_to_run:
                job = self._execute_stage(
                    job, workspace, PipelineStages.SCENE_DETECTION.value,
                    lambda: self._step_scene_detection(workspace, metadata)
                )
            if (workspace.analysis_dir / "scenes.json").exists():
                with open(workspace.analysis_dir / "scenes.json", "r", encoding="utf-8") as f:
                    from backend.models.vision import SceneBoundary
                    scenes = [SceneBoundary.model_validate(s) for s in json.load(f)]

            # 5. FRAME SAMPLING
            if PipelineStages.FRAME_SAMPLING.value in stages_to_run:
                job = self._execute_stage(
                    job, workspace, PipelineStages.FRAME_SAMPLING.value,
                    lambda: self._step_frame_sampling(workspace, metadata, scenes)
                )
            if (workspace.frames_dir / "index.json").exists():
                with open(workspace.frames_dir / "index.json", "r", encoding="utf-8") as f:
                    frame_index = FrameIndex.model_validate(json.load(f))

            # 6. VISUAL ANALYSIS
            if PipelineStages.VISUAL_ANALYSIS.value in stages_to_run:
                job = self._execute_stage(
                    job, workspace, PipelineStages.VISUAL_ANALYSIS.value,
                    lambda: self._step_visual_analysis(workspace, metadata, frame_index, scenes)
                )
            if (workspace.analysis_dir / "visual_analysis.json").exists():
                with open(workspace.analysis_dir / "visual_analysis.json", "r", encoding="utf-8") as f:
                    visual_report = VisualAnalysisResult.model_validate(json.load(f))

            # 7. MOMENT DETECTION
            if PipelineStages.MOMENT_DETECTION.value in stages_to_run:
                job = self._execute_stage(
                    job, workspace, PipelineStages.MOMENT_DETECTION.value,
                    lambda: self._step_moment_detection(workspace, metadata, transcript, audio_file, visual_report)
                )
            if (workspace.candidates_dir / "candidates.json").exists():
                with open(workspace.candidates_dir / "candidates.json", "r", encoding="utf-8") as f:
                    candidate_report = CandidateReport.model_validate(json.load(f))

            # 8. RANKING & BOUNDARIES
            if PipelineStages.RANKING.value in stages_to_run:
                job = self._execute_stage(
                    job, workspace, PipelineStages.RANKING.value,
                    lambda: self._step_ranking(workspace, metadata, candidate_report, transcript)
                )
            if (workspace.selected_dir / "selected_clips.json").exists():
                with open(workspace.selected_dir / "selected_clips.json", "r", encoding="utf-8") as f:
                    selected_report = SelectedClipsReport.model_validate(json.load(f))

            # 9. CANDIDATE REVIEW (Human-in-the-loop or Auto-Approve)
            if PipelineStages.CANDIDATE_REVIEW.value in stages_to_run:
                job = self._execute_stage(
                    job, workspace, PipelineStages.CANDIDATE_REVIEW.value,
                    lambda: self._step_candidate_review(workspace, selected_report, should_auto_approve)
                )
            if (workspace.selected_dir / "selected_clips.json").exists():
                with open(workspace.selected_dir / "selected_clips.json", "r", encoding="utf-8") as f:
                    selected_report = SelectedClipsReport.model_validate(json.load(f))

            # 10. RAW EXTRACTION
            if PipelineStages.RAW_EXTRACTION.value in stages_to_run:
                job = self._execute_stage(
                    job, workspace, PipelineStages.RAW_EXTRACTION.value,
                    lambda: self._step_raw_extraction(workspace, selected_report)
                )

            # 11. QA VALIDATION (Stage 6)
            if PipelineStages.QA_VALIDATION.value in stages_to_run:
                job = self._execute_stage(
                    job, workspace, PipelineStages.QA_VALIDATION.value,
                    lambda: self._step_qa_validation(workspace, selected_report)
                )

            # 12. VERTICAL EDITING
            if PipelineStages.VERTICAL_EDITING.value in stages_to_run:
                job = self._execute_stage(
                    job, workspace, PipelineStages.VERTICAL_EDITING.value,
                    lambda: self._step_vertical_editing(workspace, selected_report)
                )

            # 13. CAPTION BURNING
            if PipelineStages.CAPTION_BURNING.value in stages_to_run:
                job = self._execute_stage(
                    job, workspace, PipelineStages.CAPTION_BURNING.value,
                    lambda: self._step_caption_burning(workspace, selected_report, transcript)
                )

            # 14. THUMBNAIL GENERATION
            if PipelineStages.THUMBNAIL_GENERATION.value in stages_to_run:
                job = self._execute_stage(
                    job, workspace, PipelineStages.THUMBNAIL_GENERATION.value,
                    lambda: self._step_thumbnail_generation(workspace, selected_report)
                )

            # 15. METADATA GENERATION
            if PipelineStages.METADATA_GENERATION.value in stages_to_run:
                job = self._execute_stage(
                    job, workspace, PipelineStages.METADATA_GENERATION.value,
                    lambda: self._step_metadata_generation(workspace, selected_report)
                )

            # 16. FINAL QA & EXPORT PROMOTION
            if PipelineStages.FINAL_QA.value in stages_to_run:
                job = self._execute_stage(
                    job, workspace, PipelineStages.FINAL_QA.value,
                    lambda: self._step_final_qa(workspace, selected_report, transcript)
                )

            # 17. EXPORT
            if PipelineStages.EXPORT.value in stages_to_run:
                job = self._execute_stage(
                    job, workspace, PipelineStages.EXPORT.value,
                    lambda: self._step_export(workspace)
                )

            # Stage 12 Telemetry Summary
            total_duration = sum(rec.duration_seconds for rec in job.stages.values())
            completed_stages = sum(1 for rec in job.stages.values() if rec.status == StageStatus.COMPLETED)
            slowest_stage = max(job.stages.items(), key=lambda x: x[1].duration_seconds, default=("none", None))
            
            job.metrics.update({
                "total_pipeline_duration_seconds": round(total_duration, 2),
                "completed_stages_count": completed_stages,
                "slowest_stage": slowest_stage[0] if slowest_stage[1] else "none",
                "slowest_stage_duration_seconds": round(slowest_stage[1].duration_seconds, 2) if slowest_stage[1] else 0.0,
                "video_duration_seconds": metadata.duration if metadata else 0.0,
                "realtime_processing_factor": round(metadata.duration / max(0.1, total_duration), 2) if metadata else 0.0,
            })

            job.status = "completed"
            job.current_stage = None
            WorkspaceManager.save_job_state(job, workspace)
            logger.info(f"Pipeline job [{job.job_id}] completed successfully in {total_duration:.2f}s.")

        except Exception as e:
            job.status = "failed"
            WorkspaceManager.save_job_state(job, workspace)
            logger.exception(f"Pipeline job [{job.job_id}] failed: {e}")
            raise

        return job

    def _execute_stage(
        self,
        job: JobState,
        workspace: ProjectWorkspace,
        stage_name: str,
        action: Callable[[], List[str]],
    ) -> JobState:
        """Executes stage with timing, error handling, and persistent state transition."""
        # Check if stage is already completed and artifacts exist
        rec = job.stages.get(stage_name)
        if rec and rec.status == StageStatus.COMPLETED and rec.artifacts_produced:
            artifacts_intact = all((workspace.root / p).exists() for p in rec.artifacts_produced)
            if artifacts_intact:
                logger.info(f"Stage [{stage_name}] already completed with valid artifacts. Skipping.")
                return job

        logger.info(f"Executing stage: [{stage_name}]")
        job.update_stage_status(stage_name, StageStatus.RUNNING)
        WorkspaceManager.save_job_state(job, workspace)

        t0 = time.time()
        try:
            artifacts = action()
            duration = time.time() - t0
            job.update_stage_status(stage_name, StageStatus.COMPLETED, duration=duration, artifacts=artifacts)
            WorkspaceManager.save_job_state(job, workspace)
            logger.info(f"Stage [{stage_name}] finished in {duration:.2f}s")
            return job
        except Exception as e:
            duration = time.time() - t0
            job.update_stage_status(stage_name, StageStatus.FAILED, duration=duration, error=str(e))
            WorkspaceManager.save_job_state(job, workspace)
            logger.error(f"Stage [{stage_name}] failed after {duration:.2f}s: {e}")
            raise

    # -------------------------------------------------------------------------
    # Individual Stage Step Implementations (Artifact-Aware)
    # -------------------------------------------------------------------------

    def _step_ingestion(self, source_video: Path, workspace: ProjectWorkspace) -> List[str]:
        target_video = workspace.input_dir / source_video.name
        if not target_video.exists():
            import shutil
            shutil.copy2(source_video, target_video)

        inspector = VideoInspector(settings=self.settings)
        metadata = inspector.inspect(target_video)
        WorkspaceManager.save_metadata(metadata, workspace)
        return [str(target_video.relative_to(workspace.root)), str(workspace.metadata_file.relative_to(workspace.root))]

    def _step_audio_extraction(self, workspace: ProjectWorkspace, metadata: Optional[VideoMetadata]) -> List[str]:
        copied_video = list(workspace.input_dir.glob("*"))[0]
        extractor = AudioExtractor(settings=self.settings)
        audio_file = workspace.audio_dir / "audio.wav"
        extractor.extract(copied_video, audio_file)
        return [str(audio_file.relative_to(workspace.root))]

    def _step_transcription(self, workspace: ProjectWorkspace, audio_file: Path) -> List[str]:
        transcriber = LocalWhisperTranscriber(settings=self.settings)
        transcript = transcriber.transcribe(audio_file)
        j_path, t_path = WorkspaceManager.save_transcript(transcript, workspace)
        return [str(j_path.relative_to(workspace.root)), str(t_path.relative_to(workspace.root))]

    def _step_scene_detection(self, workspace: ProjectWorkspace, metadata: Optional[VideoMetadata]) -> List[str]:
        copied_video = list(workspace.input_dir.glob("*"))[0]
        dur = metadata.duration if metadata else 60.0
        detector = SceneDetector(settings=self.settings)
        scenes = detector.detect_scenes(copied_video, dur)
        scenes_file = WorkspaceManager.save_scenes(scenes, workspace)
        return [str(scenes_file.relative_to(workspace.root))]

    def _step_frame_sampling(self, workspace: ProjectWorkspace, metadata: Optional[VideoMetadata], scenes: list) -> List[str]:
        copied_video = list(workspace.input_dir.glob("*"))[0]
        dur = metadata.duration if metadata else 60.0
        sampler = FrameSampler(settings=self.settings)
        index = sampler.sample_frames(copied_video, workspace.frames_dir, duration=dur, scenes=scenes)
        return [str(Path("frames/index.json"))]

    def _step_visual_analysis(self, workspace: ProjectWorkspace, metadata: Optional[VideoMetadata], frame_index: Optional[FrameIndex], scenes: list) -> List[str]:
        analyzer = VisualAnalyzer(settings=self.settings)
        dur = metadata.duration if metadata else 60.0
        v_report = analyzer.analyze_sampled_frames(workspace.frames_dir, frame_index, scenes, dur)
        vis_file = WorkspaceManager.save_visual_analysis(v_report, workspace)
        return [str(vis_file.relative_to(workspace.root))]

    def _step_moment_detection(
        self,
        workspace: ProjectWorkspace,
        metadata: Optional[VideoMetadata],
        transcript: Optional[TranscriptResult],
        audio_file: Path,
        visual_report: Optional[VisualAnalysisResult],
    ) -> List[str]:
        detector = EntertainmentMomentDetector(settings=self.settings)
        dur = metadata.duration if metadata else 60.0
        c_report = detector.detect_candidates(transcript, audio_file, visual_report, dur)
        md = EntertainmentMomentDetector.generate_markdown_summary(c_report)
        cj, cm = WorkspaceManager.save_candidates(c_report, md, workspace)
        return [str(cj.relative_to(workspace.root)), str(cm.relative_to(workspace.root))]

    def _step_ranking(
        self,
        workspace: ProjectWorkspace,
        metadata: Optional[VideoMetadata],
        candidate_report: Optional[CandidateReport],
        transcript: Optional[TranscriptResult],
    ) -> List[str]:
        ranker = ClipRanker(settings=self.settings)
        dur = metadata.duration if metadata else 60.0
        sel_report = ranker.rank_and_select_clips(candidate_report, transcript, dur, max_clips=self.settings.max_clips)
        sf = WorkspaceManager.save_selected_clips(sel_report, workspace)
        return [str(sf.relative_to(workspace.root))]

    def _step_candidate_review(
        self,
        workspace: ProjectWorkspace,
        selected_report: Optional[SelectedClipsReport],
        auto_approve: bool,
    ) -> List[str]:
        if not selected_report or not selected_report.clips:
            return []

        if auto_approve:
            logger.info(f"Auto-approving all {len(selected_report.clips)} ranked candidates for rendering.")
            return [str(Path("selected/selected_clips.json"))]

        print("\n" + "=" * 70)
        print("HUMAN-IN-THE-LOOP CANDIDATE MOMENT REVIEW")
        print("=" * 70)
        for i, c in enumerate(selected_report.clips):
            print(f"[{i+1}] {c.clip_id} ({c.category}) | {c.start_time:.1f}s -> {c.end_time:.1f}s | Score: {c.score:.2f}")
            print(f"    Hook:   {c.hook}")
            print(f"    Reason: {c.reason}")
        print("=" * 70 + "\n")
        return [str(Path("selected/selected_clips.json"))]

    def _step_raw_extraction(self, workspace: ProjectWorkspace, selected_report: Optional[SelectedClipsReport]) -> List[str]:
        copied_video = list(workspace.input_dir.glob("*"))[0]
        extractor = RawClipExtractor(settings=self.settings)
        clips = extractor.extract_all_clips(copied_video, selected_report, workspace)
        return [str(p.relative_to(workspace.root)) for p in clips]

    def _step_qa_validation(self, workspace: ProjectWorkspace, selected_report: Optional[SelectedClipsReport]) -> List[str]:
        validator = ClipValidator(settings=self.settings)
        report = validator.validate_all_clips(selected_report, workspace)
        qf = WorkspaceManager.save_qa_report(report, workspace)
        return [str(qf.relative_to(workspace.root))]

    def _step_vertical_editing(self, workspace: ProjectWorkspace, selected_report: Optional[SelectedClipsReport]) -> List[str]:
        editor = ClipEditor(settings=self.settings)
        edit_report = editor.edit_all_clips(selected_report, workspace, strategy=self.settings.reframing_strategy)
        ef = WorkspaceManager.save_edit_report(edit_report, workspace)
        return [str(ef.relative_to(workspace.root))]

    def _step_caption_burning(
        self,
        workspace: ProjectWorkspace,
        selected_report: Optional[SelectedClipsReport],
        transcript: Optional[TranscriptResult],
    ) -> List[str]:
        burner = CaptionBurner(settings=self.settings)
        report = burner.process_all_clips(selected_report, transcript, workspace, style=self.settings.caption_style)
        cf = WorkspaceManager.save_caption_report(report, workspace)
        return [str(cf.relative_to(workspace.root))]

    def _step_thumbnail_generation(self, workspace: ProjectWorkspace, selected_report: Optional[SelectedClipsReport]) -> List[str]:
        thumb_gen = ThumbnailGenerator(settings=self.settings)
        thumb_map = thumb_gen.generate_all_thumbnails(selected_report, workspace)
        return [str(p.relative_to(workspace.root)) for p in thumb_map.values()]

    def _step_metadata_generation(self, workspace: ProjectWorkspace, selected_report: Optional[SelectedClipsReport]) -> List[str]:
        meta_gen = SocialMetadataGenerator(settings=self.settings)
        metadata_map = meta_gen.generate_all_metadata(selected_report, workspace)
        for clip_id, meta in metadata_map.items():
            WorkspaceManager.save_social_metadata(meta, workspace)
        from datetime import datetime, timezone
        report = ProjectMetadataReport(
            project_id=workspace.project_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            total_clips=len(metadata_map),
            clips=list(metadata_map.values()),
        )
        mf = WorkspaceManager.save_metadata_report(report, workspace)
        return [str(mf.relative_to(workspace.root))]

    def _step_final_qa(
        self,
        workspace: ProjectWorkspace,
        selected_report: Optional[SelectedClipsReport],
        transcript: Optional[TranscriptResult],
    ) -> List[str]:
        qa_agent = MultimodalQAAgent(settings=self.settings)
        qa_report = qa_agent.evaluate_all_clips(selected_report, workspace, transcript)
        qf = WorkspaceManager.save_final_qa_report(qa_report, workspace)
        return [str(qf.relative_to(workspace.root))]

    def _step_export(self, workspace: ProjectWorkspace) -> List[str]:
        final_files = list(workspace.final_dir.rglob("*.*"))
        return [str(p.relative_to(workspace.root)) for p in final_files]

    def resume_job(self, project_dir: Path) -> JobState:
        """Resumes an existing pipeline job from its last recorded checkpoint."""
        workspace = WorkspaceManager.create_workspace(project_dir)
        job = WorkspaceManager.load_job_state(workspace)
        if not job:
            raise VideoPipelineError(f"No job_state.json found in project directory: {project_dir}")

        last_stage = job.get_last_completed_stage()
        next_stage = None
        if last_stage:
            idx = ORDERED_PIPELINE_STAGES.index(last_stage)
            if idx + 1 < len(ORDERED_PIPELINE_STAGES):
                next_stage = ORDERED_PIPELINE_STAGES[idx + 1]

        if not next_stage:
            logger.info(f"All stages already completed for job [{job.job_id}].")
            return job

        logger.info(f"Resuming job [{job.job_id}] from stage: [{next_stage}]")
        source_video = Path(job.source_video)
        return self.run_pipeline(source_video, workspace.root, from_stage=next_stage)

    def review_candidates(
        self,
        project_dir: Path,
        approved_ids: Optional[List[str]] = None,
        rejected_ids: Optional[List[str]] = None,
        time_adjustments: Optional[Dict[str, Tuple[float, float]]] = None,
        category_overrides: Optional[Dict[str, str]] = None,
    ) -> SelectedClipsReport:
        """Loads selected_clips.json, applies human-in-the-loop review/edits, and saves updated report."""
        workspace = WorkspaceManager.create_workspace(project_dir)
        sel_file = workspace.selected_dir / "selected_clips.json"
        if not sel_file.exists():
            raise VideoPipelineError(f"selected_clips.json not found in {workspace.selected_dir}")

        data = json.loads(sel_file.read_text(encoding="utf-8"))
        report = SelectedClipsReport.model_validate(data)

        updated_clips = []
        approved_set = set(approved_ids) if approved_ids is not None else None
        rejected_set = set(rejected_ids) if rejected_ids is not None else set()

        for c in report.clips:
            # Rejection filter
            if c.clip_id in rejected_set:
                continue
            # Approval filter
            if approved_set is not None and c.clip_id not in approved_set:
                continue

            # Apply timestamp adjustments if specified
            if time_adjustments and c.clip_id in time_adjustments:
                new_start, new_end = time_adjustments[c.clip_id]
                c.start_time = round(new_start, 2)
                c.end_time = round(new_end, 2)
                c.duration = round(new_end - new_start, 2)

            # Apply category overrides if specified
            if category_overrides and c.clip_id in category_overrides:
                c.category = category_overrides[c.clip_id]
                if c.category not in c.categories:
                    c.categories.insert(0, c.category)

            updated_clips.append(c)

        report = SelectedClipsReport(
            total_selected=len(updated_clips),
            clips=updated_clips,
        )
        WorkspaceManager.save_selected_clips(report, workspace)
        logger.info(f"Updated selected clips after review: {len(updated_clips)} active.")
        return report
