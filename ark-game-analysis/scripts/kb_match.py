#!/usr/bin/env python3
"""kb_match — game-analysis.yaml 的 items 依 pack kb_tags 匹配 KB → kb-refs.yaml。

用法:
  python kb_match.py --run artifacts/cva/<run_id> [--wiki-engine /path/to/ark-wiki-engine --knowledge-root knowledge]
順序：domain tag 精確 → core tag 精確 → （選配）ark-wiki-engine wiki_query BM25/語意。
cross_domain=true：命中的頁面 domain 不是本 run 的 domain（通用化的直接產值，M8）。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ga_common as C  # noqa: E402


def wiki_query(engine: pathlib.Path, root: str, domains: str, query: str, k: int) -> list[dict]:
    script = engine / "scripts" / "wiki_query.py"
    if not script.exists():
        return []
    r = subprocess.run([sys.executable, str(script), "--knowledge_root", root, "--domains", domains, "--query", query, "--top_k", str(k)],
                       capture_output=True, text=True, encoding="utf-8")
    try:
        j = json.loads(r.stdout.strip().splitlines()[-1])
        hits = j.get("data", {}).get("results") or j.get("data", {}).get("hits") or []
        return [{"id": h.get("id") or h.get("page_id") or h.get("path"), "title": h.get("title"), "score": h.get("score", 0),
                 "match": "wiki", "trust": h.get("trust", "llm-distilled"), "domain": h.get("domain")} for h in hits]
    except Exception:  # noqa: BLE001
        return []


def main() -> None:
    ap = argparse.ArgumentParser(description="match knowledge base")
    ap.add_argument("--run", required=True)
    ap.add_argument("--wiki-engine", default=os.getenv("ARK_WIKI_ENGINE_SKILL"))
    ap.add_argument("--knowledge-root", default=os.getenv("ARK_KNOWLEDGE_ROOT", "knowledge"))
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--no-cross-domain", action="store_true", help="不掃其他 pack 的 seed")
    a = ap.parse_args()
    run = C.run_dir(a.run)
    resolved = C.load_resolved(run)
    doc = C.yaml_load(run / "game-analysis.yaml")
    seed = list(resolved["kb"]["seed"])
    if not a.no_cross_domain:  # 其他 pack 的 seed 以 core tag 參與匹配（跨 domain 重用，M8）
        P = C.pack_common()
        for other in P.list_packs():
            if other != resolved["domain"]:
                try:
                    seed += [{**pg, "_cross": True} for pg in P.load_raw(other)["kb"]["seed"]]
                except Exception:  # noqa: BLE001
                    pass
    aliases = resolved["kb"]["aliases"]
    norm = lambda t: aliases.get(t, t)  # noqa: E731
    items_spec = {i["id"]: i for i in resolved["analysis"]["items"]}
    refs_out, total_refs, cross = [], 0, 0
    with C.Timer() as t:
        for it in doc.get("items", []):
            spec = items_spec.get(it["id"], {})
            tags = [norm(x) for x in spec.get("kb_tags", [])]
            # 有觀察到內容的 item 才值得比對（全 UNKNOWN 的不查）
            informative = any(c["provenance"] not in ("UNKNOWN", "NOT_OBSERVED") for c in it.get("claims", [])) or it.get("entities")
            refs = []
            if tags and informative:
                dom_tags = [x for x in tags if x in resolved["kb"]["domain_tags"]]
                core_tags = [x for x in tags if x in resolved["kb"]["core_tags"]]
                for page in seed:
                    ptags = [norm(x) for x in page.get("tags", [])]
                    d_hit = sorted(set(dom_tags) & set(ptags)) if not page.get("_cross") else []
                    c_hit = sorted(set(core_tags) & set(ptags))
                    if d_hit or c_hit:
                        score = round((2 * len(d_hit) + len(c_hit)) / (2 * len(dom_tags) + len(core_tags) or 1), 3)
                        if page.get("_cross"):
                            score = round(score * 0.5, 3)
                        refs.append({"id": page["id"], "title": page.get("title"), "match": "tag", "score": score,
                                     "tags_hit": d_hit + c_hit, "trust": page.get("trust", "llm-distilled"),
                                     "domain": page.get("domain"), "cross_domain": page.get("domain") not in (resolved["domain"], "game-core"),
                                     "proposes": page.get("proposes", [])})
                refs.sort(key=lambda r: (-r["score"], r["id"]))
                refs = refs[: a.top_k]
                if a.wiki_engine and len(refs) < a.top_k:
                    q = " ".join(tags + [it["name"]])
                    for h in wiki_query(pathlib.Path(a.wiki_engine), a.knowledge_root, ",".join(resolved["kb"]["domains"]), q, a.top_k - len(refs)):
                        if h["id"] and all(h["id"] != r["id"] for r in refs):
                            h["cross_domain"] = h.get("domain") not in (resolved["domain"], "game-core", None)
                            refs.append(h)
            total_refs += len(refs)
            cross += sum(1 for r in refs if r.get("cross_domain"))
            refs_out.append({"item_id": it["id"], "tags_used": tags, "informative": informative, "refs": refs})
    out = {"contract": C.CONTRACT, "run_id": doc["run_id"], "domain": resolved["domain"], "kb_domains": resolved["kb"]["domains"],
           "items": refs_out, "stats": {"items": len(refs_out), "items_with_refs": sum(1 for r in refs_out if r["refs"]),
                                        "refs": total_refs, "cross_domain_refs": cross,
                                        "deterministic_refs": sum(1 for r in refs_out for x in r["refs"] if x.get("trust") == "deterministic")}}
    C.atomic_write(run / "kb-refs.yaml", C.yaml_dump(out))
    C.stage_record(run, "kb_match", t.elapsed_ms, **out["stats"])
    C.emit({**out["stats"], "file": "kb-refs.yaml"}, {"stage": "kb_match", "elapsed_ms": t.elapsed_ms})


if __name__ == "__main__":
    main()
