This is a strong multi-stage AI video agent / autonomous media-processing pipeline. The key is not to ask Antigravity to build the entire thing in one prompt. You want a staged implementation where each stage has explicit inputs, outputs, validation, and acceptance criteria.
I’d structure the project as:
Long Video → Multimodal Analysis → Candidate Moments → Scoring/Ranking → Clip Extraction → Clip QA → Vertical Editing → Captions → Thumbnail + Metadata → Export
Below is a curated prompt sequence you can give to OpenCode CLI.
________________________________________
1. Master Project Prompt
Start OpenCode with this first.
# AI Entertainment Video Clipping Agent

## Project Objective

Build a production-oriented AI agent that takes a long-form video containing both audio and visual frames and automatically converts it into multiple short-form social-media-ready clips.

The target use case is entertainment content such as:

- Podcasts
- Interviews
- Stand-up comedy
- Gaming videos
- Webinars with entertaining moments
- Conversations
- Shows
- Vlogs
- Reaction videos
- Long-form YouTube videos

The system should identify interesting, funny, emotional, surprising, controversial, informative, highly engaging, or otherwise attractive moments and turn them into polished 20–30 second vertical clips.

The system must NOT simply cut clips based on transcript keywords. It should perform multimodal analysis using:

1. Audio
2. Speech/transcript
3. Visual frames
4. Speaker/context information
5. Timing
6. Dialogue continuity
7. Semantic context
8. Entertainment/engagement signals

---


# Core Pipeline

The application should implement the following pipeline:

INPUT VIDEO
    ↓
Video Inspection
    ↓
Audio Extraction
    ↓
Speech-to-Text
    ↓
Transcript + Timestamp Generation
    ↓
Frame/Screenshot Sampling
    ↓
Multimodal Content Analysis
    ↓
Candidate Moment Detection
    ↓
Candidate Scoring
    ↓
Moment Ranking
    ↓
Clip Boundary Optimization
    ↓
Raw Clip Extraction
    ↓
Clip Quality Validation
    ↓
Vertical Video Conversion
    ↓
Smart Cropping / Speaker Framing
    ↓
Caption Generation
    ↓
Caption Styling
    ↓
Visual Enhancement
    ↓
Thumbnail Generation
    ↓
Title / Caption / Tags / Description Generation
    ↓
Final QA
    ↓
Export Organized Clips

---


# Important Engineering Principle

DO NOT implement everything at once.

Build the system incrementally.

Every stage must:

- Have a clear input
- Have a clear output
- Be independently testable
- Produce structured logs
- Fail gracefully
- Avoid unnecessary recomputation
- Store intermediate artifacts
- Be configurable
- Be deterministic where possible

The final system should behave like an AI agent orchestrating specialized tools rather than one giant function.

---


# Recommended Architecture

Use a modular architecture.

Suggested high-level components:

backend/
    agents/
    analyzers/
    audio/
    video/
    transcription/
    clip_detection/
    scoring/
    editing/
    captions/
    thumbnails/
    metadata/
    qa/
    pipeline/
    models/
    services/
    utils/

data/
    inputs/
    working/
    transcripts/
    frames/
    candidates/
    clips/
    thumbnails/
    metadata/
    final/

config/
tests/
scripts/
docs/

---


# Agent Architecture

Create specialized components/agents:

## 1. VideoAnalyzer

Responsibilities:

- Inspect video metadata
- Duration
- Resolution
- FPS
- Codec
- Audio tracks
- Aspect ratio
- Detect problematic input

## 2. AudioTranscriber

Responsibilities:

- Extract audio
- Transcribe speech
- Generate timestamps
- Preserve sentence/segment boundaries
- Support speaker information if available

## 3. VisualAnalyzer

Responsibilities:

- Sample frames intelligently
- Analyze visual changes
- Detect scene changes
- Detect faces/speakers where feasible
- Identify visually interesting moments
- Provide visual context for candidate clips

## 4. EntertainmentMomentDetector

Responsibilities:

- Analyze transcript + audio + visual signals
- Generate candidate moments
- Categorize moments

Possible categories:

- funny
- surprising
- emotional
- controversial
- shocking
- insightful
- wholesome
- dramatic
- relatable
- storytelling
- high_energy
- reaction
- debate
- punchline
- unexpected
- educational
- motivational

## 5. ClipRanker

Score candidates based on:

