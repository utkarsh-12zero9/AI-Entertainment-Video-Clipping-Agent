"""Unit and integration tests for transcription module."""

from pathlib import Path
import pytest

from backend.config.settings import PipelineSettings
from backend.models.transcript import TranscriptResult, TranscriptSegment, WordTimestamp
from backend.transcription.whisper_local import LocalWhisperTranscriber, TranscriptionError


def test_transcript_models_serialization():
    segment = TranscriptSegment(
        id=0,
        start=0.5,
        end=3.2,
        text="Hello world test",
        words=[
            WordTimestamp(word="Hello", start=0.5, end=1.0, probability=0.98),
            WordTimestamp(word="world", start=1.1, end=2.0, probability=0.95),
            WordTimestamp(word="test", start=2.1, end=3.2, probability=0.99),
        ]
    )
    result = TranscriptResult(
        language="en",
        duration=3.2,
        text="Hello world test",
        segments=[segment]
    )

    data = result.model_dump()
    assert data["language"] == "en"
    assert data["duration"] == 3.2
    assert len(data["segments"]) == 1
    assert len(data["segments"][0]["words"]) == 3
    assert data["segments"][0]["words"][0]["word"] == "Hello"


def test_transcription_missing_audio():
    transcriber = LocalWhisperTranscriber(settings=PipelineSettings(whisper_model_name="tiny"))
    with pytest.raises(TranscriptionError):
        transcriber.transcribe(Path("missing_file.wav"))


def test_local_whisper_transcription(tmp_path: Path):
    # Generate a small synthetic audio wave and transcribe it with tiny model
    import subprocess
    audio_wav = tmp_path / "speech_test.wav"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=2",
        "-ar", "16000", "-ac", "1",
        str(audio_wav)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    # Use the lightweight tiny model for fast test execution
    settings = PipelineSettings(whisper_model_name="tiny", whisper_device="cpu")
    transcriber = LocalWhisperTranscriber(settings=settings)
    result = transcriber.transcribe(audio_wav)

    assert isinstance(result, TranscriptResult)
    assert result.duration >= 1.8
