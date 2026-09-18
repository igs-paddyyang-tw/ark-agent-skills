#!/usr/bin/env python3
"""ga_analyze — 依 resolved pack 的 items（_core 4 + domain 6）逐項呼叫 LLM → game-analysis.yaml。

用法:
  python ga_analyze.py --run artifacts/cva/<run_id> [--items S01,S02] [--max-llm-calls N]

每項輸出 claims[] + entities[]。deterministic 後處理（不靠提詞）：
  - 未宣告的 claim key → 丟棄並計入 schema_violations
  - 引用不存在的 evidence id → 該 claim 降為 UNKNOWN
  - OBSERVED 但只引用 transcript evidence → 降為 INFERRED（口白不能支撐 OBSERVED）
  - provenance / confidence 不在 enum → UNKNOWN / unknown
  - 宣告了但模型沒回的 claim key → 補 UNKNOWN
  - entity 缺 id 或 id 不符命名規則 → 丟棄
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ga_common as C  # noqa: E402
from llm_adapter import Adapter, LLMError  # noqa: E402

SYSTEM = ("你是遊戲機制分析員。依據 evidence 清單（每筆有 id、時間碼、觀察）回答指定的分析項目。"
          "規則：(1) 只能引用清單中的 evidence id；(2) 影片直接看到 → OBSERVED；需推論 → INFERRED 並寫 reasoning；"
          "看不到 → UNKNOWN 且 value 為 null；(3) transcript 類 evidence 是實況口白，不可作為 OBSERVED 的依據；"
          "(4) 不要為符號/魚種/選項取名，用 prompt 指定的 id 規則；(5) 不要編造數字。"
          "只輸出 JSON：{\"claims\":[{\"key\":..,\"value\":..,\"provenance\":\"OBSERVED|INFERRED|UNKNOWN\",\"evidence\":[\"E001\"],"
          "\"confidence\":\"high|medium|low|unknown\",\"reasoning\":\"...\"}],\"entities\":[{\"id\":..,\"type\":..,...,"
          "\"provenance\":..,\"evidence\":[..]}]}")
ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")


def digest(evs: list[dict], limit_chars: int = 12000) -> str:
    lines = []
    for e in evs:
        kind = "VISUAL" if e["type"] == "visual" else "TRANSCRIPT(untrusted)"
        obs = "; ".join(e.get("observation") or [])[:300]
        nums = ", ".join(f"{n.get('label')}={n.get('value')}" for n in e.get("numbers") or [])
        lines.append(f"{e['evidence_id']} [{kind}] {e['t_start']} {e.get('extractor', '')}: {obs}" + (f" | numbers: {nums}" if nums else ""))
    out = "\n".join(lines)
    return out[:limit_chars] + ("\n…(truncated)" if len(out) > limit_chars else "")


def coerce(value, typ):
    if value is None:
        return None
    try:
        if typ == "int":
            return int(value)
        if typ == "number":
            return float(value)
        if typ == "bool":
            if isinstance(value, str):
                return value.strip().lower() in ("true", "yes", "1", "是")
            return bool(value)
        if typ == "list":
            return list(value) if isinstance(value, (list, tuple)) else [value]
        return str(value)
    except (TypeError, ValueError):
        return None


def postprocess(item: dict, res: dict, ev_index: dict) -> tuple[dict, int]:
    viol = 0
    allowed = {c["key"]: c.get("type", "string") for c in item.get("claims", [])}
    claims_out, seen = [], set()
    for c in res.get("claims", []) if isinstance(res.get("claims"), list) else []:
        if not isinstance(c, dict) or c.get("key") not in allowed or c["key"] in seen:
            viol += 1
            continue
        seen.add(c["key"])
        prov = str(c.get("provenance", "UNKNOWN")).upper()
        if prov not in ("OBSERVED", "INFERRED", "UNKNOWN", "NOT_OBSERVED"):
            viol += 1
            prov = "UNKNOWN"
        ev_ids = [x for x in (c.get("evidence") or []) if isinstance(x, str)]
        bad = [x for x in ev_ids if x not in ev_index]
        ev_ids = [x for x in ev_ids if x in ev_index]
        if bad:
            viol += 1
            prov = "UNKNOWN"
        if prov in ("OBSERVED", "INFERRED") and not ev_ids:
            viol += 1
            prov = "UNKNOWN"
        if prov == "OBSERVED" and all(ev_index[x]["type"] != "visual" for x in ev_ids):
            viol += 1
            prov = "INFERRED"
        value = coerce(c.get("value"), allowed[c["key"]]) if prov not in ("UNKNOWN", "NOT_OBSERVED") else None
        if value is None and prov not in ("UNKNOWN", "NOT_OBSERVED"):
            prov = "UNKNOWN"
        conf = c.get("confidence") if c.get("confidence") in C.CONFIDENCE else "unknown"
        if prov in ("UNKNOWN", "NOT_OBSERVED"):
            conf = "unknown"
        claims_out.append({"key": c["key"], "value": value, "provenance": prov, "evidence": ev_ids,
                           "confidence": conf, "reasoning": str(c.get("reasoning", ""))[:400]})
    for key in allowed:
        if key not in seen:
            claims_out.append({"key": key, "value": None, "provenance": "UNKNOWN", "evidence": [], "confidence": "unknown", "reasoning": ""})
    entities_out = []
    ent_spec = item.get("entity")
    if ent_spec:
        ids = set()
        for e in res.get("entities", []) if isinstance(res.get("entities"), list) else []:
            if not isinstance(e, dict) or not isinstance(e.get("id"), str) or not ID_RE.match(e["id"]) or e["id"] in ids:
                viol += 1
                continue
            ids.add(e["id"])
            ev_ids = [x for x in (e.get("evidence") or []) if x in ev_index]
            prov = str(e.get("provenance", "OBSERVED")).upper()
            if prov not in ("OBSERVED", "INFERRED") or not ev_ids:
                prov = "UNKNOWN"
            ent = {"id": e["id"], "entity_type": ent_spec["type"], "provenance": prov, "evidence": ev_ids}
            for f in ent_spec.get("fields", []):
                if f != "id":
                    ent[f] = e.get(f)
            entities_out.append(ent)
    return {"id": item["id"], "name": item["name"], "claims": claims_out, "entities": entities_out}, viol


def fake_response(item: dict, evs: list[dict]) -> dict:
    """離線假回覆：前兩個 claim 引用第一筆 visual evidence，其餘 UNKNOWN；每個 entity type 給兩個 entity。"""
    vis = [e for e in evs if e["type"] == "visual"]
    eid = vis[0]["evidence_id"] if vis else None
    claims = []
    for i, c in enumerate(item.get("claims", [])):
        if i < 2 and eid:
            val = {"int": 5, "number": 2.5, "bool": True, "list": ["a", "b"], "string": "fake-value"}[c.get("type", "string")]
            claims.append({"key": c["key"], "value": val, "provenance": "OBSERVED", "evidence": [eid], "confidence": "high", "reasoning": "fake"})
        else:
            claims.append({"key": c["key"], "value": None, "provenance": "UNKNOWN", "evidence": [], "confidence": "unknown"})
    ents = []
    if item.get("entity"):
        t = item["entity"]["type"]
        for n in ("a", "b"):
            ents.append({"id": f"{t}_{n}", "type": "high", "provenance": "OBSERVED", "evidence": [eid] if eid else [],
                         **{f: f"fake-{f}" for f in item["entity"].get("fields", []) if f not in ("id", "type")}})
    return {"claims": claims, "entities": ents}


def main() -> None:
    ap = argparse.ArgumentParser(description="analyze items")
    ap.add_argument("--run", required=True)
    ap.add_argument("--items", help="逗號分隔 item id，預設全部")
    ap.add_argument("--max-llm-calls", type=int)
    a = ap.parse_args()
    run = C.run_dir(a.run)
    m = C.load_manifest(run)
    resolved = C.load_resolved(run)
    evs = C.evidence_view(run)
    if not (run / "observations.jsonl").exists():
        C.fail("BAD_INPUT", "缺 observations.jsonl", "先跑 ga_observe.py")
    ev_index = {e["evidence_id"]: e for e in evs}
    items = resolved["analysis"]["items"]
    if a.items:
        want = set(a.items.split(","))
        items = [i for i in items if i["id"] in want]
    if a.max_llm_calls:
        os.environ["ARK_LLM_MAX_CALLS"] = str(a.max_llm_calls)
    ad = Adapter(run, resolved["pack_sha256"], resolved["extraction"]["budget"])
    dg = digest(evs)
    primer = resolved.get("references", {}).get("domain-primer.md", "")
    out_items, total_viol = [], 0
    with C.Timer() as t:
        for it in items:
            keys = "\n".join(f"- {c['key']} ({c.get('type', 'string')})" for c in it.get("claims", []))
            ent = it.get("entity")
            ent_txt = f"\nentities：type={ent['type']}，fields={ent['fields']}（id 小寫、底線）" if ent else "\nentities：此項不需要（回空陣列）"
            prompt = (f"Domain: {resolved['display_name']}（{resolved['domain']}）\n{primer[:1200]}\n\n"
                      f"## 分析項目 {it['id']} {it['name']}\n{it.get('prompt_text', '')}\n\n允許的 claim keys：\n{keys}{ent_txt}\n\n"
                      f"## Evidence\n{dg}")
            try:
                res = ad.complete_json(SYSTEM, prompt, None, fake_key=f"analyze:{it['id']}", fake_fn=lambda it=it: fake_response(it, evs))
            except LLMError as e:
                C.fail(e.code, str(e), e.hint)
            item_out, viol = postprocess(it, res, ev_index)
            total_viol += viol
            out_items.append(item_out)
    doc = {"contract": C.CONTRACT, "run_id": m["run_id"], "domain": resolved["domain"], "pack_version": resolved["version"],
           "pack_sha256": resolved["pack_sha256"], "model": ad.meta()["model"], "items": out_items,
           "stats": {"claims": sum(len(i["claims"]) for i in out_items),
                     "unknown": sum(1 for i in out_items for c in i["claims"] if c["provenance"] in ("UNKNOWN", "NOT_OBSERVED")),
                     "entities": sum(len(i["entities"]) for i in out_items), "schema_violations": total_viol}}
    C.atomic_write(run / "game-analysis.yaml", C.yaml_dump(doc))
    mm = C.load_manifest(run)
    mm.setdefault("budget_used", {})["llm_calls_analyze"] = ad.calls
    C.save_manifest(run, mm)
    C.stage_record(run, "analyze", t.elapsed_ms, **doc["stats"], **ad.meta())
    C.emit({"items": [i["id"] for i in out_items], **doc["stats"], "file": "game-analysis.yaml",
            "unknown_ratio": round(doc["stats"]["unknown"] / max(1, doc["stats"]["claims"]), 3)},
           {"stage": "analyze", "elapsed_ms": t.elapsed_ms, **ad.meta()})


if __name__ == "__main__":
    main()
