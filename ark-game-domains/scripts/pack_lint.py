#!/usr/bin/env python3
"""pack_lint — 新增 / 修改 domain pack 的放行守門（deterministic）。

用法:
  python pack_lint.py --domain fish-game
  python pack_lint.py --all
規則見 SKILL.md「Pack 契約」。有 severity=error 的違規 → exit 3。
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pack_common as P  # noqa: E402

DETECTORS = {"periodic", "scene_change", "motion_settle", "motion_burst", "still_hold",
             "roi_change", "flash", "audio_peak"}
CLAIM_TYPES = {"string", "int", "number", "bool", "list"}
RULE_REQUIRE = {"present", "nonempty", "provenance_in"}
INJECTION = re.compile(r"(忽略(以上|之前|所有)|ignore (all |the )?(previous|above)|改寫規則|disregard (your|the) (instructions|rules))", re.I)
INVISIBLE = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff]")
POC_ITEMS = 10
REQUIRED_FILES = ["domain.yaml", "extraction.yaml", "analysis/items.yaml", "kb/schema.md",
                  "spec/sections.yaml", "spec/config-structure.schema.json",
                  "spec/state-machine.skeleton.mmd", "lint/rules.yaml",
                  "eval/answer-key.template.yaml", "eval/dataset.md",
                  "references/domain-primer.md", "references/workflow-mapping.md"]


def lint_domain(domain: str, root: pathlib.Path) -> list[dict]:
    v: list[dict] = []
    add = lambda sev, rule, msg: v.append({"severity": sev, "rule": rule, "message": msg})  # noqa: E731
    d = root / domain
    for f in REQUIRED_FILES:
        if not (d / f).exists():
            add("error", "PACK-FILES", f"缺檔: {f}")
    if any(x["rule"] == "PACK-FILES" and "domain.yaml" in x["message"] for x in v):
        return v
    man = P.load_yaml(d / "domain.yaml")
    for k in ("domain", "display_name", "contract", "version", "extends"):
        if k not in man:
            add("error", "PACK-MANIFEST", f"domain.yaml 缺 {k}")
    if man.get("domain") != domain:
        add("error", "PACK-MANIFEST", f"domain.yaml.domain={man.get('domain')!r} 與目錄名 {domain!r} 不同")
    if str(man.get("contract")) != P.CONTRACT:
        add("error", "PACK-CONTRACT", f"contract {man.get('contract')!r} ≠ 引擎 {P.CONTRACT!r}")
    if "__DOMAIN__" in str(man) or "TODO" in str(man.get("detect", {}).get("cues", "")):
        add("error", "PACK-PLACEHOLDER", "manifest 仍有 __DOMAIN__ / TODO 佔位")
    if not man.get("detect", {}).get("cues"):
        add("error", "PACK-DETECT", "detect.cues 為空（ga_detect 無法判 domain）")

    try:
        raw = P.load_raw(domain, root)
        core = P.load_raw("_core", root)
    except Exception as e:  # noqa: BLE001
        add("error", "PACK-LOAD", f"載入失敗: {e}")
        return v

    # extraction
    for det in raw["extraction"].get("detectors", []):
        if det.get("use") not in DETECTORS:
            add("error", "PACK-DETECTOR", f"未知偵測器 {det.get('use')!r}（註冊表: {sorted(DETECTORS)}）")
        if not det.get("label"):
            add("error", "PACK-DETECTOR", f"偵測器 {det.get('use')} 缺 label")
    hard = core["extraction"].get("budget", {}).get("hard_max", {})
    for k, val in raw["extraction"].get("budget", {}).items():
        if k in hard and isinstance(val, (int, float)) and val > hard[k]:
            add("error", "PACK-BUDGET", f"budget.{k}={val} 超過 core hard_max {hard[k]}")

    # items
    items = raw["items"]
    total = len(core["items"]) + len(items)
    if total != POC_ITEMS:
        add("error", "PACK-ITEMS", f"合併 _core 後為 {total} 項，POC 契約要求恰 {POC_ITEMS} 項（domain 需 {POC_ITEMS - len(core['items'])} 項）")
    ids = [i.get("id") for i in items] + [i["id"] for i in core["items"]]
    if len(ids) != len(set(ids)):
        add("error", "PACK-ITEMS", "item id 重複（含與 _core 重複）")
    all_keys: set[str] = set()
    for it in items:
        if not it.get("prompt_exists"):
            add("error", "PACK-PROMPT", f"item {it.get('id')} prompt 檔不存在: {it.get('prompt')}")
        elif INJECTION.search(it["prompt_text"] or "") or INVISIBLE.search(it["prompt_text"] or ""):
            add("error", "PACK-PROMPT-GUARD", f"item {it.get('id')} prompt 含指令覆寫句型或隱形字元")
        elif "TODO" in (it["prompt_text"] or ""):
            add("warn", "PACK-PLACEHOLDER", f"item {it.get('id')} prompt 仍有 TODO")
        for c in it.get("claims", []):
            if c.get("type") not in CLAIM_TYPES:
                add("error", "PACK-CLAIM", f"item {it.get('id')} claim {c.get('key')} type {c.get('type')!r} 不合法")
            all_keys.add(c.get("key", ""))
        ent = it.get("entity")
        if ent and ("type" not in ent or "id" not in ent.get("fields", [])):
            add("error", "PACK-ENTITY", f"item {it.get('id')} entity 需有 type 且 fields 含 id")
    for it in core["items"]:
        for c in it.get("claims", []):
            all_keys.add(c["key"])
    if not any(i.get("entity") for i in items + core["items"]):
        add("error", "PACK-ENTITY", "至少一個 item 需宣告 entity（命名字典來源）")

    # kb
    clash = set(raw["kb"]["tags"]) & set(core["kb"]["tags"])
    if clash:
        add("error", "PACK-KB-TAGS", f"重定義 core tags: {sorted(clash)}")
    if not raw["kb"]["tags"]:
        add("error", "PACK-KB-TAGS", "kb/schema.md 沒有任何 domain tag")
    known = set(raw["kb"]["tags"]) | set(core["kb"]["tags"])
    for it in items:
        bad = [t for t in it.get("kb_tags", []) if t not in known]
        if bad:
            add("error", "PACK-KB-TAGS", f"item {it['id']} kb_tags 不在受控詞彙: {bad}")
    if len(raw["kb"]["seed"]) < 1:
        add("warn", "PACK-KB-SEED", "沒有 seed 頁（M5 會為 0）")
    for s in raw["kb"]["seed"]:
        for k in ("id", "title", "tags", "trust", "status", "type"):
            if k not in s:
                add("error", "PACK-KB-SEED", f"seed {s.get('path')} 缺 frontmatter {k}")
        bad = [t for t in s.get("tags", []) if t not in known]
        if bad:
            add("error", "PACK-KB-SEED", f"seed {s.get('id')} tags 不在受控詞彙: {bad}")
        if INJECTION.search(s.get("body", "")) or INVISIBLE.search(s.get("body", "")):
            add("error", "PACK-KB-GUARD", f"seed {s.get('id')} 含指令覆寫句型或隱形字元")

    # spec
    core_ids = [s["id"] for s in core["sections"]]
    dom_ids = [s.get("id") for s in raw["sections"]]
    for s in raw["sections"]:
        if s.get("insert_after") not in core_ids + dom_ids:
            add("error", "PACK-SECTIONS", f"section {s.get('id')} insert_after={s.get('insert_after')!r} 找不到錨點")
        for si in s.get("source_items", []):
            if si not in ids:
                add("error", "PACK-SECTIONS", f"section {s.get('id')} source_items 含未知 item {si}")
        for pf in s.get("claim_prefixes", []) or []:
            if not any(k.startswith(pf) for k in all_keys):
                add("error", "PACK-SECTIONS", f"section {s.get('id')} claim_prefixes {pf!r} 不對應任何 claim key")
    try:
        P._insert_sections(core["sections"], raw["sections"])
    except P.PackError as e:
        add("error", "PACK-SECTIONS", str(e))
    if raw["state_machine"] and not raw["state_machine"].lstrip().startswith("stateDiagram"):
        add("error", "PACK-SM", "state-machine.skeleton.mmd 必須是 stateDiagram-v2")
    for ph in re.findall(r"\{\{evidence:([\w.]+)\}\}", raw["state_machine"] or ""):
        if ph not in all_keys:
            add("error", "PACK-SM", f"state machine 佔位 {{{{evidence:{ph}}}}} 不是任何 item 的 claim key")
    for name, tpl in raw["dev_templates"].items():
        if "TODO" in tpl:
            add("warn", "PACK-PLACEHOLDER", f"dev template {name} 仍有 TODO")

    # atlas（圖文規格書骨架）：選配；有 atlas/ 才檢
    if raw.get("atlas", {}).get("outline"):
        sec_ids = {s2["id"] for s2 in P._insert_sections(core["sections"], raw["sections"])} if not any(
            x["rule"] == "PACK-SECTIONS" for x in v) else set()
        core_ch = [c.get("id") for c in core["atlas"]["outline"]]
        labels = {det.get("label") for det in raw["extraction"].get("detectors", [])} | {"fallback", "scene"}
        try:
            chapters = P._insert_sections(core["atlas"]["outline"], raw["atlas"]["outline"])
            for ch in chapters:
                for sid in ch.get("sections", []) or []:
                    if sec_ids and sid not in sec_ids:
                        add("error", "PACK-ATLAS", f"atlas 章 {ch['id']} 引用不存在的 spec section {sid!r}")
                fig = ch.get("figure") or {}
                if fig.get("type") not in (None, "hero", "frame", "strip", "state_frames", "none"):
                    add("error", "PACK-ATLAS", f"atlas 章 {ch['id']} figure.type {fig.get('type')!r} 不合法")
                dom_ch_ids = {c.get("id") for c in raw["atlas"]["outline"]}
                for lb in (fig.get("prefer", []) or []) if ch["id"] in dom_ch_ids else []:
                    if lb not in labels:
                        add("warn", "PACK-ATLAS", f"atlas 章 {ch['id']} prefer label {lb!r} 不在本 pack 偵測器 label")
                if "TODO" in str(ch.get("title", "")):
                    add("warn", "PACK-PLACEHOLDER", f"atlas 章 {ch['id']} title 仍有 TODO")
        except P.PackError as e:
            add("error", "PACK-ATLAS", f"atlas outline: {e}")
        for name, rule in (raw["atlas"].get("figures", {}).get("strips") or {}).items():
            for lb in rule.get("labels", []) or ([rule["around"]] if rule.get("around") else []):
                if lb not in labels:
                    add("warn", "PACK-ATLAS", f"atlas strip {name} label {lb!r} 不在本 pack 偵測器 label")
        del core_ch

    # lint rules
    for r in raw["lint_rules"]:
        if r.get("require") not in RULE_REQUIRE:
            add("error", "PACK-LINT", f"rule {r.get('id')} require={r.get('require')!r} 不在封閉集合 {sorted(RULE_REQUIRE)}")
        if r.get("severity") not in ("error", "warn"):
            add("error", "PACK-LINT", f"rule {r.get('id')} severity 必須 error|warn")
        if r.get("path") and r["path"] not in all_keys:
            add("warn", "PACK-LINT", f"rule {r.get('id')} path {r['path']!r} 不對應任何 claim key")

    # eval
    ak = raw["eval"].get("answer_key_template", {})
    ak_items = set((ak.get("items") or {}).keys())
    for i in ak_items:
        if i not in ids:
            add("error", "PACK-EVAL", f"answer-key 含未知 item {i}")
    missing = [i["id"] for i in items if i["id"] not in ak_items]
    if missing:
        add("error", "PACK-EVAL", f"answer-key 缺 domain items: {missing}")
    for name, txt in raw["references"].items():
        if name == "workflow-mapping.md" and "TBD" in txt:
            add("warn", "PACK-REF", "workflow-mapping.md 為 TBD（允許，但 dev-spec 無人接手）")
        if INJECTION.search(txt) or INVISIBLE.search(txt):
            add("error", "PACK-REF-GUARD", f"{name} 含指令覆寫句型或隱形字元")
    return v


def main() -> None:
    ap = argparse.ArgumentParser(description="domain pack lint")
    ap.add_argument("--domain")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    root = P.domains_dir()
    targets = P.list_packs(root) if a.all else ([a.domain] if a.domain else [])
    if not targets:
        P.fail("BAD_INPUT", "需要 --domain 或 --all", f"可用: {P.list_packs(root)}")
    report = {}
    errors = 0
    for d in targets:
        vs = lint_domain(d, root)
        errors += sum(1 for x in vs if x["severity"] == "error")
        report[d] = {"errors": [x for x in vs if x["severity"] == "error"],
                     "warnings": [x for x in vs if x["severity"] == "warn"]}
    data = {"packs": report, "error_count": errors,
            "warning_count": sum(len(r["warnings"]) for r in report.values())}
    if errors:
        print(__import__("json").dumps({"success": False, "contract": P.CONTRACT,
                                        "error": {"code": "GATE_BLOCKED", "message": f"{errors} 個 error 違規",
                                                  "hint": "修 pack 後重跑；warn 不阻斷"}, "data": data},
                                       ensure_ascii=False))
        sys.exit(P.EXIT["GATE_BLOCKED"])
    P.emit(data, {"domains_dir": str(root)})


if __name__ == "__main__":
    main()