- Hook strength
- Entertainment value
- Emotional intensity
- Humor
- Surprise
- Context completeness
- Visual quality
- Audio quality
- Dialogue completeness
- Standalone understandability
- Social-media potential

Do not optimize purely for virality.

A clip should make sense without requiring the viewer to watch the original video.

## 6. ClipBoundaryOptimizer

Determine:

- Start timestamp
- End timestamp
- Hook
- Context
- Punchline/payoff
- Natural ending

Target duration:
20–30 seconds.

Allow configurable tolerance where necessary.

Avoid:

- Starting mid-sentence
- Ending mid-sentence
- Cutting immediately before a punchline
- Cutting immediately after a setup
- Awkward pauses
- Abrupt speaker transitions

## 7. ClipEditor

Responsibilities:

- Extract selected clip
- Convert to vertical format
- Smart crop
- Preserve important subjects
- Add captions
- Apply visual enhancement
- Maintain audio quality

Default target:

9:16 vertical video.

Recommended output:
1080 × 1920.

## 8. CaptionEngine

Generate timed captions.

Captions should:

- Be synchronized with speech
- Be easy to read on mobile
- Avoid covering important faces
- Use short readable chunks
- Highlight important words
- Support attractive social-media styling

Caption styles must be configurable.

## 9. ThumbnailGenerator

Generate a thumbnail for every clip.

Use:

- Strong frame selection
- Face/emotion when available
- Short readable text
- High contrast
- Clear visual hierarchy

## 10. MetadataGenerator

Generate separately for every clip:

- Title
- Social media caption
- Description
- Hashtags
- Tags
- Keywords
- Suggested CTA

Metadata should be platform-aware.

Potential platforms:

- YouTube Shorts
- Instagram Reels
- TikTok
- Facebook Reels

Do not use the exact same metadata blindly across all platforms.

## 11. QualityAssuranceAgent

Before final export, verify:

- Duration
- Audio exists
- Video exists
- Captions exist
- No corrupted frames
- No abrupt beginning
- No abrupt ending
- Caption synchronization
- Correct aspect ratio
- No important face cropped
- No excessive dead air
- No duplicate clips
- Metadata exists
- Thumbnail exists

If a clip fails QA, send it back to the appropriate processing stage instead of exporting it.

---


# Data Model

Create structured models for:

VideoMetadata
TranscriptSegment
FrameAnalysis
CandidateMoment
ClipScore
ClipBoundary
ClipMetadata
QAResult
ProcessingJob

CandidateMoment should contain fields similar to:

{
    "id": "...",
    "start_time": 0.0,
    "end_time": 25.0,
    "category": "funny",
    "reason": "...",
    "transcript": "...",
    "hook": "...",
    "payoff": "...",
    "confidence": 0.0,
    "scores": {
        "humor": 0.0,
        "emotion": 0.0,
        "surprise": 0.0,
        "hook_strength": 0.0,
        "visual_quality": 0.0,
        "context_completeness": 0.0,
        "social_potential": 0.0
    }
}

---


# Folder Organization

For every source video, create a dedicated project directory.

Example:

projects/
    source_video_001/
        input/
        audio/
        transcript/
        frames/
        analysis/
        candidates/
        selected/
        raw_clips/
        edited_clips/
        captions/
        thumbnails/
        metadata/
        qa/
        final/

Categories should also be represented in the output where appropriate.

Example:

final/
    funny/
    emotional/
    surprising/
    insightful/
    dramatic/

Each clip should have consistent naming.

Example:

funny_001.mp4
funny_002.mp4
surprising_001.mp4

---


# Configuration

Do not hardcode important values.

Create configuration for:

- Minimum clip duration
- Maximum clip duration
- Target resolution
- Target aspect ratio
- Caption style
- Number of clips
- Minimum candidate score
- Frame sampling rate
- Audio analysis settings
- LLM model
- Vision model
- Transcription model
- Output formats
- Platform metadata settings

Example:

MIN_CLIP_DURATION=20
MAX_CLIP_DURATION=30
TARGET_WIDTH=1080
TARGET_HEIGHT=1920
TARGET_ASPECT_RATIO=9:16

---


# Important Constraint

The system should prioritize QUALITY over quantity.

It is better to produce:

8 excellent clips

than:

40 mediocre clips.

Avoid duplicate or near-duplicate moments.

---


