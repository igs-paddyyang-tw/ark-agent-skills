#!/usr/bin/env python3
"""vu_run — 一鍵：fetch → (pack 快照) → timeline → events → keyframes → sheets → transcript → evidence。

用法:
  python vu_run.py --source <url|path> --domain slot-game [--out artifacts/cva] [--whisper] [--crop x,y,w,h]
  python vu_run.py --source <url|path> --domain auto          # 只做到 detect sheets，之後跑 ga_detect.py
  python vu_run.py --run artifacts/cva/<run_id> --domain fish-game   # 對既有 run 綁定 domain 並完成剩餘 stage
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

HERE = pathlib.Path(__file__).resolve().parent


def step(script: str, *args) -> dict:
    r = subprocess.run([sys.executable, str(HERE / script), *args], capture_output=True, text=True, encoding="utf-8")
    try:
        j = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        C.fail("QUERY_FAILED", f"{script} 無 JSON 輸出: {r.stderr[-300:]}", "")
    if not j.get("success"):
        print(json.dumps(j, ensure_ascii=False))
        sys.exit(r.returncode or 1)
    return j


def main() -> None:
    ap = argparse.ArgumentParser(description="video understanding one-shot")
    ap.add_argument("--source")
    ap.add_argument("--run")
    ap.add_argument("--domain", default="auto")
    ap.add_argument("--out", default="artifacts/cva")
    ap.add_argument("--whisper", action="store_true")
    ap.add_argument("--crop")
    ap.add_argument("--t-range")
    a = ap.parse_args()
    if not a.source and not a.run:
        C.fail("BAD_INPUT", "需要 --source 或 --run", "")
    stages = []
    if a.source:
        j = step("vu_fetch.py", "--source", a.source, "--out", a.out, "--domain", a.domain)
        run = pathlib.Path(j["data"]["run"])
        stages.append("fetch")
    else:
        run = C.run_dir(a.run)
        if a.domain != "auto":
            C.snapshot_pack(run, a.domain)
            m = C.load_manifest(run)
            m["domain_source"] = m.get("domain_source") if m.get("domain_source") == "detected" else "cli"
            C.save_manifest(run, m)
    m = C.load_manifest(run)
    tl_args = ["--run", str(run)] + (["--crop", a.crop] if a.crop else [])
    if m.get("domain") is None:
        # auto 模式：只產 detect sheets 供 ga_detect
        step("vu_timeline.py", *tl_args); stages.append("timeline")
        step("vu_events.py", "--run", str(run), "--core-only"); stages.append("events(core_only)")
        step("vu_keyframes.py", "--run", str(run), "--core-only"); stages.append("detect")
        step("vu_sheets.py", "--run", str(run), "--core-only"); stages.append("detect_sheets")
        C.emit({"run": str(run), "run_id": run.name, "domain": None, "stages": stages,
                "next": f"python ark-game-analysis/scripts/ga_detect.py --run {run} ；判定後 python vu_run.py --run {run} --domain <d>"},
               {"mode": "auto_detect_pending"})
    if not (run / "frames" / "motion_timeline.json").exists() or a.crop:
        step("vu_timeline.py", *tl_args); stages.append("timeline")
    else:
        # domain 綁定後 ROI 可能不同 → 重算 timeline（低成本）
        step("vu_timeline.py", *tl_args); stages.append("timeline")
    step("vu_events.py", "--run", str(run)); stages.append("events")
    step("vu_keyframes.py", "--run", str(run), *(["--t-range", a.t_range] if a.t_range else [])); stages.append("keyframes")
    step("vu_sheets.py", "--run", str(run)); stages.append("sheets")
    step("vu_transcript.py", "--run", str(run), *(["--whisper"] if a.whisper else [])); stages.append("transcript")
    ev = step("vu_evidence.py", "--run", str(run), "--force"); stages.append("evidence")
    m = C.load_manifest(run)
    C.emit({"run": str(run), "run_id": run.name, "domain": m["domain"], "stages": stages,
            "evidence": ev["data"], "budget_used": m.get("budget_used", {}),
            "next": f"python ark-game-analysis/scripts/ga_observe.py --run {run}"}, {"mode": "full"})


if __name__ == "__main__":
    main()
