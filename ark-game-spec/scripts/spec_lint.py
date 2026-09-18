#!/usr/bin/env python3
"""spec_lint — ADR-002 四分法守門（deterministic）。Draft / v1 都要過。

用法:
  python spec_lint.py --run artifacts/cva/<run_id> [--spec game-spec.draft.md|game-spec.v1.md]

引擎內建規則（不可被 pack 覆寫）：
  NUM-OUTSIDE   非 special 章節中，任何含數字的行必須是 provenance 區塊內的 bullet
  OBS-EVIDENCE  OBSERVED 必有 evidence 且全部存在、至少一筆 visual（transcript 不能支撐 OBSERVED）
  INF-EVIDENCE  INFERRED 必有存在的 evidence
  KB-REF        FROM_KB 的 GKB id 必須在 kb-refs.yaml 或 pack seed 中
  PROPOSED      必有 basis（每筆為存在的 E 或 GKB）與 confidence
  UNKNOWN-Q     UNKNOWN 必對應 Open Questions 中的 Q；Q 反向也要有主
  DECIDED-D     DECIDED 必有 decisions.yaml 中存在的 D
  NAME          反引號內的名稱必須是：pack 宣告的 claim key / entities.json 的 id / GKB / E / Q / D / 章節 id
  SECTIONS      resolved pack 的所有章節都在、順序一致
  TAG-ENUM      ### 區塊只能是六個 tag
pack 規則（lint/rules.yaml，封閉語言）套用在 game-analysis 的 claims 上。
輸出 review-report.json（violations + coverage）；error → exit 3。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gs_common as C  # noqa: E402

DIGIT_RE = re.compile(r"\d")


def lint(run, spec_name: str) -> dict:
    resolved = C.load_resolved(run)
    md = (run / spec_name).read_text(encoding="utf-8")
    doc = C.parse_spec(md)
    ev = {e["evidence_id"]: e for e in C.load_evidence(run)}
    analysis = C.yaml_load(run / "game-analysis.yaml") if (run / "game-analysis.yaml").exists() else {"items": []}
    kb = C.yaml_load(run / "kb-refs.yaml") if (run / "kb-refs.yaml").exists() else {"items": []}
    ents = json.loads((run / "entities.json").read_text(encoding="utf-8")) if (run / "entities.json").exists() else {"all_ids": []}
    decisions = C.yaml_load(run / "decisions.yaml") if (run / "decisions.yaml").exists() else {"decisions": []}
    kb_ids = {r["id"] for it in kb.get("items", []) for r in it.get("refs", [])} | {s["id"] for s in resolved["kb"]["seed"]}
    d_ids = {d["decision_id"] for d in decisions.get("decisions", []) if isinstance(d, dict) and d.get("decision_id")}
    claim_keys = {c["key"] for i in resolved["analysis"]["items"] for c in i.get("claims", [])}
    section_ids = {s["id"] for s in resolved["spec"]["sections"]}
    entity_ids = set(ents.get("all_ids", []))
    allowed_names = claim_keys | entity_ids | section_ids | {"configuration"}

    V: list[dict] = []

    def add(rule, sec, line, msg, sev="error"):
        V.append({"rule": rule, "severity": sev, "section": sec, "line": line, "message": msg})

    # SECTIONS
    want = [(s["number"], s["title"]) for s in resolved["spec"]["sections"]]
    got = [(s["number"], s["title"]) for s in doc["sections"]]
    if got != want:
        add("SECTIONS", None, None, f"章節與 pack 不一致：缺 {sorted(set(want) - set(got))} 多 {sorted(set(got) - set(want))}")

    # 收集 Q
    q_defined, q_used = set(), set()
    for s in doc["sections"]:
        if s.get("special") == "open_questions":
            for _ln, line, _tag in s["lines"]:
                m = re.match(r"^- (Q\d{3,}) ", line)
                if m:
                    q_defined.add(m.group(1))
                    if "— resolved:" in line:
                        q_used.add(m.group(1))

    for s in doc["sections"]:
        sp = s.get("special")
        sec = f"{s['number']} {s['title']}"
        if sp in ("evidence", "open_questions"):
            continue
        # NUM-OUTSIDE：非 bullet、非 fence、非標記行
        if sp != "state_machine":
            for ln, line, _tag in s["lines"]:
                txt = line.strip()
                if not txt or txt.startswith(("<!--", "###", ">")):
                    continue
                if DIGIT_RE.search(txt):
                    add("NUM-OUTSIDE", sec, ln, f"provenance 區塊外出現數字: {txt[:80]}")
        for tag, bullets in s["blocks"].items():
            for b in bullets:
                ln = b["line"]
                # NAME
                for tick in b["ticks"]:
                    if tick in allowed_names or C.E_RE.match(tick) or C.Q_RE.match(tick) or C.D_RE.match(tick) or C.KB_RE.match(tick):
                        continue
                    add("NAME", sec, ln, f"未宣告的名稱 `{tick}`（不是 claim key / entity id / GKB / E / Q / D）")
                if tag == "OBSERVED":
                    if not b["evidence"]:
                        add("OBS-EVIDENCE", sec, ln, "OBSERVED 沒有 evidence")
                    else:
                        missing = [x for x in b["evidence"] if x not in ev]
                        if missing:
                            add("OBS-EVIDENCE", sec, ln, f"evidence 不存在: {missing}")
                        elif all(ev[x]["type"] != "visual" for x in b["evidence"]):
                            add("OBS-EVIDENCE", sec, ln, "OBSERVED 只有 transcript evidence（口白不能支撐 OBSERVED）")
                elif tag == "INFERRED":
                    if not b["evidence"] or any(x not in ev for x in b["evidence"]):
                        add("INF-EVIDENCE", sec, ln, "INFERRED 缺 evidence 或 evidence 不存在")
                elif tag == "FROM_KB":
                    ids = [t for t in b["ticks"] if C.KB_RE.match(t)]
                    if not ids or any(i not in kb_ids for i in ids):
                        add("KB-REF", sec, ln, f"FROM_KB 的 GKB id 缺失或不在 kb-refs/seed: {ids}")
                elif tag == "PROPOSED":
                    if not b["basis"]:
                        add("PROPOSED", sec, ln, "PROPOSED 缺 basis")
                    else:
                        bad = [x for x in b["basis"] if not ((C.E_RE.match(x) and x in ev) or (C.KB_RE.match(x) and x in kb_ids))]
                        if bad:
                            add("PROPOSED", sec, ln, f"basis 不可解析: {bad}")
                    if not b["confidence"]:
                        add("PROPOSED", sec, ln, "PROPOSED 缺 confidence")
                elif tag == "UNKNOWN":
                    q = b["question"]
                    if not q or not C.Q_RE.match(q):
                        add("UNKNOWN-Q", sec, ln, "UNKNOWN 沒有 question: Qnnn")
                    else:
                        q_used.add(q)
                        if q not in q_defined:
                            add("UNKNOWN-Q", sec, ln, f"{q} 不在 Open Questions")
                    if b["value"] not in (None, ""):
                        add("UNKNOWN-Q", sec, ln, "UNKNOWN 不可帶 value")
                elif tag == "DECIDED":
                    d = b["decision"]
                    if not d or d not in d_ids:
                        add("DECIDED-D", sec, ln, f"DECIDED 的 decision {d!r} 不在 decisions.yaml")
    for q in sorted(q_defined - q_used):
        add("UNKNOWN-Q", "Open Questions", None, f"{q} 沒有對應的 UNKNOWN 主張", "warn")

    # pack 規則套在 analysis claims
    claims = {c["key"]: dict(c) for it in analysis.get("items", []) for c in it.get("claims", [])}
    dapp_p = run / "decisions-applied.json"
    if spec_name != "game-spec.draft.md" and dapp_p.exists():
        for k, d in json.loads(dapp_p.read_text(encoding="utf-8")).get("applied", {}).items():
            if k in claims:
                claims[k].update(value=d["value"], provenance="DECIDED")
    for r in resolved["lint"]["rules"]:
        c = claims.get(r.get("path"))
        req, sev = r.get("require"), r.get("severity", "error")
        ok = True
        if req == "present":
            ok = c is not None
        elif req == "nonempty":
            ok = c is not None and c.get("value") not in (None, "", [])
        elif req == "provenance_in":
            ok = c is not None and c.get("provenance") in (r.get("values") or [])
        if not ok:
            add(f"PACK:{r.get('id')}", None, None, r.get("message", ""), sev)

    # coverage：以 spec 本身的 bullets 計（v1 的 DECIDED 才算得到）；同 key 多節出現只算一次
    seen_keys: dict[str, str] = {}
    for s in doc["sections"]:
        if s.get("special") in ("evidence", "open_questions", "configuration", "state_machine"):
            continue
        for tag in ("OBSERVED", "INFERRED", "DECIDED", "PROPOSED", "UNKNOWN"):
            for b in s["blocks"][tag]:
                if b["key"] and not b["is_entity"] and b["key"] in claim_keys and b["key"] not in seen_keys:
                    seen_keys[b["key"]] = tag
                elif b["key"] in seen_keys and tag in ("OBSERVED", "INFERRED", "DECIDED"):
                    seen_keys[b["key"]] = tag
    by = {}
    for tag in seen_keys.values():
        by[tag] = by.get(tag, 0) + 1
    total = len(seen_keys)
    supported = by.get("OBSERVED", 0) + by.get("INFERRED", 0)
    decided = by.get("DECIDED", 0)
    unknown = by.get("UNKNOWN", 0)
    errors = [v for v in V if v["severity"] == "error"]
    summary = {"spec": spec_name, "errors": len(errors), "warnings": len(V) - len(errors),
               "claims": total, "by_provenance": by,
               "coverage_all": round(supported / max(1, total), 3),
               "coverage_known": round(supported / max(1, total - unknown), 3),
               "decided": decided, "resolved_ratio": round((supported + decided) / max(1, total), 3),
               "unknown_ratio": round(unknown / max(1, total), 3),
               "open_questions": len(q_defined), "sections": len(doc["sections"])}
    return {"summary": summary, "violations": V}


def main() -> None:
    ap = argparse.ArgumentParser(description="spec lint")
    ap.add_argument("--run", required=True)
    ap.add_argument("--spec", default="game-spec.draft.md")
    a = ap.parse_args()
    run = C.run_dir(a.run)
    if not (run / a.spec).exists():
        C.fail("BAD_INPUT", f"缺 {a.spec}", "先跑 gs_draft.py")
    with C.Timer() as t:
        rep = lint(run, a.spec)
    C.atomic_write(run / "review-report.json", json.dumps(rep, ensure_ascii=False, indent=1))
    C.stage_record(run, f"lint:{a.spec}", t.elapsed_ms, **{k: v for k, v in rep["summary"].items() if k in ("errors", "warnings", "coverage_all")})
    if rep["summary"]["errors"]:
        C.fail("GATE_BLOCKED", f"{rep['summary']['errors']} 個 lint error", "見 review-report.json", data=rep)
    C.emit(rep, {"stage": "lint", "elapsed_ms": t.elapsed_ms})


if __name__ == "__main__":
    main()
