#!/usr/bin/env python3
"""gr_init — 建立一份報告設定 report.yaml（樣板見 assets/report.yaml.tmpl）。

用法:
  python gr_init.py --slug milefo --name 彌勒佛 --game-id 446 --launch-date 2026-10-01 --stage 7 \
      [--adapter bigquery-igs|csv] [--out data/slot/<slug>/report/report-d7.yaml] [--force]
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gr_common as C  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="建立 report.yaml")
    ap.add_argument("--slug", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--game-id", required=True)
    ap.add_argument("--launch-date", required=True)
    ap.add_argument("--stage", type=int, default=7, choices=[7, 14, 30])
    ap.add_argument("--adapter", default="csv")
    ap.add_argument("--out")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", a.launch_date):
        C.fail("BAD_INPUT", "--launch-date 需為 YYYY-MM-DD")
    if C.adapter_path({"adapter": a.adapter}) and not C.adapter_path({"adapter": a.adapter}).is_file():
        C.fail("BAD_INPUT", f"找不到 adapter {a.adapter}", "可用：csv、" + "、".join(p.stem for p in (C.ASSETS / "adapters").glob("*.yaml")))
    out = pathlib.Path(a.out or f"data/slot/{a.slug}/report/report-d{a.stage}.yaml")
    if out.exists() and not a.force:
        C.fail("GATE_BLOCKED", f"{out} 已存在", "加 --force 覆寫")
    tmpl = (C.ASSETS / "report.yaml.tmpl").read_text(encoding="utf-8")
    text = tmpl.format(name=a.name, slug=a.slug, game_id=a.game_id, launch_date=a.launch_date, stage=a.stage, adapter=a.adapter)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    C.emit({"config": str(out), "next": f"編輯 spec／views／composition 後：gr_run.py probe --config {out}"}, {"stage": "init"})


if __name__ == "__main__":
    main()
