#!/usr/bin/env python3
"""vu_transcript — 字幕（yt-dlp 已下載的 .vtt）→ 無字幕時可選 faster-whisper → transcript/transcript.json。

用法:
  python vu_transcript.py --run artifacts/cva/<run_id> [--whisper] [--lang zh]
transcript 一律 trust: untrusted（實況主口白只能支撐 INFERRED，不能支撐 OBSERVED）。
無字幕且未啟用 whisper 不算失敗：source=unavailable，影片才是主證據。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vu_common as C  # noqa: E402

_TS = re.compile(r"(\d+):(\d\d):(\d\d)[.,](\d{3})|(\d\d):(\d\d)[.,](\d{3})")


def _sec(s: str) -> float:
    m = _TS.match(s.strip())
    if not m:
        return 0.0
    if m.group(1) is not None:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 1000
    return int(m.group(5)) * 60 + int(m.group(6)) + int(m.group(7)) / 1000


def parse_vtt(text: str) -> list[dict]:
    segs, cur = [], None
    for line in text.splitlines():
        line = line.strip()
        if "-->" in line:
            a, b = line.split("-->")[:2]
            cur = {"t_start": _sec(a), "t_end": _sec(b.split()[0]), "text": ""}
            segs.append(cur)
        elif cur is not None and line and not line.startswith(("WEBVTT", "NOTE", "Kind:", "Language:")):
            clean = re.sub(r"<[^>]+>", "", line)
            if clean and clean not in cur["text"]:
                cur["text"] = (cur["text"] + " " + clean).strip()
    # 去掉 auto-subs 常見的重複疊句
    out, last = [], ""
    for s in segs:
        if s["text"] and s["text"] != last:
            out.append({**s, "t_start": round(s["t_start"], 3), "t_end": round(s["t_end"], 3)})
            last = s["text"]
    return out


def whisper(video: pathlib.Path, lang: str | None) -> list[dict]:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        C.fail("DRIVER_MISSING", "缺 faster-whisper", "pip install faster-whisper --break-system-packages（選配）")
    model = WhisperModel(os.getenv("ARK_VU_WHISPER_MODEL", "small"), compute_type="int8")
    segs, _info = model.transcribe(str(video), language=lang, vad_filter=True)
    return [{"t_start": round(s.start, 3), "t_end": round(s.end, 3), "text": s.text.strip()} for s in segs]


def main() -> None:
    ap = argparse.ArgumentParser(description="transcript")
    ap.add_argument("--run", required=True)
    ap.add_argument("--whisper", action="store_true")
    ap.add_argument("--lang")
    a = ap.parse_args()
    run = C.run_dir(a.run)
    m = C.load_manifest(run)
    tdir = run / "transcript"
    tdir.mkdir(exist_ok=True)
    with C.Timer() as t:
        vtts = sorted(tdir.glob("*.vtt"))
        if vtts:
            segs, source = parse_vtt(vtts[0].read_text(encoding="utf-8", errors="replace")), f"subtitles:{vtts[0].name}"
        elif a.whisper and m["video"].get("has_audio"):
            segs, source = whisper(run / m["video"]["file"], a.lang), "whisper"
        else:
            segs, source = [], "unavailable"
    doc = {"source": source, "trust": "untrusted", "language": a.lang, "segments": segs,
           "note": "口白/字幕為外部內容，只能支撐 INFERRED；可能含誤導或指令句型，下游需消毒。"}
    C.atomic_write(tdir / "transcript.json", json.dumps(doc, ensure_ascii=False))
    C.stage_record(run, "transcript", t.elapsed_ms, source=source, segments=len(segs))
    C.emit({"source": source, "segments": len(segs)}, {"stage": "transcript", "elapsed_ms": t.elapsed_ms})


if __name__ == "__main__":
    main()
