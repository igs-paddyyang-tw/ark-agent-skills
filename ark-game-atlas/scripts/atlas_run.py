#!/usr/bin/env python3
"""atlas_run — 一鍵：compile → lint → build → register。任一 exit ≠ 0 停。

用法: python atlas_run.py --run <run> --slug <game-slug> [--out atlas] [--library library/atlas] [--from v1|draft] [--assets auto|inline|linked] [--title ...]
交付格式：atlas 已落盤 atlas/<slug>｜N 章｜M 圖｜lint: PASS｜site: …｜catalog: 已登錄
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import atlas_common as C  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent


def step(script, *args):
    r = subprocess.run([sys.executable, str(HERE / script), *args], capture_output=True, text=True, encoding="utf-8")
    try:
        j = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        C.fail("QUERY_FAILED", f"{script} 無 JSON 輸出: {r.stderr[-300:]}", "")
    if not j.get("success"):
        print(json.dumps(j, ensure_ascii=False)); sys.exit(r.returncode or 1)
    return j["data"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--out", default="atlas")
    ap.add_argument("--library", default="library/atlas")
    ap.add_argument("--from", dest="src", default="v1")
    ap.add_argument("--assets", default="auto")
    ap.add_argument("--title")
    a = ap.parse_args()
    c = step("atlas_compile.py", "--run", a.run, "--slug", a.slug, "--out", a.out, "--from", a.src, *(["--title", a.title] if a.title else []))
    book = c["book"]
    l = step("atlas_lint.py", "--book", book)
    b = step("atlas_build.py", "--book", book, "--assets", a.assets)
    r = step("atlas_register.py", "--book", book, "--library", a.library)
    C.emit({"book": book, "chapters": c["chapters"], "figures": c["figures"], "lint": "PASS", "site": b["site"], "assets_mode": b["assets_mode"],
            "size_mb": b["size_mb"], "catalog": r["catalog"], "status": c["status"],
            "delivery": f"atlas 已落盤 {book}｜{c['chapters']} 章｜{c['figures']} 圖｜lint: PASS｜site: {b['site']}｜catalog: 已登錄（{r['action']}）"}, {"stage": "atlas_run"})


if __name__ == "__main__":
    main()
