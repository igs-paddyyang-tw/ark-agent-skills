#!/usr/bin/env python3
"""vu_events — 依 resolved pack 的 extraction.detectors 跑偵測器註冊表 → frames/events.json。

用法:
  python vu_events.py --run artifacts/cva/<run_id> [--core-only]
--core-only：domain 未定時只跑 periodic + scene_change（供 ga_detect 用的少量幀）。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vu_common as C  # noqa: E402
from detectors import REGISTRY, run as run_detector  # noqa: E402

CORE_ONLY = [{"use": "periodic", "every_s": 5, "label": "fallback"}, {"use": "scene_change", "threshold": 0.5, "label": "scene"}]


def audio_rms(video: pathlib.Path, hop_s: float = 0.25) -> dict | None:
    import numpy as np
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
                       capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return None
    pcm = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    hop = int(8000 * hop_s)
    n = len(pcm) // hop
    if n == 0:
        return None
    rms = np.sqrt((pcm[: n * hop].reshape(n, hop) ** 2).mean(axis=1))
    return {"hop_s": hop_s, "rms": [round(float(v), 6) for v in rms]}


def main() -> None:
    ap = argparse.ArgumentParser(description="run detectors")
    ap.add_argument("--run", required=True)
    ap.add_argument("--core-only", action="store_true")
    a = ap.parse_args()
    run = C.run_dir(a.run)
    m = C.load_manifest(run)
    tl_path = run / "frames" / "motion_timeline.json"
    if not tl_path.exists():
        C.fail("BAD_INPUT", "缺 motion_timeline.json", "先跑 vu_timeline.py")
    tl = json.loads(tl_path.read_text(encoding="utf-8"))
    if a.core_only:
        specs, mode = CORE_ONLY, "core_only"
    else:
        resolved = C.load_resolved(run)
        specs, mode = resolved["extraction"]["detectors"], "pack"
    unknown = [s["use"] for s in specs if s["use"] not in REGISTRY]
    if unknown:
        C.fail("BAD_INPUT", f"未知偵測器 {unknown}", "偵測器需先加入 detectors/ 註冊表並在 pack_lint 登記")
    ctx = {}
    if any(s["use"] == "audio_peak" for s in specs) and m["video"].get("has_audio"):
        ctx["audio_rms"] = audio_rms(run / m["video"]["file"])
    with C.Timer() as t:
        events = []
        for s in specs:
            events.extend(run_detector(tl, s, ctx))
        events.sort(key=lambda e: (e["t"], e["detector"]))
    by = {}
    for e in events:
        by[e["label"]] = by.get(e["label"], 0) + 1
    C.atomic_write(run / "frames" / "events.json", json.dumps({"mode": mode, "detectors": specs, "events": events}, ensure_ascii=False, separators=(",", ":")))
    C.stage_record(run, "events", t.elapsed_ms, mode=mode, counts=by)
    C.emit({"mode": mode, "count": len(events), "by_label": by}, {"stage": "events", "elapsed_ms": t.elapsed_ms})


if __name__ == "__main__":
    main()
