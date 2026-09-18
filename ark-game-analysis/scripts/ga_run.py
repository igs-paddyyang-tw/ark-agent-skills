#!/usr/bin/env python3
"""ga_run — observe → analyze → validate → kb_match 一鍵。

用法: python ga_run.py --run artifacts/cva/<run_id> [--force]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ga_common as C  # noqa: E402

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
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    run = str(C.run_dir(a.run))
    o = step("ga_observe.py", "--run", run, *(["--force"] if a.force else []))
    an = step("ga_analyze.py", "--run", run)
    v = step("ga_validate.py", "--run", run)
    k = step("kb_match.py", "--run", run)
    C.emit({"observe": o["data"], "analyze": an["data"], "validate": v["data"], "kb": k["data"],
            "next": f"python ark-game-spec/scripts/gs_draft.py --run {run}"}, {"stage": "ga_run"})


if __name__ == "__main__":
    main()
