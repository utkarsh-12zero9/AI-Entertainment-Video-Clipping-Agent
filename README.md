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

---

## Current Status: Stage 3 — Visual Frame Sampling + Analysis

### What is Implemented in Stage 3:
- **100% Free & Local Multimodal Vision Processing**:
  - No external paid vision API calls. All frame sampling, scene detection, face detection, and image analysis run entirely locally on CPU / GPU.
- **Intelligent Frame Sampling (`backend/analyzers/frame_sampler.py`)**:
  - Multiple sampling strategies:
    1. `fixed_interval`: Samples 1 representative frame every $N$ seconds.
    2. `scene_change`: Samples frames based on shot cut midpoints.
    3. `adaptive`: Combines shot boundaries with interval bounds to balance coverage and efficiency.
  - Extracts clean JPEG frames into `frames/frame_000001.jpg` and produces `frames/index.json`.
- **Scene / Shot Boundary Detection (`backend/analyzers/scene_detector.py`)**:
  - Uses FFmpeg's internal scene change filter (`select='gt(scene,THRESHOLD)'`) to identify cut points without heavy re-encoding.
  - Outputs `analysis/scenes.json` with exact start/end timestamps and shot durations.
- **Local Visual Content Analysis (`backend/analyzers/visual_analyzer.py`)**:
  - Computes brightness, contrast, and Laplacian variance sharpness metrics.
  - Detects faces, shot composition (`close_up`, `medium_shot`, `wide_shot`), and visual activity levels (`low`, `moderate`, `high`).
  - Outputs `analysis/visual_analysis.json`.
- **New CLI Commands**:
  - `detect-scenes`: Detects scene boundaries in a video.
  - `sample-frames`: Intelligently samples representative video frames.
  - `process-video`: Executes Stage 1 (Ingestion) + Stage 2 (Audio & Transcription) + Stage 3 (Visual Frame Sampling & Analysis).

---

## Stage 3 CLI Usage Examples

### 1. Detect Scene Boundaries
```bash
python main.py detect-scenes --input ./video.mp4 --threshold 0.35
```

### 2. Sample Representative Frames
```bash
python main.py sample-frames --input ./video.mp4 --output ./frames --strategy adaptive --interval 2.0
```

### 3. Run Full Pipeline (Stages 1, 2, & 3)
```bash
python main.py process-video --input ./video.mp4 --output ./projects/my_project_001 --model base --strategy adaptive
```

Workspace output after Stage 3:
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
├── frames/
│   ├── index.json
│   ├── frame_000001.jpg
│   ├── frame_000002.jpg
│   └── ...
├── analysis/
│   ├── scenes.json
│   └── visual_analysis.json
...
```

---

## Current Status: Stage 4 — Multimodal Entertainment Moment Detection

### What is Implemented in Stage 4:
- **Core Intelligence Layer (100% Free & Local)**:
  - Fuses linguistic speech semantics, audio energy envelopes, and visual analysis without requiring any paid LLM/vision API keys.
- **Contextual Speech Windowing (`backend/clip_detection/contextual_window.py`)**:
  - Groups timed speech segments into coherent narrative windows targeting 15–45 seconds (optimal for 20–30s shorts).
  - Identifies distinct **Hook** (opening phrase) and **Payoff** (closing punchline/statement).
- **Audio Energy Profiling (`backend/audio/analyzer.py`)**:
  - Computes RMS volume and energy profiles over time, detecting laughter, excitement, and pauses.
- **Multimodal Scoring & Tagging (`backend/clip_detection/multimodal_scorer.py`)**:
  - Scores candidates on 7 dimensions:
    - `hook_strength`: Opening engagement factor
    - `humor`: Comedic timing, jokes, and punchlines
    - `surprise`: Unexpected statements and plot twists
    - `emotion`: Sentiments and intensity
    - `visual_interest`: Face presence, motion, and scene transitions
    - `context_completeness`: Standalone understandability
    - `social_potential`: Composite virality rating
  - Multi-tag categorization (`funny`, `reaction`, `insightful`, `surprising`, `storytelling`, `punchline`, `high_energy`, etc.).
- **Deduplication Engine (`backend/clip_detection/detector.py`)**:
  - Merges overlapping candidates using 1D temporal Intersection-over-Union (IoU) to guarantee unique moments.
- **Output Artifacts**:
  - `candidates/candidates.json`: Structured candidate data and scores.
  - `candidates/candidates.md`: Clean Markdown report for developers.
- **CLI Subcommand**:
  - `detect-moments`: Discovers and ranks candidate moments from existing project artifacts.
  - `process-video`: Now automatically executes Stages 1, 2, 3, and 4 in sequence.

---

## Stage 4 CLI Usage Examples

### 1. Detect Moments from Existing Project
```bash
python main.py detect-moments \
  --transcript ./projects/my_project_001/transcript/transcript.json \
  --audio ./projects/my_project_001/audio/audio.wav \
  --visual ./projects/my_project_001/analysis/visual_analysis.json \
  --output ./projects/my_project_001/candidates
```

### 2. Run Full Pipeline (Stages 1, 2, 3 & 4)
```bash
python main.py process-video \
  --input ./podcast_episode.mp4 \
  --output ./projects/podcast_001 \
  --model base \
  --strategy adaptive
```

Project workspace structure after Stage 4:
```text
projects/podcast_001/
├── video_metadata.json
├── pipeline.log
├── input/
│   └── podcast_episode.mp4
├── audio/
│   └── audio.wav
├── transcript/
│   ├── transcript.json
│   └── transcript.txt
├── frames/
│   ├── index.json
│   └── frame_00000*.jpg
├── analysis/
│   ├── scenes.json
│   └── visual_analysis.json
├── candidates/
│   ├── candidates.json
│   └── candidates.md
...
```



