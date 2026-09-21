#!/usr/bin/env python3
"""aiqa_report — run 目錄 → test-report.md + test-results.xlsx（公司欄位回填）+ mantis-drafts.md + benchmark.json。

用法:
  python aiqa_report.py --run artifacts/aiqa/<run_id> [--baseline-xlsx 原測試表.xlsx]
報告順序刻意：摘要 → 依分類樹統計 → FAIL → 與人工不一致 → NEEDS_HUMAN → BLOCK → FLAKY → N/A → 附錄。
誤 PASS（人 fail、aiqa PASS）單獨計數，永遠在第一頁。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aiqa_common as C  # noqa: E402

ORDER = ["PASS", "FAIL", "FLAKY", "NEEDS_HUMAN", "BLOCK", "NA"]


def load_run(run: pathlib.Path) -> tuple[dict, list[dict], dict]:
    m = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    r = json.loads((run / "results.json").read_text(encoding="utf-8"))["results"] if (run / "results.json").exists() else []
    doc = json.loads(pathlib.Path(m["checklist"]).read_text(encoding="utf-8")) if pathlib.Path(m["checklist"]).exists() else {"items": []}
    return m, r, doc


def compare_baseline(results: list[dict]) -> dict:
    agree = disagree = compared = false_pass = 0
    rows = []
    for r in results:
        b = (r.get("baseline") or {}).get("android")
        if b not in ("pass", "fail") or r["verdict"] in ("NEEDS_HUMAN", "BLOCK", "NA"):
            continue
        compared += 1
        ai = "pass" if r["verdict"] == "PASS" else "fail"
        if ai == b:
            agree += 1
        else:
            disagree += 1
            rows.append({"id": r["id"], "title": r["title"], "human": b, "aiqa": r["verdict"], "reason": r.get("reason")})
            if b == "fail" and ai == "pass":
                false_pass += 1
    return {"compared": compared, "agree": agree, "disagree": disagree, "false_pass": false_pass,
            "agreement_rate": round(agree / compared, 3) if compared else None, "rows": rows}


def failed_assertions(r: dict) -> list[dict]:
    return [{**a, "rep": rep["rep"]} for rep in r.get("reps", []) for a in rep.get("assertions", []) if a["result"] in ("FAIL", "NEEDS_HUMAN", "ERROR")]


def evidence_of(run: pathlib.Path, r: dict) -> list[str]:
    out = []
    for rep in r.get("reps", []):
        vp = run / "items" / r["id"] / f"rep-{rep['rep']}" / "verdict.json"
        if vp.exists():
            for e in json.loads(vp.read_text(encoding="utf-8")).get("evidence", []):
                for k in ("crop", "screen"):
                    if e.get(k):
                        out.append(os.path.relpath(e[k], run))
    return list(dict.fromkeys(out))[:8]


def repro(run: pathlib.Path, r: dict) -> list[str]:
    tp = run / "items" / r["id"] / "rep-1" / "trace.jsonl"
    if not tp.exists():
        return []
    steps = []
    for l in tp.read_text(encoding="utf-8").splitlines():
        t = json.loads(l)
        k = t["kind"]
        if k == "tap":
            steps.append(f"tap ({t['x']},{t['y']})")
        elif k == "key":
            steps.append(f"key {t['name']}")
        elif k in ("restart_app", "net"):
            steps.append(k + (" on" if t.get("on") else " off" if k == "net" else ""))
        elif k == "wait_stable":
            steps.append("等待畫面靜止")
    # 壓縮連續重複
    out = []
    for s in steps:
        if out and out[-1].startswith(s) and out[-1].endswith(")"):
            continue
        out.append(s)
    return out[:25]


def render_md(run: pathlib.Path, m: dict, results: list[dict], doc: dict, cmp: dict) -> str:
    counts = {v: sum(1 for r in results if r["verdict"] == v) for v in ORDER}
    executed = sum(1 for r in results if r["verdict"] not in ("NA", "BLOCK"))
    auto = counts["PASS"] + counts["FAIL"] + counts["FLAKY"]
    L = ["---", "type: test-report", f"contract: \"{C.CONTRACT}\"", f"run_id: {m['run_id']}", f"game: {m.get('game')}", f"machine: {m.get('machine')}",
         f"backend: {m.get('backend')} · device: {m.get('device')} · reader: {m.get('reader')} · visual: {m.get('visual')}",
         f"checklist: {m.get('checklist')} @ {str(m.get('checklist_sha256'))[:16]}", f"pack_sha256: {m.get('pack_sha256')}", f"protocol: {m.get('protocol')}",
         f"model: {(m.get('llm') or {}).get('model')}", f"started: {m.get('created_at')} · finished: {m.get('finished_at')}", "---", "",
         f"# 測試報告 — {m.get('game')}" + (f" / {m.get('machine')}" if m.get("machine") else "") + f" — run {m['run_id']}", "",
         "> 所有 PASS 皆附證據路徑；NEEDS_HUMAN 不計入 PASS；視覺斷言不單獨撐 PASS。", "",
         "| 摘要 | 值 |", "|---|---|",
         f"| 測試項總數 / 本 run 執行 | {len(results)} / {executed} |",
         f"| PASS / FAIL / FLAKY / NEEDS_HUMAN / BLOCK / N/A | {' / '.join(str(counts[v]) for v in ORDER)} |",
         f"| 自動化率（得出 PASS/FAIL/FLAKY 判定 / 全部） | {round(auto / max(1, len(results)) * 100)}% |",
         f"| 與人工結果一致率（{cmp['compared']} 項可比） | {f'{cmp['agreement_rate']:.0%}' if cmp['agreement_rate'] is not None else '—'}（不一致 {cmp['disagree']}） |",
         f"| **誤 PASS（人 fail、aiqa PASS）** | **{cmp['false_pass']}** |",
         f"| 執行時間 / LLM 呼叫 | {m.get('elapsed_s')} s / {(m.get('llm') or {}).get('llm_calls', 0)} |", ""]
    # 分類樹
    L += ["## 1. 依公司分類樹（可貼回 xlsx 總進度頁）", "", "| 類別 | 項目 | 測項 | PASS | FAIL | FLAKY | NEEDS_HUMAN | BLOCK | N/A | 進度 |", "|---|---|---|---|---|---|---|---|---|---|"]
    groups: dict[tuple, list] = {}
    for r in results:
        groups.setdefault((r.get("category") or "", r.get("folder") or ""), []).append(r)
    for (cat, fol), rs in sorted(groups.items()):
        c = {v: sum(1 for r in rs if r["verdict"] == v) for v in ORDER}
        done = sum(1 for r in rs if r["verdict"] != "BLOCK")
        L.append(f"| {cat} | {fol} | {len(rs)} | {c['PASS']} | {c['FAIL']} | {c['FLAKY']} | {c['NEEDS_HUMAN']} | {c['BLOCK']} | {c['NA']} | {round(done / len(rs) * 100)}% |")
    L.append("")

    def section(title, verdict, with_detail=True):
        rs = [r for r in results if r["verdict"] == verdict]
        L.append(f"## {title}（{len(rs)}）"); L.append("")
        if not rs:
            L.append("- 無"); L.append(""); return
        for r in rs:
            L.append(f"### {r['id']} {r['title']} — {verdict}")
            L.append(f"- 分類：{r.get('category')} / {r.get('folder')} · tier {r.get('tier')} · 原因：{r.get('reason')}")
            if with_detail:
                for a in failed_assertions(r):
                    L.append(f"- rep{a['rep']} {a['id']} `{a['oracle']}` 期望「{a.get('expect')}」→ {a['result']}：{str(a.get('detail'))[:200]} · {a.get('spec_ref') or ''}")
                ev = evidence_of(run, r)
                if ev:
                    L.append("- 證據：" + " · ".join(f"`{e}`" for e in ev))
                rp = repro(run, r)
                if rp:
                    L.append("- 重現：" + " → ".join(rp))
                b = (r.get("baseline") or {})
                if b.get("android"):
                    L.append(f"- 人工結果對照：{b['android']}（{b.get('tester') or ''} {b.get('date') or ''}）" + (f" · Mantis {b['mantis']}" if b.get("mantis") else ""))
            L.append("")

    section("2. FAIL", "FAIL")
    L += ["## 3. 與人工結果不一致 — 最高優先看", ""]
    if cmp["rows"]:
        L += ["| id | 測試目的 | 人工 | aiqa | 原因 |", "|---|---|---|---|---|"] + [f"| {x['id']} | {x['title']} | {x['human']} | {x['aiqa']} | {x['reason']} |" for x in cmp["rows"]]
    else:
        L.append("- 無（可比 %d 項）" % cmp["compared"])
    L.append("")
    section("4. NEEDS_HUMAN（視覺信心不足 / 讀數失敗，附裁切圖）", "NEEDS_HUMAN")
    section("5. BLOCK（缺 harness / 未綁定步驟 / 前置達不到）", "BLOCK", with_detail=False)
    section("6. FLAKY（重複結果不一致）", "FLAKY")
    L += ["## 7. N/A", ""]
    nas = [r for r in results if r["verdict"] == "NA"]
    by = {}
    for r in nas:
        by[r.get("reason")] = by.get(r.get("reason"), 0) + 1
    L += [f"- {k}：{v} 項" for k, v in sorted(by.items(), key=lambda x: -x[1])] or ["- 無"]
    L += ["", "## 8. 附錄", "",
          f"- 環境：backend {m.get('backend')} · device {m.get('device')} · reader {m.get('reader')} · visual {m.get('visual')} · protocol {m.get('protocol')} · skill v{m.get('skill_version')}",
          f"- 產出：`test-results.xlsx`（公司欄位回填）· `mantis-drafts.md` · `benchmark.json` · `items/<id>/rep-k/`（截圖、裁切、observations、verdict、trace）",
          "- 判定原則：視覺斷言不單獨撐 PASS；讀數 null → NEEDS_HUMAN；重複不一致 → FLAKY；未綁定 / 無 harness → BLOCK（不假裝跑）。", ""]
    return "\n".join(L)


def write_xlsx(run: pathlib.Path, m: dict, results: list[dict], doc: dict) -> str | None:
    try:
        import openpyxl
    except ImportError:
        return None
    items = {i["id"]: i for i in doc.get("items", [])}
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "aiqa結果"
    ws.append(["編號", "類別", "項目", "測試目的", "步驟", "重複次數", "預期結果", "執行人員", "Android", "iOS", "測試日期", "備註", "Mantis單號", "aiqa verdict", "證據"])
    for n, r in enumerate(results, 1):
        it = items.get(r["id"], {})
        steps = "\n".join(it.get("manual_steps") or [a.get("do") + " " + str({k: v for k, v in a.items() if k != "do"}) for a in it.get("actions", [])])
        expected = "\n".join(f"{a['id']}. {a.get('expect', '')}" for a in it.get("assertions", []))
        verdict = r["verdict"]
        android = {"PASS": "pass", "FAIL": "fail", "NA": "N/A", "BLOCK": "block"}.get(verdict, "")
        ws.append([it.get("source_row") or n, r.get("category"), r.get("folder"), r["title"], steps, it.get("repeat", 1), expected, "aiqa",
                   android, "", m.get("finished_at", "")[:10], r.get("reason"), (r.get("baseline") or {}).get("mantis") or "", verdict,
                   "; ".join(evidence_of(run, r)[:3])])
    ws2 = wb.create_sheet("總進度")
    ws2.append(["項次", "項目頁籤", "原測項數量", "測項數量", "已完成數量", "PASS", "FAIL", "N/A", "BLOCK", "進度"])
    done = sum(1 for r in results if r["verdict"] != "BLOCK")
    c = {v: sum(1 for r in results if r["verdict"] == v) for v in ORDER}
    ws2.append([1, m.get("machine") or m.get("game"), len(doc.get("items", [])), len(results), done, c["PASS"], c["FAIL"], c["NA"], c["BLOCK"], f"{round(done / max(1, len(results)) * 100)}%"])
    out = run / "test-results.xlsx"; wb.save(out)
    return str(out)


def write_mantis(run: pathlib.Path, m: dict, results: list[dict], doc: dict) -> str:
    items = {i["id"]: i for i in doc.get("items", [])}
    L = [f"# Mantis 草稿 — {m.get('game')} / {m.get('machine')} — run {m['run_id']}", ""]
    for r in [r for r in results if r["verdict"] == "FAIL"]:
        it = items.get(r["id"], {})
        L += [f"## {r['id']} {r['title']}", "", f"**摘要**：[{r.get('folder')}] {r['title']} — aiqa 自動測試 FAIL", "",
              "**重現步驟**：", *[f"{i}. {s}" for i, s in enumerate(it.get("manual_steps") or repro(run, r), 1)], "",
              "**期望**：", *[f"- {a.get('expect')}" for a in it.get("assertions", [])], "",
              "**實際**：", *[f"- rep{a['rep']} {a['id']}：{str(a.get('detail'))[:200]}" for a in failed_assertions(r) if a["result"] == "FAIL"], "",
              "**附件**：", *[f"- {e}" for e in evidence_of(run, r)], "",
              f"**環境**：{m.get('backend')} {m.get('device')} · run {m['run_id']} · pack {str(m.get('pack_sha256'))[:12]}", "", "---", ""]
    out = run / "mantis-drafts.md"; C.atomic_write(out, "\n".join(L)); return str(out)


def main() -> None:
    ap = argparse.ArgumentParser(description="aiqa report")
    ap.add_argument("--run", required=True)
    a = ap.parse_args()
    run = pathlib.Path(a.run)
    if not (run / "manifest.json").exists():
        C.fail("BAD_INPUT", f"不是 run 目錄: {run}", "先跑 aiqa_run.py")
    m, results, doc = load_run(run)
    cmp = compare_baseline(results)
    with C.Timer() as t:
        md = render_md(run, m, results, doc, cmp)
        C.atomic_write(run / "test-report.md", md)
        xlsx = write_xlsx(run, m, results, doc)
        mantis = write_mantis(run, m, results, doc)
        counts = {v: sum(1 for r in results if r["verdict"] == v) for v in ORDER}
        tiers = {}
        for r in results:
            tiers.setdefault(r.get("tier"), {}).setdefault(r["verdict"], 0)
            tiers[r["tier"]][r["verdict"]] += 1
        bench = {"contract": C.CONTRACT, "run_id": m["run_id"], "game": m.get("game"), "machine": m.get("machine"), "backend": m.get("backend"),
                 "items": len(results), "counts": counts,
                 "M1_automation_rate": round((counts["PASS"] + counts["FAIL"] + counts["FLAKY"]) / max(1, len(results)), 3),
                 "M2_false_pass": cmp["false_pass"], "M3_agreement_rate": cmp["agreement_rate"], "M3_compared": cmp["compared"],
                 "M4_needs_human": counts["NEEDS_HUMAN"], "M6_seconds_per_item": round(m.get("elapsed_s", 0) / max(1, len(results)), 1),
                 "M7_flaky_rate": round(counts["FLAKY"] / max(1, len(results)), 3), "by_tier": tiers, "llm": m.get("llm")}
        C.atomic_write(run / "benchmark.json", json.dumps(bench, ensure_ascii=False, indent=1))
    C.emit({"report": str(run / "test-report.md"), "xlsx": xlsx, "mantis": mantis, "benchmark": str(run / "benchmark.json"), "counts": counts,
            "false_pass": cmp["false_pass"], "agreement_rate": cmp["agreement_rate"]}, {"stage": "report", "elapsed_ms": t.elapsed_ms})


if __name__ == "__main__":
    main()
