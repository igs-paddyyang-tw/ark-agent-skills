#!/usr/bin/env python3
"""ga_run — observe → analyze → validate → kb_match → report 一鍵。

用法: python ga_run.py --run artifacts/cva/<run_id> [--force] [--no-report] [--report-html] [--wiki-schema <schema.md>]
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
        print(json.dumps(j, ensure_ascii=False))
        sys.exit(r.returncode or 1)
    return j


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-report", action="store_true", help="不產 ark-md-report 契約報告")
    ap.add_argument("--report-html", action="store_true", help="報告同時產 View 軌 HTML（雙軌戳記）")
    ap.add_argument("--wiki-schema", help="report_lint 加驗 tags 白名單")
    a = ap.parse_args()
    run = str(C.run_dir(a.run))
    o = step("ga_observe.py", "--run", run, *(["--force"] if a.force else []))
    an = step("ga_analyze.py", "--run", run)
    v = step("ga_validate.py", "--run", run)
    k = step("kb_match.py", "--run", run)
    # ── report（預設產報告，--no-report 略過）── D-3 fix: ga_run 原本漏呼叫 ga_report
    rpt: dict = {}
    if not a.no_report:
        rpt_args = ["--run", run]
        if a.report_html:
            rpt_args.append("--html")
        if a.wiki_schema:
            rpt_args += ["--wiki-schema", a.wiki_schema]
        rpt = step("ga_report.py", *rpt_args)
    C.emit({"observe": o["data"], "analyze": an["data"], "validate": v["data"], "kb": k["data"],
            "report": rpt.get("data") if rpt else "skipped",
            "next": f"python ark-game-spec/scripts/gs_draft.py --run {run}"}, {"stage": "ga_run"})


if __name__ == "__main__":
    main()
