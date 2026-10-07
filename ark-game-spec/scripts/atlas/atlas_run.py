#!/usr/bin/env python3
"""atlas_run — 一鍵：compile → lint → build → register。任一 exit ≠ 0 停。

用法: python atlas_run.py --run <run> --slug <game-slug> [--out data/atlas] [--library data/library/atlas] [--from v1|draft] [--assets auto|inline|linked] [--title ...]
      python atlas_run.py --gdd data/gdd/<pack> [--slug <book-slug>] [--max-figs 6] ...   # v1.1：gdd-pack 入口（atlas_from_gdd）
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
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))  # skill root（_lib）
from _lib import run_common as C  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent


def step(script, *args):
    r = subprocess.run([sys.executable, str(HERE / script), *args], capture_output=True, text=True, encoding="utf-8")
    out = (r.stdout or "").strip()
    if not out:
        # F-6：Windows PowerShell 管線常吞子腳本 stdout（exit 0 但空）→ 給明確診斷，非泛化 QUERY_FAILED
        C.fail("QUERY_FAILED", f"{script} 無 stdout 輸出（exit={r.returncode}）",
               f"子腳本應走 emit() 輸出 JSON；Windows 下若 stdout 被吞可改逐步跑。stderr: {r.stderr[-300:]}")
    try:
        j = json.loads(out.splitlines()[-1])
    except Exception:  # noqa: BLE001
        C.fail("QUERY_FAILED", f"{script} stdout 末行非 JSON（exit={r.returncode}）",
               f"末行: {out.splitlines()[-1][:200]} | stderr: {r.stderr[-300:]}")
    if not j.get("success"):
        print(json.dumps(j, ensure_ascii=False)); sys.exit(r.returncode or 1)
    return j["data"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", help="影片 run 目錄（與 --gdd 二選一）")
    ap.add_argument("--gdd", help="gdd-pack 目錄（與 --run 二選一；走 atlas_from_gdd）")
    ap.add_argument("--slug", help="--run 必填；--gdd 預設取 gdd.yaml.slug")
    ap.add_argument("--out", default="data/atlas")
    ap.add_argument("--library", default="data/library/atlas")
    ap.add_argument("--max-figs", type=int, default=6)
    ap.add_argument("--from", dest="src", default="v1")
    ap.add_argument("--assets", default="auto")
    ap.add_argument("--title")
    a = ap.parse_args()
    if bool(a.run) == bool(a.gdd):
        C.fail("BAD_INPUT", "--run 與 --gdd 擇一", "")
    title = ["--title", a.title] if a.title else []
    if a.gdd:
        c = step("atlas_from_gdd.py", "--gdd", a.gdd, "--out", a.out, "--max-figs", str(a.max_figs), *(["--slug", a.slug] if a.slug else []), *title)
    else:
        if not a.slug:
            C.fail("BAD_INPUT", "--run 需要 --slug", "")
        c = step("atlas_compile.py", "--run", a.run, "--slug", a.slug, "--out", a.out, "--from", a.src, *title)
    book = c["book"]
    l = step("atlas_lint.py", "--book", book)
    b = step("atlas_build.py", "--book", book, "--assets", a.assets)
    r = step("atlas_register.py", "--book", book, "--library", a.library)
    C.emit({"book": book, "chapters": c["chapters"], "figures": c["figures"], "lint": "PASS", "site": b["site"], "assets_mode": b["assets_mode"],
            "size_mb": b["size_mb"], "catalog": r["catalog"], "status": c.get("status", "draft"),
            "delivery": f"atlas 已落盤 {book}｜{c['chapters']} 章｜{c['figures']} 圖｜lint: PASS｜site: {b['site']}｜catalog: 已登錄（{r['action']}）"}, {"stage": "atlas_run"})


if __name__ == "__main__":
    main()
