#!/usr/bin/env python3
"""gs_draft — game-analysis.yaml + kb-refs.yaml → game-spec.draft.md（deterministic 渲染，不呼叫 LLM）。

用法:
  python gs_draft.py --run artifacts/cva/<run_id>
章節順序來自 resolved pack（_core 通用節 + domain 錨點插入）。每個 claim 落在 provenance 區塊：
  ### OBSERVED / INFERRED   ← game-analysis 的 claims / entities
  ### FROM_KB               ← kb-refs 命中的頁
  ### PROPOSED              ← KB 頁 `proposes` 中、對應 claim 目前為 UNKNOWN 的建議（basis = KB id + item evidence）
  ### UNKNOWN               ← UNKNOWN / NOT_OBSERVED claims，各配一個 Q
渲染完自動跑 spec_lint；有 error 仍寫檔但 exit 3（agent 需修 pack / 重跑 analyze，不可手改 spec 繞 lint）。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gs_common as C  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent


def fmt_val(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, list):
        return "[" + ", ".join(str(x) for x in v) + "]"
    return str(v)


def render(resolved: dict, analysis: dict, kb: dict, manifest: dict, evidence: list[dict]) -> tuple[str, dict]:
    items = {i["id"]: i for i in analysis["items"]}
    kb_by_item = {r["item_id"]: r for r in kb.get("items", [])}
    declared = {c["key"] for i in resolved["analysis"]["items"] for c in i.get("claims", [])}
    used_ev, questions, qn = set(), [], 0
    proposed: list[dict] = []
    q_of: dict[str, str] = {}
    seen_item_in_section: set[str] = set()
    out = []

    def question_for(key: str, item, kind: str) -> str:
        nonlocal qn
        if key in q_of:
            return q_of[key]
        qn += 1
        q = f"Q{qn:03d}"
        q_of[key] = q
        questions.append({"id": q, "key": key, "item": item, "kind": kind})
        return q
    fm = {"type": "game-spec", "stage": "draft", "contract": C.CONTRACT, "run_id": analysis["run_id"], "domain": analysis["domain"],
          "pack_version": analysis.get("pack_version"), "pack_sha256": analysis.get("pack_sha256"), "model": analysis.get("model"),
          "video_sha256": manifest["video"]["sha256"]}
    out.append("---\n" + "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in fm.items()) + "\n---\n")
    out.append(f"# Game Spec Draft — {resolved['display_name']} — {analysis['run_id']}\n")
    out.append("> 每一條主張都在 provenance 區塊內；沒有 evidence 的數字不會出現在本文件。UNKNOWN 對應 Open Questions 的 Q。\n")

    for sec in resolved["spec"]["sections"]:
        sp = sec.get("special")
        out.append(f"\n## {sec['number']}. {sec['title']}")
        out.append(f"<!-- section:{sec['id']} items:{','.join(sec.get('source_items') or [])}" + (f" special:{sp}" if sp else "") + " -->")
        if sp in ("evidence", "open_questions", "state_machine", "configuration"):
            out.append("")  # 填在最後 / 由專段處理
            continue
        blocks = {t: [] for t in C.TAGS}
        prefixes = sec.get("claim_prefixes") or []
        pick = lambda key: (not prefixes) or any(key.startswith(pf) for pf in prefixes)  # noqa: E731
        for iid in sec.get("source_items") or []:
            it = items.get(iid)
            if not it:
                continue
            show_entities = sec.get("entities") is True or (not prefixes and iid not in seen_item_in_section)
            seen_item_in_section.add(iid)
            for c in it["claims"]:
                if not pick(c["key"]):
                    continue
                if c["provenance"] in ("OBSERVED", "INFERRED"):
                    used_ev.update(c["evidence"])
                    line = f"`{c['key']}` = {fmt_val(c['value'])} — evidence: {', '.join(c['evidence'])}"
                    if c["provenance"] == "INFERRED" and c.get("reasoning"):
                        line += f" — reasoning: {c['reasoning']}"
                    line += f" — confidence: {c['confidence']}"
                    blocks[c["provenance"]].append(line)
                elif c["provenance"] in ("UNKNOWN", "NOT_OBSERVED"):
                    q = question_for(c["key"], iid, c["provenance"])
                    blocks["UNKNOWN"].append(f"`{c['key']}` — question: {q}")
            for e in (it["entities"] if show_entities else []):
                used_ev.update(e["evidence"])
                extra = " ".join(f"{k}={fmt_val(v)}" for k, v in e.items()
                                 if k not in ("id", "entity_type", "provenance", "evidence") and v not in (None, ""))
                tag = e["provenance"] if e["provenance"] in ("OBSERVED", "INFERRED") else "UNKNOWN"
                if tag == "UNKNOWN":
                    q = question_for(e["id"], iid, "entity")
                    blocks["UNKNOWN"].append(f"entity `{e['id']}` — question: {q}")
                else:
                    blocks[tag].append(f"entity `{e['id']}` = {e['entity_type']} {extra}".rstrip() + f" — evidence: {', '.join(e['evidence'])}")
            ref = kb_by_item.get(iid, {})
            unknown_keys = {c["key"] for c in it["claims"] if c["provenance"] in ("UNKNOWN", "NOT_OBSERVED") and pick(c["key"])}
            if prefixes and not any(pick(c["key"]) for c in it["claims"]) and not show_entities:
                continue
            item_ev = sorted({x for c in it["claims"] for x in c["evidence"]})[:3]
            for r in ref.get("refs", []):
                blocks["FROM_KB"].append(f"`{r['id']}` {r.get('title') or ''} — tags: {', '.join(r.get('tags_hit') or [])} — trust: {r.get('trust')}"
                                         + (" — cross-domain" if r.get("cross_domain") else ""))
                for pr in r.get("proposes") or []:
                    if pr.get("key") in unknown_keys and pr.get("key") in declared:
                        basis = ", ".join([r["id"]] + item_ev)
                        proposed.append({"key": pr["key"], "value": pr.get("value"), "kb": r["id"], "section": sec["id"]})
                        blocks["PROPOSED"].append(f"`{pr['key']}` = {fmt_val(pr.get('value'))} — rationale: 依 {r['id']} 的 pattern 建議，影片未觀察到"
                                                  f" — basis: {basis} — confidence: {pr.get('confidence', 'medium')}")
        wrote = False
        for tag in ("OBSERVED", "INFERRED", "FROM_KB", "PROPOSED", "UNKNOWN"):
            if blocks[tag]:
                wrote = True
                out.append(f"\n### {tag}")
                out.extend(f"- {b}" for b in blocks[tag])
        if not wrote:
            out.append("\n### UNKNOWN")
            q = question_for(sec["id"], None, "section")
            out.append(f"- `{sec['id']}` — question: {q}")

    # 專段：state machine
    sm = resolved["spec"].get("state_machine") or ""
    claim_ev = {c["key"]: c["evidence"] for it in analysis["items"] for c in it["claims"]}
    import re
    sm_filled = re.sub(r"\{\{evidence:([\w.]+)\}\}", lambda m: "[" + (", ".join(claim_ev.get(m.group(1)) or ["UNKNOWN"])) + "]", sm)
    text = "\n".join(out)
    sm_idx = text.index("special:state_machine -->") + len("special:state_machine -->")
    text = text[:sm_idx] + "\n\n```mermaid\n" + sm_filled.strip() + "\n```\n" + text[sm_idx:]
    # 專段：configuration（數值型 claim → 參數候選；value 一律留給 config-spec.yaml 的 null）
    cfg = []
    for it in analysis["items"]:
        for c in it["claims"]:
            if c["provenance"] in ("OBSERVED", "INFERRED") and isinstance(c["value"], (int, float)) and not isinstance(c["value"], bool):
                cfg.append(f"- `{c['key']}` = {fmt_val(c['value'])} — evidence: {', '.join(c['evidence'])} — confidence: {c['confidence']}")
    cfg_block = "\n\n### OBSERVED\n" + "\n".join(cfg)
    if not cfg:
        q = question_for("configuration", None, "section")
        cfg_block = f"\n\n### UNKNOWN\n- `configuration` — question: {q}"
    ci = text.index("special:configuration -->") + len("special:configuration -->")
    text = text[:ci] + cfg_block + "\n" + text[ci:]
    # 專段：evidence
    ev_rows = ["| id | type | time | extractor | observation |", "|----|------|------|-----------|-------------|"]
    for e in evidence:
        if e["evidence_id"] in used_ev:
            ev_rows.append(f"| {e['evidence_id']} | {e['type']} | {e['t_start']} | {e.get('extractor', '')} | {'; '.join(e.get('observation') or [])[:120]} |")
    ei = text.index("special:evidence -->") + len("special:evidence -->")
    text = text[:ei] + "\n\n" + "\n".join(ev_rows) + f"\n\n共引用 {len(used_ev)} / {len(evidence)} 筆 evidence。\n" + text[ei:]
    # 專段：open questions
    qs = [f"- {q['id']} `{q['key']}` — 影片未提供足夠資訊" + (f"（item {q['item']}）" if q["item"] else "（整節無內容）") for q in questions]
    oi = text.index("special:open_questions -->") + len("special:open_questions -->")
    text = text[:oi] + "\n\n" + ("\n".join(qs) if qs else "- 無") + "\n" + text[oi:]
    return text + "\n", {"questions": questions, "used_evidence": sorted(used_ev), "proposed": proposed}


def main() -> None:
    ap = argparse.ArgumentParser(description="render spec draft")
    ap.add_argument("--run", required=True)
    ap.add_argument("--no-lint", action="store_true", help="只渲染不 lint（除錯用；正式流程不可）")
    a = ap.parse_args()
    run = C.run_dir(a.run)
    resolved = C.load_resolved(run)
    for f in ("game-analysis.yaml", "kb-refs.yaml"):
        if not (run / f).exists():
            C.fail("BAD_INPUT", f"缺 {f}", "先跑 ark-game-analysis/scripts/ga_run.py")
    analysis = C.yaml_load(run / "game-analysis.yaml")
    kb = C.yaml_load(run / "kb-refs.yaml")
    with C.Timer() as t:
        text, meta = render(resolved, analysis, kb, C.load_manifest(run), C.evidence_view(run))
    C.atomic_write(run / "game-spec.draft.md", text)
    C.atomic_write(run / "spec-draft.meta.json", json.dumps(meta, ensure_ascii=False))
    mm = C.load_manifest(run)
    mm.setdefault("skill_versions", {})["ark-game-spec"] = C.SKILL_VERSION
    C.save_manifest(run, mm)
    C.stage_record(run, "draft", t.elapsed_ms, questions=len(meta["questions"]), used_evidence=len(meta["used_evidence"]))
    data = {"file": "game-spec.draft.md", "sections": len(resolved["spec"]["sections"]), "open_questions": len(meta["questions"]),
            "used_evidence": len(meta["used_evidence"])}
    if a.no_lint:
        C.emit(data, {"stage": "draft", "elapsed_ms": t.elapsed_ms, "lint": "skipped"})
    r = subprocess.run([sys.executable, str(HERE / "spec_lint.py"), "--run", str(run), "--spec", "game-spec.draft.md"],
                       capture_output=True, text=True, encoding="utf-8")
    try:
        lint = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        C.fail("QUERY_FAILED", f"spec_lint 無輸出: {r.stderr[-300:]}", "")
    data["lint"] = lint.get("data", {}).get("summary") if lint.get("success") else lint.get("data", {}).get("summary")
    if not lint.get("success"):
        C.fail("GATE_BLOCKED", "Draft 未通過 spec_lint", "讀 review-report.json 的 violations；修 pack / 重跑 analyze，不可手改 spec 繞 lint", data=data)
    C.emit(data, {"stage": "draft", "elapsed_ms": t.elapsed_ms})


if __name__ == "__main__":
    main()