# Implementation Strategy

Implement the system in stages.

DO NOT move to the next stage until the previous stage is functional and testable.

Each stage must include:

1. Implementation
2. Unit tests
3. Integration test
4. Example command
5. README documentation
6. Error handling
7. Logging
8. Sample output

At every stage, inspect the existing codebase before making changes.

Do not unnecessarily rewrite working code.

Do not introduce libraries without explaining why they are needed.

Prefer mature, production-tested tools.

---


# Final Goal

The final application should allow something conceptually similar to:

python main.py process \
    --input ./video.mp4 \
    --output ./projects/video_001

and automatically execute the complete pipeline.

Also provide a way to execute individual stages independently.

For example:

python main.py analyze
python main.py detect-moments
python main.py extract-clips
python main.py edit
python main.py generate-metadata
python main.py qa
python main.py process

The architecture must allow individual stages to be rerun without repeating expensive previous operations.

---


# Development Rule

Start by implementing ONLY the project foundation and Stage 1.

Do not implement the entire system yet.

After completing Stage 1:

- Run tests
- Verify outputs
- Document what was implemented
- Explain what should be built next

Then wait for the next stage instruction.
________________________________________
2. Stage 1 — Project Foundation + Video Ingestion
Give this after the master prompt.
# Stage 1 — Project Foundation + Video Ingestion

Implement ONLY Stage 1.

Do not implement AI moment detection, captions, thumbnails, or final editing yet.

## Objective

Create the foundational project architecture and implement robust video ingestion and inspection.

## Requirements

Create:

1. Project structure
2. Configuration system
3. Logging
4. Error handling
5. Video metadata extraction
6. Job/project directory creation
7. CLI foundation
8. Input validation
9. Basic tests

Use FFmpeg/FFprobe or an equivalent mature video-processing tool.

## Video Metadata

Extract:

- filename
- duration
- width
- height
- FPS
- codec
- bitrate
- audio presence
- audio codec
- sample rate
- channels
- aspect ratio
- file size

## Validation

Reject or clearly report:

- Missing file
- Unsupported file
- Corrupted video
- Video without usable audio
- Invalid metadata
- Extremely short videos

Do not silently continue after critical errors.

## CLI

Implement:

process-video --input video.mp4 --output ./projects/video_001

and:

analyze-video --input video.mp4

## Output

Generate:

video_metadata.json

Example:

{
    "duration": 3600.2,
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "has_audio": true,
    "audio_codec": "aac",
    "sample_rate": 48000,
    "channels": 2,
    "aspect_ratio": "16:9"
}

## Testing

Create tests for:

- Valid video
- Missing video
- Invalid video
- Metadata extraction
- Project directory creation
- CLI arguments

## Completion Criteria

Do not proceed beyond Stage 1.

At the end provide:

1. Files created
2. Dependencies added
3. Commands to run
4. Test results
5. Example metadata output
6. Known limitations

Then stop.
________________________________________
3. Stage 2 — Audio + Transcription
# Stage 2 — Audio Extraction + Transcription

Build on the existing Stage 1 implementation.

Do not modify unrelated working components.

## Objective

Extract audio and generate a timestamped transcript suitable for precise clip detection.

## Requirements

Implement:

### AudioExtractor

Extract high-quality audio from the source video.

Store:

audio/audio.wav

Use an appropriate format for speech recognition.

### Transcriber

Integrate a high-quality speech-to-text system.

The implementation should support a configurable transcription backend.

The transcript must preserve timestamps.

Prefer segment-level and, when available, word-level timestamps.

Example:

{
    "start": 124.25,
    "end": 128.72,
    "text": "I genuinely thought that was going to work."
}

## Optional Speaker Diarization

Design the architecture so speaker diarization can be added.

If the selected transcription backend supports it, expose speaker information.

Example:

{
    "speaker": "SPEAKER_01",
    "start": 124.25,
    "end": 128.72,
    "text": "..."
}

## Output

Create:

transcript/transcript.json
transcript/transcript.txt

## Important

Do not send the entire video directly to an LLM for analysis.

The transcript must become a reusable intermediate artifact.

## Testing

Test:

- Audio extraction
- Transcription
- Timestamp validity
- Transcript serialization
- Empty/invalid audio
- Long videos

## Completion Criteria

Run the complete pipeline:

video → audio → transcript

Verify timestamps against the source video.

