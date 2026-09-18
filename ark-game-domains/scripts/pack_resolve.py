#!/usr/bin/env python3
"""pack_resolve — _core + <domain> 合併為單一 resolved.json（三個引擎只讀這個）。

用法:
  python pack_resolve.py --domain slot-game [--out run/pack/resolved.json]
  python pack_resolve.py --list                      # 列出已註冊 pack（ga_detect 的 enum 來源）
環境: ARK_GAME_DOMAINS_DIR（預設 本 skill 的 domains/）
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pack_common as P  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="resolve domain pack")
    ap.add_argument("--domain")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--out", help="寫入路徑（同時 stdout 回摘要）")
    ap.add_argument("--full", action="store_true", help="stdout 回完整 resolved（預設只回摘要）")
    a = ap.parse_args()
    root = P.domains_dir()
    if a.list:
        packs = []
        for d in P.list_packs(root):
            man = P.load_yaml(root / d / "domain.yaml")
            packs.append({"domain": d, "display_name": man.get("display_name"), "version": man.get("version"),
                          "cues": man.get("detect", {}).get("cues", []), "subtypes": man.get("detect", {}).get("subtypes", [])})
        P.emit({"packs": packs, "count": len(packs)}, {"domains_dir": str(root)})
    if not a.domain:
        P.fail("BAD_INPUT", "需要 --domain 或 --list", f"可用: {P.list_packs(root)}")
    try:
        r = P.resolve(a.domain, root)
    except P.PackError as e:
        P.fail("BAD_INPUT", str(e), "先跑 pack_lint.py --domain 看完整違規清單")
    if a.out:
        p = pathlib.Path(a.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(r, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    summary = {"domain": r["domain"], "version": r["version"], "pack_sha256": r["pack_sha256"],
               "items": r["analysis"]["item_ids"], "entities": r["analysis"]["entities"],
               "detectors": [d["use"] for d in r["extraction"]["detectors"]],
               "sections": [f'{s["number"]} {s["title"]}' for s in r["spec"]["sections"]],
               "tags": len(r["kb"]["tags"]), "seed_pages": len(r["kb"]["seed"]), "out": a.out}
    P.emit(r if a.full else summary, {"domains_dir": str(root)})


if __name__ == "__main__":
    main()
