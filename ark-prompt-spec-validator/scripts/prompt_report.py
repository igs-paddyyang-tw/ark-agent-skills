#!/usr/bin/env python3
"""prompt_report.py — merge L1 (prompt_lint) + L2 (prompt_eval) JSON into an ark-md-report `review` MD.

Usage:
  python prompt_report.py --l1 l1.json [--l2 l2.json] --subject <repo-relative-path>
                          --out docs/reports/review/<date>-prompt-drift-<slug>.md
                          [--title "..."] [--tags skill-review,prompt] [--log knowledge/.../prompt-drift-log.md]

Scoring (scoring_version 1): total = 0.4*L1 + 0.6*L2; no L2 → total = L1; any P0 → 0 / broken.
Afterwards run ark-md-report/scripts/report_lint.py then report_register.py on the output.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short=7", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "nogit"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--l1", required=True)
    ap.add_argument("--l2")
    ap.add_argument("--subject", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--title")
    ap.add_argument("--tags", default="skill-review,prompt")
    ap.add_argument("--log", help="pipe-delimited log 檔（append 一行）")
    a = ap.parse_args()

    l1 = json.loads(Path(a.l1).read_text(encoding="utf-8"))
    l2 = json.loads(Path(a.l2).read_text(encoding="utf-8")) if a.l2 else None
    s1 = l1["summary"]
    l1_score = s1["score"]
    l2_score = (l2["summary"]["deterministic"]["score"] if l2 else None)
    if s1["p0"]:
        total, verdict = 0, "broken"
    else:
        total = round(0.4 * l1_score + 0.6 * l2_score) if l2_score is not None else l1_score
        verdict = "sound" if total >= 90 else ("needs-work" if total >= 70 else "broken")
    today = dt.date.today().isoformat()
    sha = git_sha()

    # findings: L1 by rule, L2 failed cases
    findings = []
    for f in l1["findings"]:
        findings.append({"sev": f["severity"], "conf": f["confidence"], "where": f"{f['file']}:{f['line']}",
                         "desc": f"{f['rule']} {f['message']}", "ev": f"{f['file']} L{f['line']}"})
    if l2:
        for c in l2["cases"]:
            if c["ok"] is False:
                head = (c["failures"][0].get("fails") or [c["failures"][0].get("error", "")]) if c["failures"] else [""]
                findings.append({"sev": "P1", "conf": "high", "where": f"eval {c['id']}",
                                 "desc": f"{c['id']} [{c['intent']}] 通過率 {c['passed']}/{c['total']}：{'; '.join(map(str, head))[:120]}",
                                 "ev": (c["failures"][0].get("response_head", "") if c["failures"] else "")[:160]})
    order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    findings.sort(key=lambda x: order[x["sev"]])
    cnt = {k.upper(): sum(1 for f in findings if f["sev"] == k.upper()) for k in ("p0", "p1", "p2", "p3")}

    title = a.title or f"{a.subject} 提詞規格驗證"
    tags = ", ".join(t.strip() for t in a.tags.split(","))
    fm = [
        "---", f'title: "{title}"', "type: review", f'subject: "{a.subject}"', f"date: {today}",
        "author: claude", "source_skill: ark-prompt-spec-validator", f"verdict: {verdict}",
        "confidence: high" if not any(f["conf"] != "high" for f in findings) else "confidence: medium",
        f"findings: {{ p0: {cnt['P0']}, p1: {cnt['P1']}, p2: {cnt['P2']} }}", f"tags: [{tags}]",
        f"score: {total}", 'score_version: "v1"', "sources:", f"  - {a.subject}", f"  - {a.l1}",
    ]
    if a.l2:
        fm.append(f"  - {a.l2}")
    fm.append("---")

    body = [f"# {title}", "",
            "## Verdict", "",
            f"**{verdict}** — 總分 {total}/100（L1 靜態 {l1_score}" + (f"，L2 行為 {l2_score}" if l2_score is not None else "，無 L2") + f"）。"
            f"L1 P0:{s1['p0']} P1:{s1['p1']} P2:{s1['p2']} P3:{s1['p3']}"
            + (f"；L2 deterministic {l2['summary']['deterministic']['ok']}/{l2['summary']['deterministic']['total']}，llm-distilled {l2['summary']['llm_distilled']['ok']}/{l2['summary']['llm_distilled']['total']}（不計分）" if l2 else "")
            + f"。git {sha}。", "",
            "## Findings", "",
            "| ID | Severity | Confidence | 位置 | 描述 |", "|----|----------|------------|------|------|"]
    for i, f in enumerate(findings, 1):
        desc = f["desc"].replace("|", "\\|")
        body.append(f"| F-{i} | {f['sev']} | {f['conf']} | `{f['where']}` | {desc} |")
    if not findings:
        body.append("| — | — | — | — | 無 finding |")
    body += ["", "## Evidence", ""]
    for i, f in enumerate(findings, 1):
        if f["sev"] in ("P0", "P1"):
            ev = f["ev"].replace("\n", " ")
            body.append(f"- F-{i}：`{ev}`")
    if not any(f["sev"] in ("P0", "P1") for f in findings):
        body.append("- 無 P0/P1，無需證據區塊")
    body += ["", "## Actions", ""]
    n = 0
    if s1["p0"]:
        n += 1; body.append(f"- A-{n}：先清 P0（PL-001/002/003/004），再重跑 L1；P0 未清不進 L2（對應 F-1）")
    if s1["p1"]:
        n += 1; body.append(f"- A-{n}：修 L1 P1（placeholder / 路徑 / 觸發詞衝突 / 排除段），目標 P1 = 0")
    if l2 and any(c["ok"] is False for c in l2["cases"]):
        n += 1; body.append(f"- A-{n}：針對失敗 eval 案例修提詞或修斷言；每次改 description 加對應 trigger/no-trigger 案例")
    if not l2:
        n += 1; body.append(f"- A-{n}：補 `evals/<slug>.eval.yaml`，最少 2 trigger + 1 no-trigger + 1 boundary 案例，跑 prompt_eval.py 取得 L2")
    if n == 0:
        body.append("- A-1：無需行動；下次 description 變更時重跑 L1+L2 回歸")
    body += ["", "## 邊界聲明", "",
             f"- 分析基準：{today}，git {sha}，scoring_version 1（L1 0.4 / L2 0.6；無 L2 時總分 = L1）",
             "- 未涵蓋：程式碼與 spec 一致性（ark-code-spec-validator）、line coverage（ark-test-runner）、description 改寫（ark-skill-creator）",
             "- 不適用情境：L2 `judge` 結果為 llm-distilled，不進總分；PL-013 指令矛盾為 heuristic（confidence medium），需人工確認",
             "- 時效：被驗證檔或其引用的 skill 任一變更後，本結論失效，應重跑", ""]

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(fm + [""] + body), encoding="utf-8")

    if a.log:
        lp = Path(a.log); lp.parent.mkdir(parents=True, exist_ok=True)
        with lp.open("a", encoding="utf-8") as fh:
            fh.write(f"{today}|{sha}|{a.subject}|{total}|{l1_score}|{l2_score if l2_score is not None else 'N/A'}|{verdict}|1\n")

    emoji = {"sound": "✅", "needs-work": "⚠️", "broken": "❌"}[verdict]
    print(f"{emoji} 報告已落盤 {out}｜verdict: {verdict}｜score: {total}｜P0:{cnt['P0']} P1:{cnt['P1']}")
    print(f"下一步：python <ark-md-report>/scripts/report_lint.py {out}")


if __name__ == "__main__":
    main()
