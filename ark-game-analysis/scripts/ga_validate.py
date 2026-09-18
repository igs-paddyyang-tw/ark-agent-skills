#!/usr/bin/env python3
"""ga_validate — game-analysis.yaml 契約驗證 + 產出命名字典 entities.json（spec_lint 的命名守門來源）。

用法:
  python ga_validate.py --run artifacts/cva/<run_id>
檢查：所有 pack 宣告的 item 都在；每 item 的 claim keys 恰為宣告集合；provenance/confidence enum；
evidence id 存在；entity id 規則；UNKNOWN 佔比 > 60% → warn「domain 可疑」。error → exit 6。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ga_common as C  # noqa: E402

ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")


def main() -> None:
    ap = argparse.ArgumentParser(description="validate game-analysis.yaml")
    ap.add_argument("--run", required=True)
    a = ap.parse_args()
    run = C.run_dir(a.run)
    resolved = C.load_resolved(run)
    p = run / "game-analysis.yaml"
    if not p.exists():
        C.fail("BAD_INPUT", "缺 game-analysis.yaml", "先跑 ga_analyze.py")
    doc = C.yaml_load(p)
    ev_ids = {e["evidence_id"] for e in C.load_evidence(run)}
    errors, warns = [], []
    want = {i["id"]: i for i in resolved["analysis"]["items"]}
    got = {i["id"]: i for i in doc.get("items", [])}
    for iid in want:
        if iid not in got:
            errors.append(f"缺 item {iid}")
    entities = {}
    total = unknown = 0
    for iid, it in got.items():
        spec = want.get(iid)
        if not spec:
            errors.append(f"未宣告的 item {iid}")
            continue
        keys = [c["key"] for c in it.get("claims", [])]
        want_keys = [c["key"] for c in spec.get("claims", [])]
        if sorted(keys) != sorted(want_keys):
            errors.append(f"{iid} claim keys 與 pack 宣告不符: {sorted(set(keys) ^ set(want_keys))}")
        for c in it.get("claims", []):
            total += 1
            if c.get("provenance") not in C.PROVENANCE:
                errors.append(f"{iid}.{c.get('key')} provenance 非法: {c.get('provenance')}")
            if c.get("confidence") not in C.CONFIDENCE:
                errors.append(f"{iid}.{c.get('key')} confidence 非法")
            bad = [x for x in c.get("evidence", []) if x not in ev_ids]
            if bad:
                errors.append(f"{iid}.{c.get('key')} 引用不存在的 evidence {bad}")
            if c.get("provenance") in ("UNKNOWN", "NOT_OBSERVED"):
                unknown += 1
                if c.get("value") not in (None, "", []):
                    errors.append(f"{iid}.{c.get('key')} UNKNOWN 卻有 value")
            elif c.get("provenance") in ("OBSERVED", "INFERRED") and not c.get("evidence"):
                errors.append(f"{iid}.{c.get('key')} {c['provenance']} 無 evidence")
        for e in it.get("entities", []):
            if not ID_RE.match(str(e.get("id", ""))):
                errors.append(f"{iid} entity id 非法: {e.get('id')}")
            entities.setdefault(e.get("entity_type", "unknown"), []).append(e["id"])
    ratio = unknown / max(1, total)
    if ratio > 0.6:
        warns.append(f"UNKNOWN 佔比 {ratio:.0%} > 60%：domain 可能判錯或素材不足")
    if not any(entities.values()):
        warns.append("沒有任何 entity（命名守門字典為空）")
    C.atomic_write(run / "entities.json", json.dumps({"entities": entities, "all_ids": sorted({i for v in entities.values() for i in v})}, ensure_ascii=False, indent=1))
    data = {"errors": errors, "warnings": warns, "claims": total, "unknown_ratio": round(ratio, 3), "entities": {k: len(v) for k, v in entities.items()}}
    C.stage_record(run, "validate", 0, errors=len(errors), warnings=len(warns))
    if errors:
        C.fail("QUERY_FAILED", f"{len(errors)} 個契約錯誤", "修正 ga_analyze 後處理或 pack 宣告", data=data)
    C.emit(data, {"stage": "validate"})


if __name__ == "__main__":
    main()
