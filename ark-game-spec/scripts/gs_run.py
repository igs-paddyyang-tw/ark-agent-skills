#!/usr/bin/env python3
"""gs_run — 分段一鍵：
  --stage draft   gs_draft（含 lint）→ gs_review → decisions.template.yaml
  --stage decide  gs_decide → spec_lint(v1)
  --stage dev     gs_dev → gs_metrics
用法: python gs_run.py --run artifacts/cva/<run_id> --stage draft|decide|dev [--answer-key f] [--llm]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gs_common as C  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent


def step(script, *args):
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--stage", required=True, choices=["draft", "decide", "dev"])
    ap.add_argument("--answer-key")
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--allow-deferred", action="store_true")
    a = ap.parse_args()
    run = str(C.run_dir(a.run))
    if a.stage == "draft":
        d = step("gs_draft.py", "--run", run)
        r = step("gs_review.py", "--run", run, *(["--llm"] if a.llm else []))
        t = step("gs_decide.py", "--run", run, "--template")
        C.emit({"draft": d["data"], "review": r["data"], "template": t["data"],
                "next": "人員決議 → decisions.yaml → gs_run.py --stage decide"}, {"stage": "draft"})
    if a.stage == "decide":
        d = step("gs_decide.py", "--run", run)
        l = step("spec_lint.py", "--run", run, "--spec", "game-spec.v1.md")
        C.emit({"decide": d["data"], "lint_v1": l["data"]["summary"], "next": "gs_run.py --stage dev"}, {"stage": "decide"})
    d = step("gs_dev.py", "--run", run, *(["--allow-deferred"] if a.allow_deferred else []))
    mt = step("gs_metrics.py", "--run", run, *(["--answer-key", a.answer_key] if a.answer_key else []))
    C.emit({"dev": d["data"], "metrics": mt["data"]}, {"stage": "dev"})


if __name__ == "__main__":
    main()
