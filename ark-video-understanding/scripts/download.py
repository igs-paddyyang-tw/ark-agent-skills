#!/usr/bin/env python3
import json
import subprocess
from pathlib import Path
from urllib.parse import urlparse

def is_url(value):
    try:
        return urlparse(value).scheme in ("http", "https")
    except Exception:
        return False

def download_video(source, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    template = str(out_dir / "source.%(ext)s")
    cmd = [
        "yt-dlp", "--no-playlist",
        "-f", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
        "--merge-output-format", "mp4",
        "-o", template, source
    ]
    subprocess.run(cmd, check=True)
    candidates = sorted(out_dir.glob("source.*"))
    videos = [p for p in candidates if p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}]
    if not videos:
        raise RuntimeError("yt-dlp completed but no video file was found.")
    return videos[0]

def fetch_captions(source, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = str(out_dir / "caption")
    cmd = [
        "yt-dlp", "--no-playlist",
        "--write-subs", "--write-auto-subs",
        "--sub-langs", "all",
        "--sub-format", "vtt",
        "--skip-download",
        "-o", prefix,
        source
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    vtts = sorted(out_dir.glob("caption*.vtt"))
    if vtts:
        return vtts[0]
    return None
