#!/usr/bin/env python3
"""gs_dev — game-spec.v1.md + decisions → dev-spec/ 六檔（研發直接可用）。

用法:
  python gs_dev.py --run artifacts/cva/<run_id> [--allow-deferred]
輸出 dev-spec/{game-spec.md, feature-spec.md, state-machine.md, ui-spec.md, config-spec.yaml, qa-checklist.md}
  - 五份 .md 由 pack 的 spec/dev/*.md.j2（Jinja2 沙箱）渲染
  - config-spec.yaml 由引擎產生：structure（entities）+ parameters[]（**value 一律 null**，競品數字只在 competitor_reference）
Gate：有 deferred 決議 → exit 3（--allow-deferred 可放行但 manifest 標記）；pack lint 規則 severity=error 且 require=nonempty 未滿足 → exit 3；
      config-spec 的 parameters[].value 非 null → exit 3（引擎自檢）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gs_common as C  # noqa: E402

FILES = ["game-spec.md", "feature-spec.md", "state-machine.md", "ui-spec.md", "qa-checklist.md"]


def render_j2(tpl: str, ctx: dict) -> str:
    try:
        from jinja2.sandbox import SandboxedEnvironment
    except ImportError:
        C.fail("DRIVER_MISSING", "缺 jinja2", "pip install jinja2 --break-system-packages")
    env = SandboxedEnvironment(autoescape=False, trim_blocks=False, lstrip_blocks=False, keep_trailing_newline=True)
    return env.from_string(tpl).render(**ctx)


def main() -> None:
    ap = argparse.ArgumentParser(description="dev-ready spec")
    ap.add_argument("--run", required=True)
    ap.add_argument("--allow-deferred", action="store_true")
    a = ap.parse_args()
    run = C.run_dir(a.run)
    resolved = C.load_resolved(run)
    m = C.load_manifest(run)
    v1 = run / "game-spec.v1.md"
    if not v1.exists():
        C.fail("BAD_INPUT", "缺 game-spec.v1.md", "先跑 gs_decide.py")
    analysis = C.yaml_load(run / "game-analysis.yaml")
    dapplied = json.loads((run / "decisions-applied.json").read_text(encoding="utf-8")) if (run / "decisions-applied.json").exists() else {"applied": {}, "deferred": []}
    if dapplied.get("deferred") and not a.allow_deferred:
        C.fail("GATE_BLOCKED", f"{len(dapplied['deferred'])} 個 defer 決議未解: {dapplied['deferred']}",
               "回 ark-grill-me 決議，或 --allow-deferred（manifest 會標記 dev-spec 不完整）")
    # 合併決議到 claims
    items = []
    for it in analysis["items"]:
        claims = []
        for c in it["claims"]:
            c = dict(c)
            if c["key"] in dapplied["applied"]:
                d = dapplied["applied"][c["key"]]
                c.update(value=d["value"], provenance="DECIDED", evidence=c.get("evidence") or [], decision_id=d["decision_id"])
            claims.append(c)
        items.append({**it, "claims": claims})
    # pack nonempty/error 規則 gate
    claims_by_key = {c["key"]: c for it in items for c in it["claims"]}
    blocked = []
    for r in resolved["lint"]["rules"]:
        if r.get("severity") == "error" and r.get("require") == "nonempty":
            c = claims_by_key.get(r["path"])
            if not c or c.get("value") in (None, "", []):
                blocked.append(f"{r['id']}: {r.get('message')}")
    if blocked:
        C.fail("GATE_BLOCKED", "dev-spec 必填欄位未決", "; ".join(blocked), data={"blocked": blocked})

    ctx = {"domain": resolved["domain"], "display_name": resolved["display_name"], "run_id": m["run_id"], "items": items,
           "spec_v1": v1.read_text(encoding="utf-8"),
           "flow_states": (claims_by_key.get("flow.states") or {}).get("value") or [],
           "ui_elements": [e for it in items for e in it["entities"] if e.get("entity_type") == "ui_element"],
           "ui_claims": [c for c in claims_by_key.values() if c["key"].startswith("ui.") and c["provenance"] not in ("UNKNOWN", "NOT_OBSERVED")],
           "checkable": [c for c in claims_by_key.values() if c["provenance"] in ("OBSERVED", "INFERRED", "DECIDED")],
           "open_questions": [{"id": q["id"], "key": q["key"], "text": "待決" + ("（deferred）" if q["key"] in dapplied.get("deferred", []) else "")}
                              for q in json.loads((run / "spec-draft.meta.json").read_text(encoding="utf-8"))["questions"]
                              if q["key"] not in dapplied["applied"]]}
    import re
    claim_ev = {k: c["evidence"] for k, c in claims_by_key.items()}
    ctx["state_machine"] = re.sub(r"\{\{evidence:([\w.]+)\}\}", lambda mm: "[" + ", ".join(claim_ev.get(mm.group(1)) or ["UNKNOWN"]) + "]",
                                  resolved["spec"].get("state_machine") or "stateDiagram-v2\n    [*] --> idle")
    out_dir = run / "dev-spec"
    out_dir.mkdir(exist_ok=True)
    written = []
    with C.Timer() as t:
        for name in FILES:
            tpl = resolved["spec"]["dev_templates"].get(name)
            if tpl is None:
                C.fail("BAD_INPUT", f"pack 缺 dev template {name}.j2", "pack_lint 應已擋下；檢查 _core/spec/dev/")
            C.atomic_write(out_dir / name, render_j2(tpl, ctx))
            written.append(name)
        # config-spec.yaml
        structure: dict = {}
        for it in items:
            for e in it["entities"]:
                structure.setdefault(e["entity_type"], []).append({"id": e["id"], **{k: v for k, v in e.items() if k not in ("id", "entity_type", "evidence", "provenance") and v not in (None, "")},
                                                                    "observed": e["provenance"] == "OBSERVED"})
        params = []
        for k, c in sorted(claims_by_key.items()):
            v = c.get("value")
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                continue
            params.append({"name": k, "type": "integer" if isinstance(v, int) else "number", "value": None, "source": "TO_BE_DECIDED_BY_MATH",
                           "competitor_reference": {"value": v, "provenance": c["provenance"], "evidence": c.get("evidence", []),
                                                    **({"decision_id": c["decision_id"]} if c.get("decision_id") else {})}})
        cfg = {"contract": C.CONTRACT, "domain": resolved["domain"], "run_id": m["run_id"], "structure": structure, "parameters": params,
               "note": "parameters[].value 一律 null：數字由 Math 決定；competitor_reference 只是競品觀察，不可直接抄。"}
        if any(p["value"] is not None for p in params):
            C.fail("GATE_BLOCKED", "config-spec parameters 出現非 null value（引擎自檢失敗）", "")
        schema = resolved["spec"].get("config_structure_schema")
        if schema:
            try:
                import jsonschema
                jsonschema.validate(structure, schema)
            except ImportError:
                pass
            except Exception as e:  # noqa: BLE001
                C.fail("GATE_BLOCKED", f"config-spec structure 不符 pack schema: {str(e)[:200]}", "")
        C.atomic_write(out_dir / "config-spec.yaml", C.yaml_dump(cfg))
        written.append("config-spec.yaml")
    mm = C.load_manifest(run)
    mm["dev_spec"] = {"files": written, "deferred_allowed": bool(dapplied.get("deferred")) and a.allow_deferred, "parameters": len(params)}
    C.save_manifest(run, mm)
    C.stage_record(run, "dev", t.elapsed_ms, files=len(written), parameters=len(params))
    C.emit({"dir": "dev-spec", "files": written, "parameters": len(params), "structure": {k: len(v) for k, v in structure.items()},
            "deferred_allowed": mm["dev_spec"]["deferred_allowed"], "next": f"python gs_metrics.py --run {run}"}, {"stage": "dev", "elapsed_ms": t.elapsed_ms})


if __name__ == "__main__":
    main()