Document the exact commands and output.

Then stop.
________________________________________
4. Stage 3 — Visual Frame Analysis
This stage is important because your requirement is genuinely multimodal, rather than transcript-only.
# Stage 3 — Visual Frame Sampling + Analysis

Build on the existing pipeline.

## Objective

Analyze the visual component of the video and generate reusable visual information for candidate moment detection.

## Requirements

Implement intelligent frame sampling.

Do NOT blindly extract every frame.

Support multiple sampling strategies:

1. Fixed interval
2. Scene-change based
3. Adaptive sampling

The architecture should allow future replacement of the sampling strategy.

## Frame Extraction

For long videos, extract representative frames at configurable intervals.

Store:

frames/
    frame_000001.jpg
    frame_000002.jpg
    ...

Each frame must have timestamp metadata.

Example:

{
    "frame": "frame_000001.jpg",
    "timestamp": 125.4
}

## Visual Analysis

Integrate a configurable vision-capable model.

For sampled frames, analyze:

- Number of visible people
- Faces
- Approximate facial expressions
- Important objects
- Scene type
- Visual activity
- Camera changes
- Text appearing on screen
- Reactions
- Visually interesting events

Do not make unsupported claims from a single frame.

Visual analysis should include confidence.

## Scene Detection

Implement scene/shot boundary detection where practical.

Represent scenes as:

{
    "start": 120.0,
    "end": 138.4
}

## Output

Create:

frames/index.json
analysis/visual_analysis.json
analysis/scenes.json

## Performance

Do not unnecessarily send hundreds of frames individually to an LLM.

Design batching/caching mechanisms.

## Completion Criteria

Demonstrate:

video
→ sampled frames
→ timestamps
→ scene information
→ visual analysis

Add tests and documentation.

Stop after Stage 3.
________________________________________
5. Stage 4 — The Core: Entertainment Moment Detection
This is where the project becomes an actual AI clipping agent.
# Stage 4 — Multimodal Entertainment Moment Detection

This is the core intelligence layer.

Use the existing:

- Transcript
- Timestamped speech
- Audio information
- Scene boundaries
- Visual analysis

to discover candidate short-form moments.

## Objective

Identify moments that could perform well as entertainment-oriented short-form content.

Do NOT simply search for keywords.

The model must reason about context.

## Candidate Categories

Support:

- funny
- punchline
- surprising
- shocking
- emotional
- controversial
- dramatic
- insightful
- relatable
- wholesome
- storytelling
- reaction
- debate
- unexpected
- high_energy
- motivational

Allow multiple categories for a candidate.

## Candidate Detection

Analyze the transcript in contextual windows.

A candidate should generally contain:

HOOK
+
CONTEXT
+
PAYOFF

Avoid candidates where the viewer cannot understand what is happening.

## Signals

Evaluate:

### Audio

- Energy
- Loudness changes
- Pauses
- Laughter
- Excitement
- Emotional intensity

### Transcript

- Punchlines
- Surprising statements
- Strong opinions
- Stories
- Questions
- Unexpected answers
- Emotional statements
- Humor
- Narrative payoff

### Visual

- Facial reactions
- Scene changes
- Physical reactions
- Multiple speakers
- Visual surprises
- High activity

## Candidate Schema

Create:

{
    "id": "candidate_001",
    "start_time": 512.2,
    "end_time": 539.7,
    "categories": ["funny", "reaction"],
    "transcript": "...",
    "hook": "...",
    "payoff": "...",
    "reason": "...",
    "confidence": 0.91,
    "scores": {
        "hook_strength": 0.92,
        "humor": 0.95,
        "surprise": 0.62,
        "emotion": 0.48,
        "visual_interest": 0.83,
        "context_completeness": 0.94,
        "social_potential": 0.91
    }
}

## Important

Do not select moments solely because they contain:

"funny"
"haha"
"amazing"
"wow"
"crazy"

The system must understand semantic context.

## Duplicate Detection

Candidates covering essentially the same moment must be merged or deduplicated.

## Output

Create:

candidates/candidates.json

and a human-readable:

candidates/candidates.md

The markdown should allow a developer to quickly inspect:

- timestamp
- category
- transcript
- reason
- score

## Completion Criteria

Run the detector against a real sample video.

Produce multiple candidate moments.

Verify manually that the candidates are semantically meaningful.

Do not yet perform final clip editing.

