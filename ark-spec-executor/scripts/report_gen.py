#!/usr/bin/env python3
"""report_gen.py — 驗收報告 + pipeline 狀態 + 迴圈判定

Usage:
    python report_gen.py <plan.md> --workspace <ws> [--out docs/reports/<name>-acceptance.md] [--no-pipeline]

讀 data/<plan>-progress.json → 產：
    - docs/reports/<name>-acceptance.md（摘要表 / 任務結果 / 未通過清單含證據 / 人工待辦）
    - docs/pipeline/<feature>.yaml：phase=execute、append acceptance_rates、acceptance_report_path（不存在則建立）
    - 迴圈判定：閾值從 ark-code-spec-validator/references/loop-rules.md 解析（找不到用 90/70 並警告），不硬編碼

acceptance_rate = pass / total × 100（total 含 human/pending；blocked 列入未通過——loop-rules 定義）
exit：0 產出成功；1 讀不到 checkpoint
"""
import sys

if __name__ == "__main__" and ({"-h", "--help"} & set(sys.argv[1:]) or len(sys.argv) < 2):
    print(__doc__ or "")
    raise SystemExit(0)

import json
import re
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def opt(argv, name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


def thresholds() -> tuple[int, int, str]:
    for cand in [HERE.parent.parent / "ark-code-spec-validator" / "references" / "loop-rules.md",
                 Path(".kiro/skills/ark-code-spec-validator/references/loop-rules.md"),
                 Path("skills/ark-code-spec-validator/references/loop-rules.md")]:
        if cand.exists():
            txt = cand.read_text(encoding="utf-8")
            ship = re.search(r"\*\*≥\s*(\d+)\*\*", txt)
            mid = re.search(r"\*\*(\d+)\s*[–-]\s*(\d+)\*\*", txt)
            if ship and mid:
                return int(ship.group(1)), int(mid.group(1)), str(cand)
    return 90, 70, "（未找到 loop-rules.md，使用預設 90/70）"


def decide(rate: float, ship: int, retry: int) -> tuple[str, str]:
    if rate >= ship:
        return "ship", f"≥ {ship}：自動觸發 ark-code-spec-validator 做最終 drift check"
    if rate >= retry:
        return "retry_failed", f"{retry}–{ship - 1}：產修復清單，重跑失敗項（run_plan.py --resume）"
    return "stop", f"< {retry}：停止，依 loop-rules 方向分流（missing_in_code → 回 executor；mismatch → grill-me）"


def write_pipeline(ws: Path, feature: str, plan_path: Path, report_rel: str, rate: float) -> Path:
    p = ws / "docs" / "pipeline" / f"{feature}.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    if p.exists():
        txt = p.read_text(encoding="utf-8")
        txt = re.sub(r"^phase:.*$", "phase: execute", txt, flags=re.M)
        txt = re.sub(r"^updated_at:.*$", f'updated_at: "{now}"', txt, flags=re.M)
        if re.search(r"^acceptance_report_path:", txt, re.M):
            txt = re.sub(r"^acceptance_report_path:.*$", f"acceptance_report_path: {report_rel}", txt, flags=re.M)
        else:
            txt += f"\nacceptance_report_path: {report_rel}\n"
        if re.search(r"^acceptance_rates:", txt, re.M):
            txt = re.sub(r"^(acceptance_rates:\s*\n(?:  - .*\n)*)", lambda m: m.group(1) + f"  - {rate}\n", txt, flags=re.M)
        else:
            txt += f"acceptance_rates:\n  - {rate}\n"
        p.write_text(txt, encoding="utf-8")
    else:
        p.write_text(f"""feature: {feature}
phase: execute
plan_path: {plan_path}
acceptance_report_path: {report_rel}
drift_scores: []
acceptance_rates:
  - {rate}
loop_count: 0
created_at: "{now}"
updated_at: "{now}"
""", encoding="utf-8")
    return p


def main() -> int:
    argv = sys.argv[1:]
    plan_path = Path(argv[0])
    ws = Path(opt(argv, "--workspace", ".")).resolve()
    ckpt_p = ws / "data" / f"{plan_path.stem}-progress.json"
    if not ckpt_p.exists():
        print(f"❌ 找不到 checkpoint {ckpt_p}（先 run_plan.py）"); return 1
    ckpt = json.loads(ckpt_p.read_text(encoding="utf-8"))
    sys.path.insert(0, str(HERE))
    from plan_parse import load_plan
    plan = load_plan(ws / plan_path if not plan_path.is_absolute() else plan_path)
    tasks = {t["id"]: t for t in plan["tasks"]}
    recs = ckpt["tasks"]
    total = len(recs); passed = sum(r["status"] == "pass" for r in recs.values())
    rate = round(passed / total * 100, 1) if total else 0.0
    ship, retry, src = thresholds()
    direction, advice = decide(rate, ship, retry)
    name = plan["name"]
    out = Path(opt(argv, "--out", f"docs/reports/{name}-acceptance.md"))
    out_abs = ws / out if not out.is_absolute() else out
    out_abs.parent.mkdir(parents=True, exist_ok=True)

    counts = {k: sum(r["status"] == k for r in recs.values()) for k in ("pass", "fail", "blocked", "skipped", "pending")}
    L = [f"# 驗收報告：{plan['frontmatter'].get('title', name)}", "",
         f"> plan：`{plan_path}`　runner：{ckpt.get('runner')}　產出：{datetime.now().isoformat(timespec='minutes')}", "",
         "## 摘要", "", "| 指標 | 值 |", "|---|---|", f"| 總任務 | {total} |", f"| 通過 | {counts['pass']} |", f"| 失敗 | {counts['fail']} |",
         f"| 人工待辦（blocked） | {counts['blocked']} |", f"| 待驗（pending） | {counts['pending']} |", f"| 跳過（依賴失敗） | {counts['skipped']} |",
         f"| **acceptance_rate** | **{rate}%** |", f"| 迴圈判定 | `{direction}` — {advice} |", f"| 閾值來源 | {src} |", "",
         "## 任務結果", "", "| # | 任務 | 角色 | 狀態 | 驗證 | 次數 | 耗時 |", "|---|---|---|---|---|---|---|"]
    mark = {"pass": "✅ pass", "fail": "❌ fail", "blocked": "⏸ blocked", "skipped": "⤼ skipped", "pending": "⏸ pending"}
    for tid in plan["order"]:
        if tid not in recs: continue
        r = recs[tid]; t = tasks[tid]; v = r.get("verify", {})
        L.append(f"| {tid} | {t['name']} | {t['role']} | {mark[r['status']]} | {v.get('method', '—')} | {r.get('attempts', '—')} | {r.get('duration_ms', 0)}ms |")
    bad = [(tid, recs[tid]) for tid in plan["order"] if recs.get(tid, {}).get("status") in ("fail", "skipped", "pending")]
    if bad:
        L += ["", "## 未通過清單", ""]
        for tid, r in bad:
            t = tasks[tid]; v = r.get("verify", {})
            L += [f"### {tid} {t['name']}", f"- AC（{t.get('ac_id') or '—'}）：{t['ac']}", f"- 狀態：{r['status']}　方法：{v.get('method', '—')}　指令：`{v.get('command', '')}`"]
            if r.get("reason"): L.append(f"- 原因：{r['reason']}")
            if v.get("evidence"): L += ["- 證據：", "```", v["evidence"][:1200], "```"]
            if r.get("scope_violations"): L.append(f"- ⚠️ 越界寫入：{r['scope_violations']}")
            L.append("")
    hum = [(tid, recs[tid]) for tid in plan["order"] if recs.get(tid, {}).get("status") == "blocked"]
    if hum:
        L += ["## 人工待辦", ""] + [f"- [ ] {tid} {tasks[tid]['name']}：{tasks[tid]['ac']}" for tid, _ in hum] + [""]
    out_abs.write_text("\n".join(L), encoding="utf-8")
    print(f"✅ 報告 → {out_abs}\n   acceptance_rate={rate}%  判定={direction}")
    if "--no-pipeline" not in argv:
        pp = write_pipeline(ws, name, plan_path, str(out), rate)
        print(f"   pipeline → {pp}（phase=execute，acceptance_rates append）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
