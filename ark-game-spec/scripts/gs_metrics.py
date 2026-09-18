#!/usr/bin/env python3
"""gs_metrics — 產出 benchmark.json（M1–M9 + lead time），可選 answer key。

用法:
  python gs_metrics.py --run artifacts/cva/<run_id> [--answer-key answer-key.yaml]
  M1 Lead Time（fetch→dev，小時）      M2 各 stage 耗時           M3 Evidence Coverage（lint summary）
  M4 UNKNOWN Recall（答案卷 NOT_OBSERVED/UNKNOWN 中，Draft 也標 UNKNOWN 的比例）
  M5 KB Reuse（有 refs 的 item 比例）  M6 Draft→v1 修改率（changes / claims）
  M7 Hallucination Rate（答案卷可核對的非 UNKNOWN 主張中，值不符或答案卷為 NOT_OBSERVED 的比例）
  M8 Cross-domain Reuse                M9 Domain Detect 正確（manifest.detect vs answer key）
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gs_common as C  # noqa: E402


def norm(v):
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "yes"):
            return True
        if s in ("false", "no"):
            return False
        try:
            return float(s)
        except ValueError:
            return s
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, list):
        return sorted(str(x).lower() for x in v)
    return v


def main() -> None:
    ap = argparse.ArgumentParser(description="benchmark")
    ap.add_argument("--run", required=True)
    ap.add_argument("--answer-key")
    a = ap.parse_args()
    run = C.run_dir(a.run)
    m = C.load_manifest(run)
    analysis = C.yaml_load(run / "game-analysis.yaml") if (run / "game-analysis.yaml").exists() else {"items": []}
    rep = json.loads((run / "review-report.json").read_text(encoding="utf-8")) if (run / "review-report.json").exists() else {"summary": {}}
    kb = C.yaml_load(run / "kb-refs.yaml") if (run / "kb-refs.yaml").exists() else {"stats": {}}
    dapp = json.loads((run / "decisions-applied.json").read_text(encoding="utf-8")) if (run / "decisions-applied.json").exists() else None
    stages = m.get("stages", {})
    t0 = _dt.datetime.fromisoformat(m["created_at"])
    t_end = max((_dt.datetime.fromisoformat(s["at"]) for s in stages.values() if s.get("at")), default=t0)
    claims = [c for it in analysis.get("items", []) for c in it.get("claims", [])]
    bench = {"contract": C.CONTRACT, "run_id": m["run_id"], "domain": m.get("domain"), "domain_source": m.get("domain_source"),
             "pack_version": m.get("pack_version"), "pack_sha256": m.get("pack_sha256"), "video_sha256": m["video"]["sha256"],
             "model": analysis.get("model"), "skill_versions": m.get("skill_versions", {}),
             "M1_lead_time_h": round((t_end - t0).total_seconds() / 3600, 3),
             "M2_stage_ms": {k: v.get("elapsed_ms") for k, v in stages.items()},
             "M3_coverage_all": rep["summary"].get("coverage_all"), "M3_coverage_known": rep["summary"].get("coverage_known"),
             "M5_kb_reuse": round(kb["stats"].get("items_with_refs", 0) / max(1, kb["stats"].get("items", 1)), 3) if kb.get("stats") else None,
             "M6_modification_rate": round(len(dapp["changes"]) / max(1, len(claims)), 3) if dapp else None,
             "M8_cross_domain_refs": kb.get("stats", {}).get("cross_domain_refs"),
             "llm_calls": {k: v for k, v in m.get("budget_used", {}).items() if k.startswith("llm")},
             "budget_used": m.get("budget_used", {}), "lint_errors": rep["summary"].get("errors"),
             "unknown_ratio": rep["summary"].get("unknown_ratio")}
    if a.answer_key:
        ak = C.yaml_load(run / a.answer_key if not os.path.isabs(a.answer_key) and not os.path.exists(a.answer_key) else a.answer_key)
        expected = {k: v for item in (ak.get("items") or {}).values() for k, v in (item or {}).items()}
        by_key = {c["key"]: c for c in claims}
        unk_total = unk_hit = checkable = halluc = correct = 0
        details = []
        for k, exp in expected.items():
            c = by_key.get(k)
            if c is None:
                continue
            exp_unknown = exp in ("NOT_OBSERVED", "UNKNOWN", "", None, [])
            draft_unknown = c["provenance"] in ("UNKNOWN", "NOT_OBSERVED")
            if exp_unknown:
                unk_total += 1
                if draft_unknown:
                    unk_hit += 1
                else:
                    checkable += 1; halluc += 1
                    details.append({"key": k, "expected": exp, "got": c["value"], "verdict": "hallucination(not observable)"})
            elif not draft_unknown:
                checkable += 1
                if norm(exp) == norm(c["value"]):
                    correct += 1
                else:
                    halluc += 1
                    details.append({"key": k, "expected": exp, "got": c["value"], "verdict": "mismatch"})
            else:
                details.append({"key": k, "expected": exp, "got": None, "verdict": "missed(UNKNOWN)"})
        bench.update({"M4_unknown_recall": round(unk_hit / unk_total, 3) if unk_total else None,
                      "M7_hallucination_rate": round(halluc / checkable, 3) if checkable else None,
                      "accuracy_on_checkable": round(correct / checkable, 3) if checkable else None,
                      "M9_domain_detect_correct": (m.get("detect", {}).get("domain") == ak.get("domain")) if m.get("detect") else None,
                      "answer_key": {"file": a.answer_key, "expected_keys": len(expected), "details": details}})
    C.atomic_write(run / "benchmark.json", json.dumps(bench, ensure_ascii=False, indent=1))
    C.stage_record(run, "metrics", 0)
    C.emit({k: v for k, v in bench.items() if k.startswith("M") or k in ("lint_errors", "unknown_ratio", "llm_calls")}, {"stage": "metrics", "file": "benchmark.json"})


if __name__ == "__main__":
    main()