Stop after this stage.
________________________________________
6. Stage 5 — Candidate Ranking + Boundary Optimization
This stage prevents the classic AI clipping problem:
“Technically 25 seconds, but it starts in the middle of a sentence and ends awkwardly.”
# Stage 5 — Clip Ranking + Boundary Optimization

Build on the candidate detection system.

## Objective

Turn raw candidate moments into high-quality clip specifications.

## Duration

Target:

20–30 seconds.

Prefer approximately 25 seconds when possible.

However, semantic completeness takes priority over an arbitrary timestamp.

## Boundary Optimization

For each candidate:

1. Find natural sentence start
2. Include sufficient context
3. Preserve setup
4. Preserve punchline/payoff
5. Include reaction when useful
6. End at a natural linguistic/visual boundary

Avoid:

- Mid-word cuts
- Mid-sentence cuts
- Abrupt speaker changes
- Cutting off laughter
- Cutting before punchline
- Excessive silence
- Beginning with unexplained pronouns such as "he", "they", "that"
- Ending immediately before a conclusion

## Ranking

Calculate an overall score.

Suggested conceptual weighting:

Hook: 20%
Entertainment: 20%
Standalone context: 15%
Payoff: 15%
Emotional impact: 10%
Visual interest: 10%
Audio quality: 5%
Uniqueness: 5%

Keep weights configurable.

## Clip Specification

Create:

{
    "clip_id": "funny_001",
    "start_time": 512.8,
    "end_time": 538.9,
    "duration": 26.1,
    "category": "funny",
    "score": 0.91,
    "reason": "...",
    "hook": "...",
    "payoff": "...",
    "transcript": "..."
}

## Diversity

Do not select 10 clips from the same 2-minute section.

Apply temporal diversity.

Avoid near-duplicate clips.

## Output

Create:

selected/selected_clips.json

Sort clips by quality score.

Allow configuration such as:

--max-clips 10

## Completion Criteria

Generate a ranked list of final clip specifications.

Do not yet add captions or thumbnails.

Stop after this stage.
________________________________________
7. Stage 6 — Raw Clip Extraction + Automated QA
# Stage 6 — Raw Clip Extraction + Automated QA

## Objective

Extract the selected clips from the original video and verify their technical integrity.

## Requirements

For every selected clip:

1. Extract using FFmpeg
2. Preserve high-quality audio
3. Preserve video quality
4. Verify duration
5. Verify audio stream
6. Verify video stream

Output:

raw_clips/
    funny/
    emotional/
    surprising/
    ...

## Clip Validation

For each generated clip check:

- Duration
- Resolution
- FPS
- Audio presence
- Audio/video synchronization
- Corruption
- Black frames
- Excessive silence
- Invalid timestamps

## Generate QA result

Example:

{
    "clip_id": "funny_001",
    "passed": true,
    "checks": {
        "duration": true,
        "audio": true,
        "video": true,
        "sync": true,
        "corruption": false
    }
}

## Important

A technically valid clip is NOT necessarily a good clip.

This stage only validates technical correctness.

Semantic editing QA will happen later.

## Completion Criteria

All selected candidates should produce valid raw clips.

Add tests.

Stop.
________________________________________
8. Stage 7 — Vertical Social Media Editing
# Stage 7 — Vertical Social Media Editing

Now transform raw clips into social-media-ready videos.

## Target

Default:

1080 × 1920
9:16
vertical

## Smart Reframing

Do NOT simply resize the original 16:9 video.

Implement intelligent cropping.

Prioritize:

1. Active speaker
2. Face
3. Multiple speakers
4. Important visual object

The architecture should support:

- Center crop
- Face-aware crop
- Speaker-aware crop
- Dynamic horizontal movement

## Editing

Add configurable:

- Slight contrast enhancement
- Mild sharpening
- Exposure correction where appropriate
- Noise reduction where appropriate
- Audio normalization
- Subtle visual enhancement

Do NOT over-process the video.

Avoid gimmicky effects by default.

## Audio

Normalize audio to a suitable social-media level.

Prevent clipping.

Maintain speech clarity.

## Output

edited_clips/

Each clip should retain its category and clip ID.

Example:

edited_clips/funny/funny_001.mp4

## Completion Criteria

Generate mobile-friendly clips.

Verify:

