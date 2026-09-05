# AI Entertainment Video Clipping Agent

A production-oriented, multi-stage autonomous AI video pipeline that transforms long-form video content into polished, engaging short-form vertical clips.

---

## Current Status: Stage 1 — Project Foundation + Video Ingestion

### What is Implemented in Stage 1:
- **Modular Project Structure**:
  - `backend/config`: Configurable pipeline parameters with Pydantic (`PipelineSettings`).
  - `backend/models`: Domain data models (`VideoMetadata`, `ProjectWorkspace`).
  - `backend/utils`: Structured console + file logger (`setup_logger`), strict domain error hierarchy (`MissingVideoError`, `CorruptedVideoError`, `NoAudioError`, etc.).
  - `backend/video`: Video inspection engine (`VideoInspector`) wrapping `ffprobe`, calculating FPS, duration, exact and standard aspect ratios (`16:9`, `9:16`, `1:1`, etc.), and validating stream constraints.
  - `backend/pipeline`: Workspace manager (`WorkspaceManager`) scaffolding the required project directory tree and saving `video_metadata.json`.
- **Command-Line Interface (`main.py`)**:
  - `analyze-video`: Inspects any video and prints formatted metadata or JSON.
  - `process-video`: Ingests video, creates standardized project workspace, validates constraints, and writes `video_metadata.json`.
- **Automated Test Suite**:
  - 12 comprehensive unit and integration tests using synthetic media generated via FFmpeg (`pytest`).

---

## Installation & Setup

Ensure **Python 3.10+** and **FFmpeg/FFprobe** are installed and added to your `PATH`.

```bash
pip install -r requirements.txt
```

---

## CLI Usage Examples

### 1. Analyze Video Metadata (dry run)
```bash
python main.py analyze-video --input ./my_video.mp4
```
To output raw JSON:
```bash
python main.py analyze-video --input ./my_video.mp4 --json
```

### 2. Ingest and Scaffold Project Workspace
```bash
python main.py process-video --input ./my_video.mp4 --output ./projects/my_video_001
```

Generated project directory layout:
```text
projects/my_video_001/
├── video_metadata.json
├── pipeline.log
├── input/
├── audio/
├── transcript/
├── frames/
├── analysis/
├── candidates/
├── selected/
├── raw_clips/
├── edited_clips/
├── captions/
├── thumbnails/
├── metadata/
├── qa/
└── final/
```

---

## Running the Test Suite
```bash
python -m pytest -v
```
