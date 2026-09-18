#!/usr/bin/env python3
"""gs_decide — decisions.yaml 套用到 Draft → game-spec.v1.md（deterministic，重跑 bit-identical）。

用法:
  python gs_decide.py --run artifacts/cva/<run_id> [--decisions decisions.yaml] [--template]
decisions.yaml 契約：
  decisions:
    - {decision_id: D001, question_id: Q003, topic: free_spin.count_awarded, decision: accept|modify|reject|defer,
       value: 10, reason: "...", decided_by: "企畫 X", date: 2026-09-20, affects: [free_spin], domain: slot-game}
規則：accept → 該 key 的 PROPOSED 轉 DECIDED（無 PROPOSED 則需 value）；modify → DECIDED 用 value；
reject → PROPOSED 移除、UNKNOWN 保留並註記；defer → 保留 UNKNOWN，dev 階段阻斷。
--template：由 Open Questions 產出 decisions.template.yaml 供填寫。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gs_common as C  # noqa: E402

DECISIONS = ("accept", "modify", "reject", "defer")


def fmt_val(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, list):
        return "[" + ", ".join(str(x) for x in v) + "]"
    return str(v)


def main() -> None:
    ap = argparse.ArgumentParser(description="apply decisions")
    ap.add_argument("--run", required=True)
    ap.add_argument("--decisions", default="decisions.yaml")
    ap.add_argument("--template", action="store_true")
    a = ap.parse_args()
    run = C.run_dir(a.run)
    resolved = C.load_resolved(run)
    draft_p = run / "game-spec.draft.md"
    if not draft_p.exists():
        C.fail("BAD_INPUT", "缺 game-spec.draft.md", "先跑 gs_draft.py")
    meta = json.loads((run / "spec-draft.meta.json").read_text(encoding="utf-8"))
    if a.template:
        tpl = {"contract": C.CONTRACT, "run_id": C.load_manifest(run)["run_id"], "domain": resolved["domain"],
               "decisions": [{"decision_id": f"D{i:03d}", "question_id": q["id"], "topic": q["key"], "decision": "defer",
                              "value": None, "reason": "", "decided_by": "", "date": str(_dt.date.today()), "affects": [q.get("item")] if q.get("item") else [],
                              "domain": resolved["domain"]} for i, q in enumerate(meta["questions"], 1)]}
        C.atomic_write(run / "decisions.template.yaml", C.yaml_dump(tpl))
        C.emit({"file": "decisions.template.yaml", "count": len(tpl["decisions"]), "next": "填好後另存 decisions.yaml，再跑 gs_decide.py"})
    dp = run / a.decisions
    if not dp.exists():
        C.fail("BAD_INPUT", f"缺 {a.decisions}", "gs_decide.py --template 產範本；或由 ark-grill-me 產出")
    dec = C.yaml_load(dp)
    ds = dec.get("decisions") or []
    errors = []
    q_valid = {q["id"]: q for q in meta["questions"]}
    seen = set()
    for d in ds:
        for k in ("decision_id", "question_id", "topic", "decision", "reason", "decided_by", "date"):
            if not d.get(k) and not (k == "reason" and d.get("decision") == "defer"):
                errors.append(f"{d.get('decision_id')} 缺 {k}")
        if d.get("decision") not in DECISIONS:
            errors.append(f"{d.get('decision_id')} decision 非法: {d.get('decision')}")
        if d.get("decision") == "modify" and d.get("value") in (None, ""):
            errors.append(f"{d.get('decision_id')} modify 需 value")
        if d.get("question_id") not in q_valid:
            errors.append(f"{d.get('decision_id')} question {d.get('question_id')} 不在 Draft 的 Open Questions")
        if d.get("decision_id") in seen:
            errors.append(f"decision_id 重複 {d.get('decision_id')}")
        seen.add(d.get("decision_id"))
    if errors:
        C.fail("BAD_INPUT", f"decisions.yaml {len(errors)} 個錯誤", "; ".join(errors[:5]), data={"errors": errors})

    by_q = {d["question_id"]: d for d in ds}
    lines = draft_p.read_text(encoding="utf-8").splitlines()
    # pass 1：每節有 PROPOSED 的 key（UNKNOWN 被 accept/modify 時由 PROPOSED bullet 轉 DECIDED，避免重複）
    proposed_in_section: list[set] = []
    _tag, _cur = None, None
    for line in lines:
        if line.startswith("## "):
            proposed_in_section.append(set()); _cur = proposed_in_section[-1]; _tag = None
        elif C.TAG_RE.match(line):
            _tag = C.TAG_RE.match(line).group(1)
        elif _tag == "PROPOSED" and _cur is not None and C.BULLET_RE.match(line):
            k = C.parse_bullet(C.BULLET_RE.match(line).group(1)).get("key")
            if k:
                _cur.add(k)
    sec_i = -1
    out, changes, deferred, cur_tag = [], [], [], None
    applied: dict[str, dict] = {}
    pending_decided: list[str] = []  # 本節要新增到 DECIDED 區塊的 bullet

    def flush_decided():
        nonlocal pending_decided
        if pending_decided:
            if out and out[-1].strip():
                out.append("")
            out.append("### DECIDED")
            out.extend(pending_decided)
            out.append("")
            pending_decided = []

    for line in lines:
        if line.startswith("## "):
            flush_decided()
            cur_tag = None
            sec_i += 1
            out.append(line)
            continue
        m = C.TAG_RE.match(line)
        if m:
            cur_tag = m.group(1)
            out.append(line)
            continue
        mq = re.match(r"^- (Q\d{3,}) ", line)
        if mq and mq.group(1) in by_q and by_q[mq.group(1)]["decision"] in ("accept", "modify"):
            out.append(line + f" — resolved: {by_q[mq.group(1)]['decision_id']}")
            continue
        mb = C.BULLET_RE.match(line)
        if mb and cur_tag in ("UNKNOWN", "PROPOSED"):
            b = C.parse_bullet(mb.group(1))
            q = b.get("question")
            key = b.get("key")
            d = by_q.get(q) if cur_tag == "UNKNOWN" else next((x for x in ds if x["topic"] == key and x["decision"] in ("accept", "modify", "reject")), None)
            if d is None:
                out.append(line)
                continue
            dec_kind = d["decision"]
            if cur_tag == "UNKNOWN":
                if dec_kind == "defer":
                    deferred.append(key)
                    out.append(line + " — decision: " + d["decision_id"] + " (deferred)")
                elif dec_kind == "reject":
                    out.append(line + " — decision: " + d["decision_id"] + " (rejected, 保持 UNKNOWN)")
                else:
                    if key in proposed_in_section[sec_i]:
                        continue  # 由同節 PROPOSED bullet 轉 DECIDED
                    val = d.get("value")
                    if val in (None, ""):
                        prop = next((x for x in meta.get("proposed", []) if x["key"] == key), None)
                        if prop is None:
                            errors.append(f"{d['decision_id']} accept 但 {key} 無 PROPOSED 值，請改 modify 並給 value")
                            out.append(line)
                            continue
                        val = prop["value"]
                    pending_decided.append(f"- `{key}` = {fmt_val(val)} — decision: {d['decision_id']} — rationale: {d.get('reason', '')}")
                    applied[key] = {"value": val, "decision_id": d["decision_id"], "decision": dec_kind}
                    changes.append({"key": key, "from": "UNKNOWN", "to": "DECIDED", "decision_id": d["decision_id"]})
                    continue  # UNKNOWN bullet 移除
            else:  # PROPOSED
                if dec_kind == "reject":
                    changes.append({"key": key, "from": "PROPOSED", "to": "removed", "decision_id": d["decision_id"]})
                    continue
                val = d.get("value") if dec_kind == "modify" else b.get("value")
                pending_decided.append(f"- `{key}` = {fmt_val(val)} — decision: {d['decision_id']} — rationale: {d.get('reason', '')}")
                applied[key] = {"value": val, "decision_id": d["decision_id"], "decision": dec_kind}
                changes.append({"key": key, "from": "PROPOSED", "to": "DECIDED", "decision_id": d["decision_id"]})
                continue
            continue
        out.append(line)
    flush_decided()
    if errors:
        C.fail("BAD_INPUT", f"{len(errors)} 個決議無法套用", "; ".join(errors[:5]), data={"errors": errors})
    text = "\n".join(out)
    text = re.sub(r'^stage: "draft"$', 'stage: "v1"', text, count=1, flags=re.M)
    text = text.replace("# Game Spec Draft —", "# Game Spec v1 —", 1)
    text = re.sub(r"\n### (UNKNOWN|PROPOSED)\n(?:\s*\n)*(?=### |## |\Z)", "\n", text)  # 清掉空的區塊
    text = re.sub(r"\n{3,}", "\n\n", text)
    C.atomic_write(run / "game-spec.v1.md", text + ("\n" if not text.endswith("\n") else ""))
    C.atomic_write(run / "decisions-applied.json", json.dumps({"applied": applied, "deferred": deferred, "changes": changes}, ensure_ascii=False, indent=1))
    C.stage_record(run, "decide", 0, decisions=len(ds), changes=len(changes), deferred=len(deferred))
    C.emit({"file": "game-spec.v1.md", "decisions": len(ds), "changes": changes, "deferred": deferred,
            "next": f"python spec_lint.py --run {run} --spec game-spec.v1.md ; python gs_dev.py --run {run}"}, {"stage": "decide"})


if __name__ == "__main__":
    main()