- 9:16
- Correct resolution
- Audio/video sync
- No important face cut off
- No black borders
- No unintended stretching

Stop after this stage.
________________________________________
9. Stage 8 — Captions
# Stage 8 — Caption Engine

## Objective

Add accurate, attractive, mobile-friendly captions.

## Requirements

Use word-level timestamps when available.

Captions must remain synchronized with speech.

## Caption Design

Support multiple configurable styles.

Example styles:

1. Clean
2. Bold
3. Highlighted keywords
4. Karaoke-style
5. Minimal
6. Entertainment

Default style should be attractive but not excessive.

## Rules

Captions should:

- Use short chunks
- Be readable on mobile
- Avoid covering faces
- Stay within safe areas
- Have sufficient contrast
- Highlight important words when appropriate
- Avoid excessive words per line

## Dynamic Positioning

Where possible, position captions away from:

- Faces
- Important UI
- Important visual content

## Caption QA

Verify:

- No missing words
- No severe timestamp drift
- No captions appearing too early
- No captions appearing too late
- No overlapping caption segments

## Output

Generate:

captions/
    funny_001.srt

and rendered:

edited_clips_with_captions/

## Completion Criteria

Review several generated clips visually.

Caption timing must align naturally with speech.

Stop after this stage.
________________________________________
10. Stage 9 — Thumbnail + Social Metadata Agent
# Stage 9 — Thumbnail + Metadata Generation

## Objective

For every final clip generate platform-ready metadata.

## Thumbnail

Select the strongest frame from the clip.

Consider:

- Facial expression
- Emotion
- Visual clarity
- Composition
- Contrast
- Context

Generate thumbnail text where appropriate.

Keep thumbnail text short.

Avoid covering faces.

Output:

thumbnails/
    funny_001.jpg

## Title

Generate several candidate titles internally and select the strongest one.

Titles should be:

- Short
- Curiosity-driven
- Accurate
- Entertainment-focused
- Not misleading

## Social Caption

Generate platform-specific captions.

## Description

Generate a concise description.

## Tags

Generate:

- hashtags
- keywords
- searchable tags

Avoid irrelevant tags.

## CTA

Optionally generate a suitable engagement CTA.

Examples:

- What would you do?
- Agree or disagree?
- Would you have reacted the same way?

Do not force a CTA into every clip.

## Platform Metadata

Generate separately for:

YouTube Shorts
Instagram Reels
TikTok
Facebook Reels

Do not blindly copy the same text to every platform.

## Output

Create:

metadata/
    funny_001.json

Example:

{
    "clip_id": "funny_001",
    "category": "funny",
    "title": "...",
    "caption": "...",
    "description": "...",
    "hashtags": [],
    "keywords": [],
    "platforms": {
        "youtube_shorts": {},
        "instagram_reels": {},
        "tiktok": {},
        "facebook_reels": {}
    }
}

Stop after this stage.
________________________________________
11. Stage 10 — Final Multimodal QA Agent
This is very important. Don’t skip it.
# Stage 10 — Final Multimodal QA Agent

## Objective

Build a final QA agent that reviews the generated clips before export.

The QA agent must evaluate the actual generated video, not just metadata.

## Check Technical Quality

Verify:

- Video opens successfully
- Correct duration
- 9:16 aspect ratio
- Correct resolution
- Audio exists
- Audio/video synchronization
- No corrupted frames
- No black frames
- No severe compression artifacts

## Check Semantic Quality

Analyze:

- Does the clip make sense independently?
- Does the opening provide enough context?
- Is the ending natural?
- Is the punchline/payoff preserved?
- Is the clip actually interesting?
- Are captions accurate?
- Are captions synchronized?
- Are faces cropped incorrectly?
- Is important visual information hidden?
- Is there excessive dead air?

## Abrupt Cut Detection

Explicitly inspect:

START:

- Does it begin naturally?
- Is the first spoken word complete?
- Does it start too suddenly?

END:

- Is the sentence complete?
- Is the reaction complete?
- Is the punchline preserved?

## Score

Generate:

{
    "clip_id": "funny_001",
    "overall_score": 0.91,
    "passed": true,
    "issues": [],
    "recommendations": []
}

## Failure Handling

If QA fails:

Do not simply delete the clip.

Return a structured repair recommendation:

{
    "action": "RETRIM",
    "new_start": 511.9,
    "new_end": 539.4
}

or:

