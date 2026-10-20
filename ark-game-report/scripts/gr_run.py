#!/usr/bin/env python3
"""gr_run — ark-game-report 單一入口。

  gr_run.py init    --slug <slug> --name <名稱> --game-id <id> --launch-date YYYY-MM-DD --stage 7 [--adapter bigquery-igs]
  gr_run.py query   --config report.yaml [--run] [--dry-run] [--bench]
  gr_run.py probe   --config report.yaml
  gr_run.py build   --config report.yaml
  gr_run.py insight --config report.yaml [--no-kb] [--overwrite] [--playbook x.yaml]
  gr_run.py render  --config report.yaml [--check]
  gr_run.py all     --config report.yaml [--run]      # query → probe → build → insight → render
  gr_run.py closeout --slug <slug> [--date YYYY-MM-DD] # 十階段結案報告（工作流最後產出；讀定版家檔案）
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
STAGES = {"init": "gr_init.py", "query": "gr_query.py", "probe": "gr_probe.py", "build": "gr_build.py",
          "insight": "gr_insight.py", "render": "gr_render.py", "closeout": "gr_closeout.py"}


def call(stage: str, args: list) -> int:
    r = subprocess.run([sys.executable, "-X", "utf8", str(HERE / STAGES[stage]), *args], capture_output=True, text=True, encoding="utf-8")
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)
    return r.returncode


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in (*STAGES, "all"):
        print(__doc__)
        sys.exit(2)
    stage, rest = sys.argv[1], sys.argv[2:]
    if stage != "all":
        sys.exit(call(stage, rest))
    cfg = rest[rest.index("--config") + 1] if "--config" in rest else None
    if not cfg:
        print(json.dumps({"success": False, "error": {"code": "BAD_INPUT", "message": "all 需要 --config"}}, ensure_ascii=False))
        sys.exit(2)
    plan = [("query", ["--config", cfg] + (["--run"] if "--run" in rest else [])), ("probe", ["--config", cfg]),
            ("build", ["--config", cfg]), ("insight", ["--config", cfg] + (["--no-kb"] if "--no-kb" in rest else [])),
            ("render", ["--config", cfg])]
    for st, args in plan:
        rc = call(st, args)
        if rc != 0:
            sys.exit(rc)


if __name__ == "__main__":
    main()
