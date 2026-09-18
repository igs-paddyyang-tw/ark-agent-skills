#!/usr/bin/env python3
"""atlas_register — 登錄到圖書館目錄 library/atlas/catalog.json（機器讀）+ catalog.md（人讀）+ log.md（append-only）。

用法:
  python atlas_register.py --book atlas/<slug> [--library library/atlas]
規則：同 slug 為更新；登錄前當場跑 atlas_lint 與 atlas_build --check，結果填入 lint / pair；
status=published 但 lint≠PASS 或 pair≠OK → 拒絕（exit 3）；distribution 必為 internal。
catalog 契約與 ark-book 的 library/catalog.json 平行（kind: atlas），圖書館網站可同時讀兩份。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import atlas_common as C  # noqa: E402
import atlas_build  # noqa: E402
import atlas_lint  # noqa: E402

CATALOG_VERSION = 1


def main() -> None:
    ap = argparse.ArgumentParser(description="register atlas")
    ap.add_argument("--book", required=True)
    ap.add_argument("--library", default="library/atlas")
    a = ap.parse_args()
    book = C.atlas_dir(a.book)
    cy = C.yaml_load(book / "atlas.yaml")
    lint = atlas_lint.lint(book)
    pair = atlas_build.check(book)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    lint_status = "PASS" if lint["summary"]["errors"] == 0 else "FAIL"
    if cy.get("status") == "published" and (lint_status != "PASS" or pair["status"] != "OK"):
        C.fail("GATE_BLOCKED", f"published 需 lint PASS 與 pair OK（現況 {lint_status} / {pair['status']}）", "修後重跑 atlas_build.py", data={"lint": lint["summary"], "pair": pair})
    lib = pathlib.Path(a.library)
    lib.mkdir(parents=True, exist_ok=True)
    cat_p = lib / "catalog.json"
    cat = json.loads(cat_p.read_text(encoding="utf-8")) if cat_p.exists() else {"catalog_version": CATALOG_VERSION, "kind": "atlas", "shelves": [], "books": []}
    g = cy.get("game", {})
    entry = {"kind": "atlas", "slug": cy["slug"], "title": cy["title"], "subtitle": cy.get("subtitle"), "author": cy.get("author"),
             "version": cy.get("version", 1), "status": cy.get("status"), "language": cy.get("language", "zh-Hant"),
             "distribution": cy.get("distribution"), "shelf": cy.get("shelf"), "tags": cy.get("tags", []),
             "game": {k: g.get(k) for k in ("domain", "display_name", "run_id", "video_sha256", "spec_source", "pack_version", "decisions", "open_questions", "claims")},
             "cover": cy.get("cover"), "style": (cy.get("style") or {}).get("name"),
             "chapters": [{"n": c["n"], "slug": c["slug"], "title": c["title"], "type": c["type"], "figures": c.get("figures", [])} for c in cy["chapters"]],
             "figures": lint["summary"].get("figures", 0),
             "paths": {"book_dir": str(book), "site": str(book / "site" / "index.html"), "atlas_yaml": str(book / "atlas.yaml"),
                       "figures_json": str(book / "figures.json"), "sources": str(book / "sources")},
             "lint": {"status": lint_status, "errors": lint["summary"]["errors"], "checked": now},
             "pair": {"status": pair["status"], "checked": now},
             "created": cy.get("created"), "updated": str(_dt.date.today())}
    books = [b for b in cat["books"] if b["slug"] != cy["slug"]]
    action = "update" if len(books) != len(cat["books"]) else "add"
    books.append(entry)
    cat["books"] = sorted(books, key=lambda b: (b.get("shelf") or "", b["slug"]))
    cat["updated"] = now
    warn = None
    if entry["shelf"] not in cat["shelves"]:
        warn = f"shelf {entry['shelf']!r} 不在受控 shelves，圖書館會放「未分類」；要新增請人工改 catalog.json.shelves"
    C.atomic_write(cat_p, json.dumps(cat, ensure_ascii=False, indent=1))
    md = ["# Atlas 圖書館目錄（圖文遊戲規格書）", "", f"更新：{now}", "", "| shelf | slug | 書名 | domain | 版本 | 狀態 | 章 | 圖 | lint | pair |", "|---|---|---|---|---|---|---|---|---|---|"]
    md += [f"| {b.get('shelf')} | {b['slug']} | {b['title']} | {b['game'].get('domain')} | v{b['version']} | {b['status']} | {len(b['chapters'])} | {b.get('figures', 0)} | {b['lint']['status']} | {b['pair']['status']} |" for b in cat["books"]]
    C.atomic_write(lib / "catalog.md", "\n".join(md) + "\n")
    with (lib / "log.md").open("a", encoding="utf-8") as f:
        f.write(f"| {now} | {cy['slug']} | v{cy.get('version', 1)} | {cy.get('status')} | {len(cy['chapters'])} | {action} | lint={lint_status} pair={pair['status']} |\n")
    C.emit({"catalog": str(cat_p), "action": action, "slug": cy["slug"], "lint": lint_status, "pair": pair["status"], "books": len(cat["books"]), "warning": warn}, {"stage": "register"})


if __name__ == "__main__":
    main()
