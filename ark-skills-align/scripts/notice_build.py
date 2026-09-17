#!/usr/bin/env python3
"""notice_build.py — 由 check_consumers --impact 的 JSON 產 Alignment Notice（ADR-004）。

輸出 ark-md-report `review` 型 Markdown（report_lint 必過）：宣告哪些 skill 有破壞性變更、
影響哪些消費端、遷移指引。廣播到 team 頻道（D-1）。

用法：python notice_build.py impact.json --out docs/reports/review/2026-09-17-align-notice.md
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path


def build(impact: dict) -> str:
    rel = impact.get("release", "unknown")
    breaking = impact.get("breaking", [])
    affected = impact.get("affected", [])
    recipients = impact.get("recipients", [])
    today = date.today().isoformat()
    lines = [
        "---",
        "title: \"Alignment Notice — skill 破壞性升版\"",
        "type: report",
        "report_type: review",
        f"created: {today}",
        "language: zh-TW",
        f"loop_stage: align",
        f"verdict: {'broken' if breaking else 'sound'}",
        f"recipients: {json.dumps(recipients, ensure_ascii=False)}",
        f"affected: {json.dumps(affected, ensure_ascii=False)}",
        "---",
        "",
        "# Alignment Notice — skill 破壞性升版",
        "",
        f"## 摘要（Summary）",
        f"列車 `{rel}` 含 {len(breaking)} 個破壞性升版，影響 {len(affected)} 個消費端。",
        "",
        "## 破壞性變更（Breaking）",
    ]
    if breaking:
        lines.append("| skill | 從 | 到 | 遷移指引 |")
        lines.append("|-------|-----|-----|----------|")
        for b in breaking:
            lines.append(f"| {b.get('skill')} | {b.get('from','?')} | {b.get('to','?')} "
                         f"| {b.get('migration','見該 skill CHANGELOG ### Breaking')} |")
    else:
        lines.append("（無）")
    lines += ["", "## 受影響消費端（Affected）"]
    if affected:
        for a in affected:
            lines.append(f"- {a}")
    else:
        lines.append("（無）")
    lines += ["", "## 下一步（Action）",
              "1. 該部署 manager（`<專案>-agent`）改 `skills-matrix.yaml` 的 release",
              "2. `align_sync.py plan --waves` → 逐波 `apply --wave N --yes`（私訊 manager 確認，C-5）",
              "3. `align_sync.py verify` P0/P1=0 才算對齊完成", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="產 Alignment Notice")
    ap.add_argument("impact", help="check_consumers --impact 的 JSON")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    impact = json.loads(Path(args.impact).read_text(encoding="utf-8"))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(impact), encoding="utf-8")
    print(f"✅ Alignment Notice → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
