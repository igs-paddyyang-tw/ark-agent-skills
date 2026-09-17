#!/usr/bin/env python3
import math
import subprocess
from pathlib import Path

def _duration(video):
    out = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video)
    ], text=True).strip()
    return float(out)

def _parse_time(value):
    if value is None:
        return None
    parts = value.split(":")
    if len(parts) == 1:
        return float(parts[0])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])

def _fmt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}-{m:02d}-{s:05.2f}".replace(".", "_")

def _candidate_timestamps(video, start, end, detail, fps):
    duration = _duration(video)
    start = 0 if start is None else max(0, _parse_time(start))
    end = duration if end is None else min(duration, _parse_time(end))
    span = max(0.1, end - start)

    if detail == "transcript":
        return []
    if detail == "efficient":
        cap = 50
        step = max(1.0 / min(fps or 1.0, 2.0), span / max(1, cap))
    elif detail == "balanced":
        cap = 100
        step = max(0.5, span / max(1, cap))
    else:
        cap = 1000000
        step = max(0.5, 1.0 / min(fps or 1.0, 2.0))

    ts = []
    t = start
    while t < end and len(ts) < cap:
        ts.append(t)
        t += step
    if not ts or ts[-1] != end:
        ts.append(end)
    return ts

def _extract(video, timestamp, out_file, resolution):
    vf = f"scale={resolution}:-2"
    subprocess.run([
        "ffmpeg", "-y", "-ss", str(timestamp), "-i", str(video),
        "-frames:v", "1", "-vf", vf, "-q:v", "2", str(out_file)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

def _dedup(paths, threshold=2.0):
    # Uses ffmpeg to create 16x16 grayscale thumbnails and Python stdlib only.
    kept = []
    previous = None
    for path in paths:
        thumb = path.with_suffix(".dedup.pgm")
        subprocess.run([
            "ffmpeg", "-y", "-i", str(path), "-vf", "scale=16:16,format=gray",
            "-f", "image2", str(thumb)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        data = thumb.read_bytes()
        # PGM header ends at the third newline.
        pos = 0
        for _ in range(3):
            pos = data.find(b"\n", pos) + 1
        pixels = data[pos:]
        if previous is None:
            keep = True
        else:
            n = min(len(previous), len(pixels))
            diff = sum(abs(previous[i] - pixels[i]) for i in range(n)) / max(1, n)
            keep = diff > threshold
        if keep:
            kept.append(path)
            previous = pixels
        else:
            path.unlink(missing_ok=True)
        thumb.unlink(missing_ok=True)
    return kept

def extract_frames(video, out_dir, detail="balanced", start=None, end=None,
                   resolution=512, fps=None, max_frames=None, dedup=True,
                   explicit_timestamps=None):
    out_dir = Path(out_dir)
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    timestamps = _candidate_timestamps(video, start, end, detail, fps)
    if explicit_timestamps:
        timestamps.extend(_parse_time(x) for x in explicit_timestamps)

    # stable sorted unique timestamps
    timestamps = sorted(set(round(x, 3) for x in timestamps))
    if max_frames:
        timestamps = timestamps[:max_frames]

    results = []
    for idx, ts in enumerate(timestamps, 1):
        path = frames_dir / f"candidate_{idx:04d}_{_fmt_time(ts)}.jpg"
        _extract(video, ts, path, resolution)
        results.append((ts, path))

    paths = [p for _, p in results]
    if dedup and paths:
        kept = set(_dedup(paths))
        results = [(ts, p) for ts, p in results if p in kept]

    final = []
    for idx, (ts, path) in enumerate(results, 1):
        new = frames_dir / f"E{idx:03d}_{_fmt_time(ts)}.jpg"
        path.rename(new)
        final.append({
            "evidence_id": f"E{idx:03d}",
            "timestamp_seconds": ts,
            "timestamp": _fmt_time(ts).replace("-", ":", 2).replace("_", "."),
            "path": str(new.relative_to(out_dir)).replace("\\", "/"),
            "kind": "frame"
        })
    return final