{
    "action": "REPOSITION_CAPTIONS"
}

or:

{
    "action": "REGENERATE"
}

The pipeline should be able to send the clip back to the appropriate stage.

## Completion Criteria

Only clips passing final QA should enter:

final/

Generate:

qa/final_report.json

Stop after this stage.
________________________________________
12. Stage 11 — Orchestrator / Actual AI Agent
Only after all previous stages work individually should you give OpenCode this.
# Stage 11 — End-to-End AI Video Clipping Agent

All individual pipeline stages now exist.

Build the orchestration layer.

## Objective

Create one agent capable of executing the complete workflow:

INPUT VIDEO
→ INSPECT
→ TRANSCRIBE
→ ANALYZE FRAMES
→ DETECT MOMENTS
→ RANK
→ OPTIMIZE BOUNDARIES
→ EXTRACT
→ EDIT
→ CAPTION
→ THUMBNAIL
→ METADATA
→ QA
→ EXPORT

## Agent Behavior

The orchestrator must maintain state.

It must know:

- What stage has completed
- What artifacts exist
- What failed
- What needs retrying
- What can be reused

Do not rerun expensive operations unnecessarily.

Example:

If transcription already exists:

Do not transcribe again.

If frame analysis already exists:

Do not repeat it.

## Job State

Maintain something similar to:

{
    "job_id": "...",
    "status": "processing",
    "stages": {
        "ingestion": "completed",
        "transcription": "completed",
        "visual_analysis": "completed",
        "moment_detection": "completed",
        "ranking": "completed",
        "extraction": "processing",
        "editing": "pending",
        "captioning": "pending",
        "metadata": "pending",
        "qa": "pending"
    }
}

## Retry

A failed stage should be retryable independently.

Example:

process --resume JOB_ID

or:

process --stage captioning JOB_ID

## Parallelism

Where safe, process independent clips concurrently.

For example:

clip_001
clip_002
clip_003

can be edited independently.

But do not create uncontrolled parallelism that consumes all CPU/GPU resources.

Use configurable worker limits.

## Human Review

Add an optional review mode.

Before expensive final rendering, allow:

review candidates

which displays:

- Clip ID
- Category
- Start/end
- Transcript
- Score
- Reason

The user can approve/reject candidates.

Optional:

--auto-approve

## Final Output

For each clip:

final/
    funny/
        funny_001.mp4
        funny_001.jpg
        funny_001.json

The JSON should contain all relevant metadata.

## Final CLI

Support:

agent process --input video.mp4

agent analyze --input video.mp4

agent detect-moments --job JOB_ID

agent review --job JOB_ID

agent render --job JOB_ID

agent qa --job JOB_ID

agent export --job JOB_ID

agent resume --job JOB_ID

## Important

The system must be modular.

Do not turn the orchestrator into a giant monolithic file.

Each stage should remain independently testable.

## Completion Criteria

Run an actual end-to-end test using a real long-form video.

Measure:

- Processing time
- Number of candidates
- Number selected
- Number rejected by QA
- Number exported
- Failure rate

Produce an end-to-end report.

Stop after implementation and testing.
________________________________________
13. Stage 12 — Production Optimization
Once the agent works, give it this final prompt.
# Stage 12 — Production Optimization

The complete AI video clipping agent is functional.

Now optimize it for production-quality entertainment clipping.

Do not rewrite working components unnecessarily.

## 1. Performance

Profile:

- Transcription
- Frame extraction
- Vision analysis
- LLM calls
- FFmpeg processing
- Caption rendering

Identify bottlenecks.

Implement:

- caching
- batching
- concurrency
- incremental processing
- artifact reuse

## 2. Cost Optimization

Avoid unnecessary LLM/vision calls.

Use a funnel:

CHEAP SIGNALS
↓
Candidate Detection
↓
HIGH-VALUE CANDIDATES
↓
EXPENSIVE MULTIMODAL ANALYSIS
↓
FINAL QA

Do not send every frame of a one-hour video to an expensive vision model.

## 3. Entertainment Ranking

Improve ranking so the system prefers moments with:

- Strong first 1–3 seconds
- Clear premise
- Escalation
- Emotional change
- Surprise
- Punchline
- Reaction
- Payoff
- Standalone context

## 4. Hook Optimization

Where possible, detect whether the clip begins strongly.

