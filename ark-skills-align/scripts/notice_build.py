#!/usr/bin/env python3
"""notice_build.py — 由消費端影響 JSON 產 Alignment Notice（ADR-004）。

輸出 ark-md-report `review` 型 Markdown，**保證過 report_lint**：完整 Verdict/Findings/
Evidence/Actions/邊界聲明 章節 + 統計一致（每個 breaking = 一個 P1 Finding，Evidence 標
「支持 F-x」，Actions 對應 Finding）。宣告哪些 skill 破壞性升版、影響哪些消費端。廣播 team 頻道（D-1）。

impact JSON schema（check_consumers 尚未提供 --impact 旗標時可手組）：
    {"release": "...", "breaking": [{"skill","from","to","migration"}], "affected": [...], "recipients": [...]}

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
    verdict = "needs-work" if breaking else "sound"  # 破壞性升版 = 消費端需行動（非 broken/sound）

    # 每個 breaking skill = 一個 Finding（P1：需 sync，非致命）；統計與表列自然一致
    p1 = len(breaking)
    fm = [
        "---",
        'title: "Alignment Notice — skill 破壞性升版"',
        "type: review",
        f'subject: "{rel}"',
        f"date: {today}",
        "author: ark-skills-align/notice_build.py",
        "source_skill: ark-skills-align",
        f"verdict: {verdict}",
        "confidence: high",
        "tags: [alignment, breaking-change, skills-sync]",
        f"sources: {json.dumps(['check_consumers（消費端掃描）', 'pre-push major 偵測'], ensure_ascii=False)}",
        f"findings: {{p0: 0, p1: {p1}, p2: 0, p3: 0}}",
        f"recipients: {json.dumps(recipients, ensure_ascii=False)}",
        f"affected: {json.dumps(affected, ensure_ascii=False)}",
        "---",
        "",
        "# Alignment Notice — skill 破壞性升版",
        "",
        "## Verdict",
        "",
        f"列車 `{rel}` 含 **{len(breaking)}** 個破壞性升版，影響 **{len(affected)}** 個消費端部署。"
        f"消費端需依下方 Actions 執行 `align_sync` 對齊——判定 **{verdict}**（需行動，非資料損毀）。",
        "",
        "## Findings",
        "",
    ]
    if breaking:
        fm += [
            "| ID | 嚴重度 | skill | 從 | 到 | 遷移指引 |",
            "|----|--------|-------|-----|-----|----------|",
        ]
        for n, b in enumerate(breaking, 1):
            fm.append(
                f"| F-{n} | P1 | {b.get('skill')} | {b.get('from', '?')} | {b.get('to', '?')} "
                f"| {b.get('migration', '見該 skill CHANGELOG ### Breaking')} |")
    else:
        fm.append("本次列車無破壞性升版，消費端無需 sync。")

    fm += ["", "## Evidence", ""]
    if breaking:
        for n, b in enumerate(breaking, 1):
            fm.append(f"- **E-{n}**（支持 F-{n}）：`check_consumers --name {b.get('skill')}` "
                      f"掃出 {len(affected)} 個已部署複本仍為舊版；pre-push 偵測到 major 升版 "
                      f"{b.get('from', '?')} → {b.get('to', '?')}。")
    else:
        fm.append("（無破壞性變更，無需證據）")

    fm += ["", "## Actions", ""]
    if breaking:
        fids = "、".join(f"F-{n}" for n in range(1, len(breaking) + 1))
        fm += [
            "| ID | 動作 | 對應 Finding | 負責 |",
            "|----|------|--------------|------|",
            f"| A-1 | 該部署 manager（`<專案>-agent`）改 `skills-matrix.yaml` 的 release | {fids} | 各消費端 manager |",
            f"| A-2 | `align_sync.py plan --waves` → 逐波 `apply --wave N --yes`（私訊 manager 確認，C-5） | {fids} | 各消費端 manager |",
            f"| A-3 | `align_sync.py verify` 直到 P0/P1=0 才算對齊完成 | {fids} | 各消費端 manager |",
        ]
    else:
        fm.append("無需行動。")

    fm += ["", "## 邊界聲明", "",
           "- 本通知僅宣告破壞性升版與影響面，**不代消費端執行 sync**（各 manager 自行決定時機）。",
           "- `affected` 清單為 `check_consumers` 掃描當下的部署複本，實際版本以各端 `skills.lock.json` 為準。",
           "- 消費端若已透過 `policy: sync` 於重啟時自動重建，可能已對齊，無需重複 apply。",
           ""]
    return "\n".join(fm)


def main() -> int:
    ap = argparse.ArgumentParser(description="產 Alignment Notice")
    ap.add_argument("impact", help="消費端影響 JSON（release/breaking/affected/recipients）")
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
