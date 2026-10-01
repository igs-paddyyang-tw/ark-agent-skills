#!/usr/bin/env python3
"""gdd_run — lint → build 一鍵（lint 有 error 就停，不產 HTML）。

用法: python gdd_run.py --pack data/gdd/<slug> [--out <html>] [--style <style.yaml>]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gdd_common as C  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent


def step(script: str, *args) -> dict:
    r = subprocess.run([sys.executable, str(HERE / script), *args], capture_output=True, text=True, encoding="utf-8")
    try:
        j = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        C.fail("QUERY_FAILED", f"{script} 無 JSON 輸出: {r.stderr[-400:]}")
    if not j.get("success"):
        print(json.dumps(j, ensure_ascii=False))
        sys.exit(r.returncode or 1)
    return j


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", required=True)
    ap.add_argument("--out")
    ap.add_argument("--style")
    a = ap.parse_args()
    pack = str(C.pack_dir(a.pack))
    lint = step("gdd_lint.py", "--pack", pack)
    bargs = ["--pack", pack] + (["--out", a.out] if a.out else []) + (["--style", a.style] if a.style else [])
    build = step("gdd_build.py", *bargs)
    C.emit({"lint": lint["data"], "build": build["data"]}, {"stage": "gdd_run"})


if __name__ == "__main__":
    main()
