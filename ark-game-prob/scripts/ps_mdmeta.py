#!/usr/bin/env python3
"""ps_mdmeta — md 模式（1.4）：手寫 / 既有的 prob-spec.md → prob-spec.meta.json（沒有 xlsx、沒有快測也能走 ps_html → ps_lint）。

meta 內容：contract / kind / mode: md / slug / game / sections（由 `## N. ` 標題讀）/ pending_params（數「待決議」）/
verdict（frontmatter）/ sources（frontmatter `sources:` 列的檔案，存在就記 sha16，供 PS-STALE 與 PS-NUM 允許集）/ md_sha256_16。
md 模式沒有派生值表，ps_lint 的 PS-NUM 降為 warning（數字請在來源欄 / 文中標出處）。

用法: python ps_mdmeta.py --dir <含 prob-spec.md 的目錄> [--game <名>] [--slug <slug>]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ps_common as C  # noqa: E402
import ps_mdview as M  # noqa: E402

PENDING = "待決議"


def build_meta(md_p: pathlib.Path, game: str | None = None, slug: str | None = None) -> dict:
    text = md_p.read_text(encoding="utf-8")
    doc = M.parse_md(text)
    fm = doc["fm"]
    heads = [s["raw_title"] for s in doc["sections"] if s.get("no") and s["no"].isdigit()]
    body = M.split_fm(text)[1]
    stripped = re.sub(r"<!--\s*human:[a-z0-9_-]+\s*-->.*?<!--\s*/human\s*-->", "", body, flags=re.S)
    pending = stripped.count(PENDING)
    sources: dict = {}
    fm_src = fm.get("sources") if isinstance(fm.get("sources"), dict) else {}
    for k, rel in fm_src.items():
        for base in [md_p.parent, pathlib.Path.cwd(), *md_p.resolve().parents]:
            p = base / str(rel)
            if p.exists() and p.is_file():
                sources[k] = {"path": str(rel), "sha256_16": C.sha16(p)}
                break
    game = game or str(fm.get("game") or doc["title"].replace("機率規格書", "").strip("：: （）()") or md_p.parent.name)
    slug = slug or str(fm.get("slug") or md_p.parent.name)
    return {"contract": "1", "kind": "prob-spec", "mode": str(fm.get("mode") or "md"), "slug": slug, "game": game,
            "sections": heads, "pending_params": pending, "verdict": str(fm.get("verdict") or "未快測"), "sources": sources, "derived": [],
            "md_sha256_16": C.sha16(md_p), "generated": dt.datetime.now().isoformat(timespec="seconds")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--game")
    ap.add_argument("--slug")
    a = ap.parse_args()
    d = pathlib.Path(a.dir)
    md_p = d / "prob-spec.md"
    if not md_p.exists():
        C.fail("BAD_INPUT", f"缺 {md_p}", "照 assets/prob-spec.template.md 寫一份")
    meta = build_meta(md_p, a.game, a.slug)
    C.atomic_write(d / "prob-spec.meta.json", json.dumps(meta, ensure_ascii=False, indent=1))
    C.emit({"meta": str(d / "prob-spec.meta.json"), "mode": meta["mode"], "sections": len(meta["sections"]), "pending_params": meta["pending_params"], "sources": list(meta["sources"]),
            "delivery": f"meta 已落盤（md 模式）｜{len(meta['sections'])} 段｜待決議 {meta['pending_params']}｜來源 {len(meta['sources'])}"}, {"stage": "ps_mdmeta"})


if __name__ == "__main__":
    main()