If the strongest hook occurs later in the moment, investigate whether the clip can begin earlier/later without destroying narrative context.

Never rearrange dialogue unnaturally.

## 5. Duplicate Prevention

Use semantic similarity to prevent:

- duplicate clips
- near-duplicate clips
- same joke appearing multiple times
- multiple clips from the same exact moment

## 6. Diversity

Ensure final output contains a mixture of categories when available.

For example:

3 funny
2 surprising
2 emotional
1 insightful
1 reaction

instead of:

9 funny clips from the same section.

Make this configurable.

## 7. Human-in-the-loop

Provide optional review interfaces or structured candidate review.

The user should be able to:

- approve
- reject
- change timestamps
- change category
- regenerate metadata
- rerender captions

## 8. Observability

Every job should record:

- Processing duration
- Model calls
- Errors
- Retries
- Token usage where available
- Generated clips
- Rejected clips
- QA failures

## 9. Configuration

Move all tunable parameters into configuration.

Do not hardcode:

- models
- thresholds
- durations
- caption styles
- output resolution
- scoring weights
- worker count

## 10. Final Quality Goal

The final system should behave less like:

"AI automatically cuts random 25-second sections"

and more like:

"An AI video editor watches and understands the content, identifies the strongest entertainment moments, creates coherent short-form narratives, edits them for mobile viewing, and validates the final result."

## Final Deliverable

Provide:

1. Production-ready architecture
2. Complete documentation
3. Setup instructions
4. Environment configuration
5. CLI documentation
6. Test suite
7. Example pipeline
8. Troubleshooting guide
9. Performance report
10. Known limitations
________________________________________
One architectural recommendation I’d strongly make
Don’t build this as one LLM agent with 20 tools.
Build it as a pipeline of specialized agents/services with structured artifacts:
                    ┌──────────────────┐
                    │   Input Video    │
                    └────────┬─────────┘
                             ↓
                    ┌──────────────────┐
                    │ Video Inspector  │
                    └────────┬─────────┘
                             ↓
              ┌──────────────┴──────────────┐
              ↓                             ↓
       ┌─────────────┐              ┌─────────────┐
       │ Transcriber │              │Frame Analyzer│
       └──────┬──────┘              └──────┬──────┘
              ↓                            ↓
              └──────────────┬─────────────┘
                             ↓
                  ┌─────────────────────┐
                  │ Multimodal Analyzer │
                  └──────────┬──────────┘
                             ↓
                  ┌─────────────────────┐
                  │ Moment Detector     │
                  └──────────┬──────────┘
                             ↓
                  ┌─────────────────────┐
                  │ Rank + Deduplicate  │
                  └──────────┬──────────┘
                             ↓
                  ┌─────────────────────┐
                  │ Boundary Optimizer  │
                  └──────────┬──────────┘
                             ↓
                  ┌─────────────────────┐
                  │ Clip Extractor      │
                  └──────────┬──────────┘
                             ↓
                  ┌─────────────────────┐
                  │ Vertical Editor     │
                  └──────────┬──────────┘
                             ↓
              ┌──────────────┴──────────────┐
              ↓                             ↓
       ┌─────────────┐              ┌─────────────┐
       │ Caption AI  │              │ Thumbnail AI│
       └──────┬──────┘              └──────┬──────┘
              └──────────────┬─────────────┘
                             ↓
                    ┌────────────────┐
                    │ Metadata Agent │
                    └───────┬────────┘
                            ↓
                    ┌────────────────┐
                    │ Multimodal QA  │
                    └───────┬────────┘
                            ↓
                       ┌──────────┐
                       │  FINAL   │
                       └──────────┘
The most important design decision
Make every stage produce a persistent structured artifact.
For example:
video_metadata.json
        ↓
transcript.json
        ↓
visual_analysis.json
        ↓
candidates.json
        ↓
selected_clips.json
        ↓
clip_manifest.json
        ↓
qa_report.json
        ↓
final_metadata.json
That gives you three huge advantages:
1.	You can debug the AI’s decisions.
2.	You don’t have to rerun expensive models.
3.	You can eventually replace individual models without rebuilding the entire system.
And for an entertainment-focused system, I’d make Stage 4 (moment detection), Stage 5 (boundary optimization), and Stage 10 (final multimodal QA) the highest-quality parts of the system. Those three determine whether this feels like a genuine AI editor or just an automated FFmpeg clipping script.
