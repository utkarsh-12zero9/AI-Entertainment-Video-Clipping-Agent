"""CLI integration tests."""

import json
import subprocess
import sys
from pathlib import Path


def test_cli_analyze_video(valid_video_path: Path):
    cmd = [
        sys.executable,
        "main.py",
        "analyze-video",
        "--input", str(valid_video_path),
        "--json"
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["width"] == 1280
    assert data["height"] == 720
    assert data["has_audio"] is True


def test_cli_process_video(valid_video_path: Path, tmp_path: Path):
    out_dir = tmp_path / "cli_project_001"
    cmd = [
        sys.executable,
        "main.py",
        "process-video",
        "--input", str(valid_video_path),
        "--output", str(out_dir)
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res.returncode == 0
    
    # Verify directory structure was created and metadata file exists
    meta_path = out_dir / "video_metadata.json"
    assert meta_path.exists()
    
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    assert meta["aspect_ratio"] == "16:9"

    # Verify input copy exists
    assert (out_dir / "input" / valid_video_path.name).exists()


def test_cli_rejects_missing_video(tmp_path: Path):
    cmd = [
        sys.executable,
        "main.py",
        "analyze-video",
        "--input", "non_existent_file.mp4"
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert res.returncode != 0
