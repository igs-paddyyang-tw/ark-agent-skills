#!/usr/bin/env python3
"""gs_review — Draft 的審查報告（deterministic 為主，--llm 可加 advisory 評論）→ review-report.md（+ 更新 review-report.json）。

用法:
  python gs_review.py --run artifacts/cva/<run_id> [--llm]
內容：lint 摘要、Missing Information（UNKNOWN 清單，附 KB 建議）、低信心主張、只靠單一 evidence 的主張、
domain 可疑（UNKNOWN > 60%）、給 grill-me 的提問清單（Q → 建議決策選項）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gs_common as C  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="review draft")
    ap.add_argument("--run", required=True)
    ap.add_argument("--spec", default="game-spec.draft.md")
    ap.add_argument("--llm", action="store_true", help="加一段 advisory LLM 評論（不影響 gate）")
    a = ap.parse_args()
    run = C.run_dir(a.run)
    resolved = C.load_resolved(run)
    rep_p = run / "review-report.json"
    if not rep_p.exists():
        C.fail("BAD_INPUT", "缺 review-report.json", "先跑 gs_draft.py（會自動 lint）")
    rep = json.loads(rep_p.read_text(encoding="utf-8"))
    analysis = C.yaml_load(run / "game-analysis.yaml")
    kb = C.yaml_load(run / "kb-refs.yaml")
    meta = json.loads((run / "spec-draft.meta.json").read_text(encoding="utf-8"))
    kb_by_item = {r["item_id"]: r for r in kb.get("items", [])}
    s = rep["summary"]
    lines = [f"# Review Report — {resolved['display_name']} — {analysis['run_id']}", "",
             f"- spec: `{a.spec}` · lint errors: **{s['errors']}** · warnings: {s['warnings']}",
             f"- claims: {s['claims']} · coverage(all): **{s['coverage_all']:.0%}** · coverage(known): {s['coverage_known']:.0%} · UNKNOWN: {s['unknown_ratio']:.0%}",
             f"- open questions: {s['open_questions']} · sections: {s['sections']}", ""]
    if s["unknown_ratio"] > 0.6:
        lines += ["> ⚠️ UNKNOWN 佔比 > 60%：domain 可能判錯（manifest.detect）或素材不足（見 pack eval/dataset.md）。", ""]
    if rep["violations"]:
        lines += ["## Lint violations", "", "| severity | rule | section | line | message |", "|---|---|---|---|---|"]
        lines += [f"| {v['severity']} | {v['rule']} | {v.get('section') or ''} | {v.get('line') or ''} | {v['message']} |" for v in rep["violations"]]
        lines.append("")
    # Missing information
    lines += ["## Missing Information（UNKNOWN → Open Questions）", ""]
    low_conf, single_ev = [], []
    for it in analysis["items"]:
        for c in it["claims"]:
            if c["provenance"] in ("OBSERVED", "INFERRED"):
                if c["confidence"] == "low":
                    low_conf.append((it["id"], c))
                if len(c["evidence"]) == 1:
                    single_ev.append((it["id"], c))
    for q in meta["questions"]:
        sugg = []
        for r in kb_by_item.get(q.get("item") or "", {}).get("refs", []):
            for pr in r.get("proposes") or []:
                if pr.get("key") == q["key"]:
                    sugg.append(f"{r['id']} 建議 `{q['key']}` = {pr.get('value')}（{pr.get('confidence', 'medium')}）")
        lines.append(f"- **{q['id']}** `{q['key']}`" + (f"（item {q['item']}）" if q.get("item") else "") + (" — KB: " + "；".join(sugg) if sugg else ""))
    lines.append("")
    lines += ["## 低信心主張（confidence: low）", ""] + ([f"- {i} `{c['key']}` = {c['value']} — {', '.join(c['evidence'])}" for i, c in low_conf] or ["- 無"]) + [""]
    lines += ["## 只靠單一 evidence 的主張", ""] + ([f"- {i} `{c['key']}` = {c['value']} — {c['evidence'][0]}" for i, c in single_ev] or ["- 無"]) + [""]
    lines += ["## 給 ark-grill-me 的決議清單", "", "每題可選：accept（採 PROPOSED）/ modify（給值）/ reject / defer（阻斷 dev-spec）。", ""]
    lines += [f"- {q['id']} `{q['key']}`" for q in meta["questions"]]
    lines.append("")
    llm_note = None
    if a.llm:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "ark-game-analysis", "scripts"))
        try:
            from llm_adapter import Adapter, LLMError
            ad = Adapter(run, resolved["pack_sha256"], resolved["extraction"]["budget"])
            md = (run / a.spec).read_text(encoding="utf-8")
            res = ad.complete_json("你是資深遊戲企畫審稿人。只輸出 JSON {\"comments\":[{\"section\":..,\"comment\":..}],\"risks\":[..]}。不得新增任何數字或規則主張。",
                                   f"審閱以下規格草稿，指出邏輯矛盾、缺漏、對研發不清楚之處：\n\n{md[:20000]}", None,
                                   fake_key="review", fake_fn=lambda: {"comments": [], "risks": ["fake provider"]})
            llm_note = res
            lines += ["## LLM Review（advisory，不影響 gate）", ""]
            lines += [f"- [{c.get('section')}] {c.get('comment')}" for c in res.get("comments", [])] or ["- 無評論"]
            lines += [""] + [f"- risk: {r}" for r in res.get("risks", [])] + [""]
        except Exception as e:  # noqa: BLE001
            lines += ["## LLM Review", "", f"- 未執行：{e}", ""]
    C.atomic_write(run / "review-report.md", "\n".join(lines))
    rep["review"] = {"low_confidence": len(low_conf), "single_evidence": len(single_ev), "llm": llm_note}
    C.atomic_write(rep_p, json.dumps(rep, ensure_ascii=False, indent=1))
    C.stage_record(run, "review", 0, low_confidence=len(low_conf), single_evidence=len(single_ev))
    C.emit({"file": "review-report.md", "summary": s, "low_confidence": len(low_conf), "single_evidence": len(single_ev),
            "open_questions": len(meta["questions"]), "next": "人員以 ark-grill-me 逐題決議 → decisions.yaml → gs_decide.py"}, {"stage": "review"})


if __name__ == "__main__":
    main()
