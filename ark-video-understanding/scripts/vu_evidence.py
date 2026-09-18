#!/usr/bin/env python3
"""vu_evidence — keyframes + sheets + transcript → evidence.jsonl（產出後唯讀，下游只能引用不能新增）。

用法:
  python vu_evidence.py --run artifacts/cva/<run_id>
每行：evidence_id E001…、type visual|transcript、extractor（偵測器 label）、t_start/t_end、frame、sheet/cell、
trust {timestamp: deterministic, observation: llm|untrusted}、observation（此時為空，ga_observe 填）。
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vu_common as C  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="build evidence.jsonl")
    ap.add_argument("--run", required=True)
    ap.add_argument("--force", action="store_true", help="覆寫既有 evidence.jsonl（會使下游 observation 失效）")
    a = ap.parse_args()
    run = C.run_dir(a.run)
    m = C.load_manifest(run)
    out = run / "evidence.jsonl"
    if out.exists() and not a.force:
        C.fail("GATE_BLOCKED", "evidence.jsonl 已存在且唯讀", "刻意重建請加 --force（下游 observation 需重跑）")
    kf = json.loads((run / "frames" / "keyframes.json").read_text(encoding="utf-8"))["keyframes"]
    sheets = json.loads((run / "frames" / "sheets.json").read_text(encoding="utf-8"))["sheets"]
    cell_of = {}
    for s in sheets:
        for c in s["cells"]:
            cell_of[c["keyframe_idx"]] = {"file": s["file"], "sheet": s["sheet"], "cell": c["cell"]}
    tpath = run / "transcript" / "transcript.json"
    tr = json.loads(tpath.read_text(encoding="utf-8")) if tpath.exists() else {"segments": []}
    lines, n = [], 0
    with C.Timer() as t:
        for k in kf:
            n += 1
            lines.append({"evidence_id": f"E{n:03d}", "type": "visual", "extractor": k["label"], "detector": k["detector"],
                          "t_start": k["ts"], "t_end": k["ts"], "t_sec": k["t"], "frame": k["file"],
                          "sheet": cell_of.get(k["idx"]), "video_sha256": m["video"]["sha256"],
                          "trust": {"timestamp": "deterministic", "observation": "llm"},
                          "observation": [], "numbers": [], "confidence": None, "extra": k.get("extra", {})})
        for s in tr.get("segments", []):
            n += 1
            lines.append({"evidence_id": f"E{n:03d}", "type": "transcript", "extractor": tr.get("source", "subtitles"),
                          "t_start": C.fmt_ts(s["t_start"]), "t_end": C.fmt_ts(s["t_end"]), "t_sec": s["t_start"],
                          "frame": None, "sheet": None, "video_sha256": m["video"]["sha256"],
                          "trust": {"timestamp": "deterministic", "observation": "untrusted"},
                          "observation": [s["text"]], "numbers": [], "confidence": "low", "extra": {}})
    if out.exists():
        out.chmod(stat.S_IWUSR | stat.S_IRUSR)
    C.atomic_write(out, "\n".join(json.dumps(x, ensure_ascii=False) for x in lines) + "\n")
    out.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    C.stage_record(run, "evidence", t.elapsed_ms, visual=len(kf), transcript=len(tr.get("segments", [])))
    C.emit({"count": len(lines), "visual": len(kf), "transcript": len(tr.get("segments", [])), "file": "evidence.jsonl", "readonly": True},
           {"stage": "evidence", "elapsed_ms": t.elapsed_ms})


if __name__ == "__main__":
    main()
