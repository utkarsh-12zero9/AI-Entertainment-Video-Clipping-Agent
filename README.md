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

---

## Current Status: Stage 5 — Candidate Ranking + Boundary Optimization

### What is Implemented in Stage 5:
- **Linguistic Boundary Optimization (`backend/clip_detection/boundary_optimizer.py`)**:
  - Eliminates awkward cutoffs, mid-word splices, and mid-sentence breaks.
  - Snaps clip start times to natural speech segment beginnings.
  - **Dangling Pronoun Resolution**: Checks whether the clip begins with unexplained pronouns (`he`, `she`, `it`, `they`, `that`, `this`); if so, automatically includes preceding context without exceeding maximum duration.
  - **Payoff & Reaction Preservation**: Snaps clip end times to sentence termination + `0.35s` natural audio breathing room for laughter and reaction.
  - Enforces the target 20–30s short-form duration sweet spot (default ~25s).
- **Weighted Multimodal Ranking (`backend/scoring/ranker.py`)**:
  - Ranks candidates across 8 weighted criteria:
    - Hook: 20%
    - Entertainment / Humor: 20%
    - Standalone Context: 15%
    - Payoff: 15%
    - Emotional Impact: 10%
    - Visual Interest: 10%
    - Audio Quality: 5%
    - Uniqueness: 5%
- **Temporal Diversity Enforcement**:
  - Prevents clustering of clips from the same segment of the video using configurable temporal spacing (`min_clip_spacing_sec`).
- **Category-Prefixed Clip Identification**:
  - Automatically generates standard category-named IDs: `funny_001`, `emotional_001`, `surprising_001`, etc.
- **Output Artifact**:
  - `selected/selected_clips.json`: Complete, production-ready clip specifications ready for video rendering.
- **CLI Commands**:
  - `rank-clips`: Ranks candidates from `candidates.json` and generates `selected_clips.json`.
  - `process-video`: Executes Stages 1 through 5 seamlessly.

---

## Stage 5 CLI Usage Examples

### 1. Rank & Optimize Clips from Existing Project
```bash
python main.py rank-clips \
  --candidates ./projects/podcast_001/candidates/candidates.json \
  --transcript ./projects/podcast_001/transcript/transcript.json \
  --output ./projects/podcast_001/selected/selected_clips.json \
  --max-clips 8 \
  --min-spacing 15.0
```

### 2. Run Full Pipeline (Stages 1 through 5)
```bash
python main.py process-video \
  --input ./podcast_episode.mp4 \
  --output ./projects/podcast_001 \
  --model base \
  --max-clips 8
```

Project workspace structure after Stage 5:
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
├── selected/
│   └── selected_clips.json
```

---

## Current Status: Stage 6 — Raw Clip Extraction + Automated Quality Assurance (QA)

### What is Implemented in Stage 6:
- **Keyframe-Accurate Raw Clip Extraction (`backend/video/clip_extractor.py`)**:
  - Uses FFmpeg input seeking with libx264 re-encoding (`-ss <start> -i <source> -t <duration> -c:v libx264 -crf 18 -preset fast -c:a aac -b:a 192k`).
  - Preserves audio/video synchronization with `-avoid_negative_ts make_zero`.
  - Organizes output into category-prefixed subdirectories (`raw_clips/<category>/<output_filename>`).
- **Automated Multi-Point Quality Assurance (`backend/qa/clip_validator.py`)**:
  - **Duration Tolerance Verification**: Verifies clip duration matches specification within $\pm 0.75$s tolerance.
  - **Stream Integrity**: Confirms presence and non-corruption of both video and audio streams.
  - **Audio/Video Stream Synchronization**: Checks stream start offsets and drift between audio and video packets.
  - **Excessive Silence Detection**: Evaluates FFmpeg `silencedetect` filter to catch dead audio gaps exceeding 4.0s.
  - **Black Frame Detection**: Evaluates FFmpeg `blackdetect` filter to catch black screen anomalies.
- **QA Artifacts & Logging**:
  - Automatically exports comprehensive per-clip checks and overall pass/fail status to `qa/clip_qa_report.json`.
- **CLI Commands**:
  - `extract-clips`: Extracts raw clips from source video according to `selected_clips.json`.
  - `qa-clips`: Runs automated QA on extracted raw clips.
  - `process-video`: Executes full multi-stage pipeline across all Stages 1 through 6 seamlessly.

---

## Stage 6 CLI Usage Examples

### 1. Extract Raw Clips from Existing Project
```bash
python main.py extract-clips \
  --input ./podcast_episode.mp4 \
  --selected ./projects/podcast_001/selected/selected_clips.json \
  --output ./projects/podcast_001 \
  --crf 18 \
  --preset fast
