#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from config import load_env, whisper_provider
from download import is_url, download_video, fetch_captions
from frames import extract_frames
from transcribe import parse_vtt, write_transcript, extract_audio, whisper

def build_evidence_md(manifest, transcript_rows):
    lines = [
        "# Ark Video Evidence",
        "",
        f"- Schema: `{manifest['schema_version']}`",
        f"- Source: `{manifest['source']['input']}`",
        f"- Source type: `{manifest['source']['type']}`",
        f"- Transcript: `{manifest['transcript']['source']}`",
        "",
        "## Evidence Frames",
        ""
    ]
    for f in manifest["frames"]:
        lines.append(
            f"### {f['evidence_id']} — {f['timestamp']}\n"
            f"- Path: `{f['path']}`\n"
            f"- Type: `OBSERVED_FRAME`\n"
        )
    lines += ["## Transcript", ""]
    for row in transcript_rows:
        lines.append(f"- [{row['start']} → {row['end']}] {row['text']}")
    if not transcript_rows:
        lines.append("`NOT_AVAILABLE`")
    lines += [
        "",
        "## Grounding Rules",
        "",
        "- OBSERVED = directly visible/audible.",
        "- INFERRED = downstream interpretation; not produced by this Skill.",
        "- FROM_KB = downstream knowledge retrieval.",
        "- PROPOSED = downstream design proposal.",
        "- Missing evidence must be reported as `NOT_OBSERVED`."
    ]
    return "\n".join(lines) + "\n"

def main():
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--detail", choices=["transcript", "efficient", "balanced", "token-burner"], default="balanced")
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--timestamps", help="comma-separated absolute timestamps")
    ap.add_argument("--max-frames", type=int)
    ap.add_argument("--resolution", type=int, default=512)
    ap.add_argument("--fps", type=float)
    ap.add_argument("--whisper", choices=["groq", "openai"])
    ap.add_argument("--no-whisper", action="store_true")
    ap.add_argument("--no-dedup", action="store_true")
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    source_type = "url" if is_url(args.source) else "local"

    if source_type == "url":
        caption = fetch_captions(args.source, out / "source")
        video = None
        # Captions-only mode does not require a video download.
        if args.detail != "transcript" or caption is None:
            video = download_video(args.source, out / "source")
    else:
        video = Path(args.source)
        if not video.exists():
            raise SystemExit(f"Local video not found: {video}")
        caption = None

    transcript_rows = []
    transcript_source = "unavailable"

    if caption:
        transcript_rows = parse_vtt(caption)
        shutil.copy2(caption, out / "transcript.vtt")
        transcript_source = "native_caption"
    elif video and not args.no_whisper:
        provider = args.whisper or whisper_provider()
        if provider:
            audio = out / "audio.mp3"
            extract_audio(video, audio)
            data = whisper(audio, provider)
            segments = data.get("segments", [])
            transcript_rows = [{
                "start": f"{int(s['start']//3600):02d}:{int(s['start']//60)%60:02d}:{s['start']%60:06.3f}",
                "end": f"{int(s['end']//3600):02d}:{int(s['end']//60)%60:02d}:{s['end']%60:06.3f}",
                "text": s.get("text", "").strip()
            } for s in segments]
            transcript_source = f"whisper_{provider}"
        else:
            transcript_source = "unavailable_no_whisper_key"

    write_transcript(transcript_rows, out / "transcript.txt")

    frames = []
    if video:
        explicit = [x.strip() for x in args.timestamps.split(",")] if args.timestamps else None
        frames = extract_frames(
            video, out, detail=args.detail, start=args.start, end=args.end,
            resolution=args.resolution, fps=args.fps, max_frames=args.max_frames,
            dedup=not args.no_dedup, explicit_timestamps=explicit
        )

    manifest = {
        "schema_version": "ark-video-evidence/v1",
        "source": {"input": args.source, "type": source_type},
        "processing": {
            "detail": args.detail,
            "start": args.start,
            "end": args.end,
            "resolution": args.resolution,
            "fps": args.fps,
            "dedup": not args.no_dedup
        },
        "transcript": {
            "source": transcript_source,
            "segments": len(transcript_rows)
        },
        "frames": frames,
        "grounding": {
            "produced_semantics": ["OBSERVED"],
            "downstream_semantics": ["INFERRED", "FROM_KB", "PROPOSED"]
        }
    }

    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "evidence.md").write_text(build_evidence_md(manifest, transcript_rows), encoding="utf-8")
    (out / "meta").mkdir(exist_ok=True)
    (out / "meta" / "run.json").write_text(json.dumps(vars(args), ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "status": "ok",
        "out_dir": str(out),
        "frames": len(frames),
        "transcript_source": transcript_source,
        "manifest": str(out / "manifest.json"),
        "evidence": str(out / "evidence.md")
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
