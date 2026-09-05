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

---

## Current Status: Stage 2 — Audio Extraction + Transcription

### What is Implemented in Stage 2:
- **Free, Open-Source Local Transcription**:
  - Uses local OpenAI Whisper models (`tiny`, `base`, `small`, `medium`, `large`).
  - No paid API keys or external services required. Runs on local CPU or CUDA automatically.
- **Audio Extraction Engine (`backend/audio/extractor.py`)**:
  - `AudioExtractor`: Automatically extracts high-fidelity 16kHz mono uncompressed PCM audio (`audio/audio.wav`), optimized for speech recognition.
  - Validates audio stream existence and output non-emptiness.
- **Timestamped Transcription (`backend/transcription/whisper_local.py`)**:
  - `LocalWhisperTranscriber`: Generates segment-level timestamps (`start`, `end`, `text`) and word-level timestamps (`words` with start, end, confidence).
  - Pluggable `BaseTranscriber` interface ready for future speaker diarization.
- **Artifact Serialization**:
  - `transcript/transcript.json`: Structured JSON containing detected language, duration, segments, and word timestamps.
  - `transcript/transcript.txt`: Clean plaintext transcript text.
- **New CLI Commands**:
  - `extract-audio`: Extracts 16kHz mono WAV from any video file.
  - `transcribe-video`: Transcribes video or audio directly using local Whisper.
  - `process-video`: Executes both Stage 1 (Ingestion) and Stage 2 (Audio extraction & Transcription) sequentially.

---

## Stage 2 CLI Usage Examples

### 1. Extract Audio from Video
```bash
python main.py extract-audio --input ./video.mp4 --output ./audio.wav
```

### 2. Transcribe Video / Audio File Directly
```bash
python main.py transcribe-video --input ./video.mp4 --model base --output ./transcript_out
```

### 3. Run Full Pipeline (Stage 1 + Stage 2)
```bash
python main.py process-video --input ./video.mp4 --output ./projects/my_project_001 --model base
```

Workspace output after Stage 2:
```text
projects/my_project_001/
├── video_metadata.json
├── pipeline.log
├── input/
│   └── video.mp4
├── audio/
│   └── audio.wav
├── transcript/
│   ├── transcript.json
│   └── transcript.txt
...
```