```

### 2. Run Automated QA Validation on Extracted Clips
```bash
python main.py qa-clips \
  --project-dir ./projects/podcast_001 \
  --selected ./projects/podcast_001/selected/selected_clips.json \
  --duration-tolerance 0.75 \
  --max-silence 4.0
```

### 3. Run Full Pipeline (Stages 1 through 6)
```bash
python main.py process-video \
  --input ./podcast_episode.mp4 \
  --output ./projects/podcast_001 \
  --model base \
  --max-clips 8
```

Project workspace structure after Stage 6:
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
├── selected/
│   └── selected_clips.json
├── raw_clips/
│   ├── funny/
│   │   └── funny_001.mp4
│   ├── storytelling/
│   │   └── storytelling_002.mp4
│   └── surprising/
│       └── surprising_003.mp4
└── qa/
    └── clip_qa_report.json
```

---

## Current Status: Stage 7 — Vertical Social Media Editing

### What is Implemented in Stage 7:
- **Intelligent 9:16 Smart Reframing (`backend/video/smart_cropper.py`)**:
  - Automatically converts horizontal clips to mobile-first **1080 × 1920 (9:16)** vertical format without distortion or blind center cuts.
  - **Speaker & Face-Aware Cropping**: Utilizes local OpenCV Haar face cascade analysis to compute the median horizontal focus anchor ($X_{center}$) across sampled frames.
  - **Balanced Fallback**: When no faces are present, applies clean, mathematical center-cropping ($X = \frac{W_{scaled} - 1080}{2}$).
  - Guaranteed zero black letterboxing and zero pixel stretching.
- **Subtle Visual Enhancements & EBU R128 Audio Normalization (`backend/video/clip_editor.py`)**:
  - **Visual Enhancement**: Applies mild unsharp detail filtering (`unsharp=5:5:0.5:5:5:0.0`) for crisp mobile display.
  - **Audio Normalization**: Applies EBU R128 standard loudness normalization (`loudnorm=I=-14:LRA=11:TP=-1.5`) tailored for platforms like TikTok, Instagram Reels, and YouTube Shorts.
- **Categorized Folder Organization**:
  - Outputs rendered vertical videos directly into categorized folders: `edited_clips/<category>/<clip_id>.mp4`.
  - Serializes full edit telemetry to `analysis/edit_report.json`.
- **CLI Commands**:
  - `edit-clips`: Reframes raw clips into vertical social-media-ready videos.
  - `process-video`: Executes Stages 1 through 7 seamlessly in an end-to-end pipeline.

---

## Stage 7 CLI Usage Examples

### 1. Reframe Raw Clips to Vertical 9:16
```bash
python main.py edit-clips \
  --project-dir ./projects/podcast_001 \
  --selected ./projects/podcast_001/selected/selected_clips.json \
  --strategy smart_face \
  --loudness -14.0
```

### 2. Run Full Pipeline (Stages 1 through 7)
```bash
python main.py process-video \
  --input ./podcast_episode.mp4 \
  --output ./projects/podcast_001 \
  --model base \
  --max-clips 8
```

Project workspace structure after Stage 7:
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
│   ├── visual_analysis.json
│   └── edit_report.json
├── candidates/
│   ├── candidates.json
│   └── candidates.md
├── selected/
│   └── selected_clips.json
├── raw_clips/
│   ├── funny/
│   │   └── funny_001.mp4
│   ├── storytelling/
│   │   └── storytelling_002.mp4
│   └── surprising/
│       └── surprising_003.mp4
├── edited_clips/
│   ├── funny/
│   │   └── funny_001.mp4
│   ├── storytelling/
│   │   └── storytelling_002.mp4
│   └── surprising/
│       └── surprising_003.mp4
└── qa/
    └── clip_qa_report.json
```






