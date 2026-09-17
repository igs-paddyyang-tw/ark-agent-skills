#!/usr/bin/env python3
import re
import subprocess
from pathlib import Path

def parse_vtt(vtt):
    text = Path(vtt).read_text(encoding="utf-8", errors="ignore")
    blocks = re.split(r"\n\s*\n", text)
    rows = []
    for block in blocks:
        m = re.search(r"(\d\d:\d\d:\d\d\.\d{3})\s+-->\s+(\d\d:\d\d:\d\d\.\d{3})", block)
        if not m:
            continue
        lines = []
        for line in block.splitlines():
            if "-->" in line or line.startswith("WEBVTT") or re.match(r"^\d+$", line):
                continue
            line = re.sub(r"<[^>]+>", "", line).strip()
            if line:
                lines.append(line)
        if lines:
            rows.append({
                "start": m.group(1),
                "end": m.group(2),
                "text": " ".join(lines)
            })
    # Basic consecutive duplicate suppression common in auto captions.
    clean = []
    last = None
    for row in rows:
        if row["text"] != last:
            clean.append(row)
            last = row["text"]
    return clean

def write_transcript(rows, out_file):
    p = Path(out_file)
    p.write_text(
        "\n".join(f"[{r['start']} → {r['end']}] {r['text']}" for r in rows),
        encoding="utf-8"
    )

def extract_audio(video, out_file):
    subprocess.run([
        "ffmpeg", "-y", "-i", str(video),
        "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k",
        str(out_file)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

def whisper(audio, provider):
    import urllib.request, urllib.parse, json, os
    # Kept deliberately dependency-free. Multipart encoding is implemented here.
    key = os.getenv("GROQ_API_KEY") if provider == "groq" else os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(f"{provider} API key is not configured.")

    endpoint = "https://api.groq.com/openai/v1/audio/transcriptions" if provider == "groq" \
        else "https://api.openai.com/v1/audio/transcriptions"
    model = "whisper-large-v3" if provider == "groq" else "whisper-1"

    boundary = "----ArkVideoBoundary7MA4YWxkTrZu0gW"
    audio_bytes = Path(audio).read_bytes()
    body = []
    body.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n{model}\r\n".encode())
    body.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"response_format\"\r\n\r\nverbose_json\r\n".encode())
    body.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"audio.mp3\"\r\nContent-Type: audio/mpeg\r\n\r\n".encode())
    body.append(audio_bytes)
    body.append(f"\r\n--{boundary}--\r\n".encode())

    req = urllib.request.Request(endpoint, data=b"".join(body), method="POST")
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    with urllib.request.urlopen(req, timeout=300) as resp:
        data = json.loads(resp.read().decode())
    return data
