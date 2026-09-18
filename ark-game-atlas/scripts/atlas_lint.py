#!/usr/bin/env python3
"""atlas_lint — 圖文規格書的守門（deterministic）。build / register 前必過；error → exit 3。

用法:
  python atlas_lint.py --book atlas/<slug>

規則：
  ATL-YAML      atlas.yaml 必要欄位（slug/title/genre=atlas/status/distribution/game/chapters）
  ATL-CHAPTERS  chapters 與檔案一致、章號連續、frontmatter 必要欄位
  ATL-SECTIONS  一般章五段齊全且順序正確；序四段
  ATL-ONELINE   「一句話」不得含數字
  ATL-FIGURE    「畫面」段 ≥1 figure 或固定句「影片未拍到本章對應畫面。」；figure id 在 figures.json、檔案存在、evidence 在 sources/evidence.jsonl
  ATL-NUM       全書數字必須能在 sources 的 spec bullet 中找到（E/Q/D/GKB/F id、時間碼、章號、frontmatter、表格欄位例外）
  ATL-NAME      反引號名稱 ⊆ spec claim key / entity id / GKB / E / Q / D / F / section id
  ATL-PROV      「規則」段每條 bullet 以 **OBSERVED|INFERRED|DECIDED|FROM_KB|PROPOSED|UNKNOWN** 開頭
  ATL-STALE     atlas.yaml.game.spec_sha256 / evidence_sha256 與 sources/ 現況一致
  ATL-INJECT    章節不得含指令覆寫句型 / 隱形字元
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import atlas_common as C  # noqa: E402

TAG_RE = re.compile(r"^- \*\*(OBSERVED|INFERRED|DECIDED|FROM_KB|PROPOSED|UNKNOWN)\*\* ")
NUM_RE = re.compile(r"\d+(?:\.\d+)?")
ID_TOKEN_RE = re.compile(r"\b(?:E|Q|D|F)\d{3,}\b|GKB-[A-Z0-9]+-[A-Z0-9]+-\d{3,}|\d\d:\d\d:\d\d\.\d{3}|\bv\d+(?:\.\d+)?\b|sha256|[0-9a-f]{12,}…?|\d{8}-[\w-]+")
INJECTION = re.compile(r"(忽略(以上|之前|所有)|ignore (all |the )?(previous|above)|改寫規則|disregard (your|the) (instructions|rules))", re.I)
INVISIBLE = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff]")


def numbers_in(text: str) -> set[str]:
    return set(NUM_RE.findall(ID_TOKEN_RE.sub(" ", text)))


def lint(book) -> dict:
    V = []
    add = lambda rule, where, msg, sev="error": V.append({"rule": rule, "severity": sev, "where": where, "message": msg})  # noqa: E731
    cy = C.yaml_load(book / "atlas.yaml")
    for k in ("slug", "title", "genre", "status", "distribution", "game", "chapters"):
        if k not in cy:
            add("ATL-YAML", "atlas.yaml", f"缺 {k}")
    if cy.get("genre") != "atlas":
        add("ATL-YAML", "atlas.yaml", "genre 必須為 atlas")
    if cy.get("distribution") != "internal":
        add("ATL-YAML", "atlas.yaml", "競品畫面：distribution 必須為 internal", "error")
    game = cy.get("game") or {}
    src = book / "sources"
    spec_p = src / game.get("spec_source", "game-spec.v1.md")
    if not spec_p.exists():
        add("ATL-STALE", "sources", f"缺 {spec_p.name}")
        return {"summary": {"errors": len(V)}, "violations": V}
    spec_md = spec_p.read_text(encoding="utf-8")
    if C.sha_text(spec_md) != game.get("spec_sha256"):
        add("ATL-STALE", "sources", "spec sha 與 atlas.yaml 不一致（run 更新後未重編）")
    if (src / "evidence.jsonl").exists() and C.sha_file(src / "evidence.jsonl") != game.get("evidence_sha256"):
        add("ATL-STALE", "sources", "evidence sha 不一致")
    spec = C.parse_spec(spec_md)
    ev_ids = {json.loads(l)["evidence_id"] for l in (src / "evidence.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()} if (src / "evidence.jsonl").exists() else set()
    figs = json.loads((book / "figures.json").read_text(encoding="utf-8"))["figures"] if (book / "figures.json").exists() else []
    fig_by_id = {f["figure_id"]: f for f in figs}
    # 允許的數字：spec bullet 的原文 + configuration/evidence 表 + atlas.yaml 統計
    allowed_nums: set[str] = set()
    for s in spec["sections"]:
        for bl in s["blocks"].values():
            for b in bl:
                allowed_nums |= numbers_in(b["raw"])
        for _ln, l, _t in s["lines"]:
            allowed_nums |= numbers_in(l)
    allowed_nums |= numbers_in(json.dumps({k: v for k, v in game.items() if k in ("decisions", "open_questions", "claims")}))
    allowed_nums |= numbers_in(str(len(ev_ids)))
    allowed_nums |= numbers_in(C.fmt_ts(0))
    # 名稱字典
    entities = json.loads((src / "entities.json").read_text(encoding="utf-8")).get("all_ids", []) if (src / "entities.json").exists() else []
    claim_keys = {b["key"] for s in spec["sections"] for bl in s["blocks"].values() for b in bl if b["key"]}
    sec_ids = {s["id"] for s in spec["sections"]}
    allowed_names = claim_keys | set(entities) | sec_ids | {"configuration"}
    kb_ids = {t for s in spec["sections"] for b in s["blocks"]["FROM_KB"] for t in b["ticks"]}
    if (src / "kb-refs.yaml").exists():
        kb_ids |= {r["id"] for it in C.yaml_load(src / "kb-refs.yaml").get("items", []) for r in it.get("refs", [])}

    files = C.chapter_files(book)
    listed = [c["file"] for c in cy.get("chapters", [])]
    if [f.name for f in files] != listed:
        add("ATL-CHAPTERS", "atlas.yaml", f"chapters 與檔案不一致: {sorted(set(listed) ^ {f.name for f in files})}")
    for i, f in enumerate(files):
        if not f.name.startswith(f"{i:02d}-"):
            add("ATL-CHAPTERS", f.name, f"章號不連續（期望 {i:02d}）")
        md = f.read_text(encoding="utf-8")
        if INJECTION.search(md) or INVISIBLE.search(md):
            add("ATL-INJECT", f.name, "含指令覆寫句型或隱形字元")
        ch = C.parse_chapter(md)
        fm = ch["frontmatter"]
        for k in ("chapter", "slug", "title", "type", "sections", "figures", "tags", "sources"):
            if k not in fm:
                add("ATL-CHAPTERS", f.name, f"frontmatter 缺 {k}")
        want = list(C.PREFACE_SECTIONS if fm.get("type") == "preface" else C.ATLAS_SECTIONS)
        got = list(ch["sections"].keys())
        if got != want:
            add("ATL-SECTIONS", f.name, f"段落應為 {want}，實為 {got}")
        if fm.get("type") != "preface":
            one = "\n".join(ch["sections"].get("一句話", []))
            if NUM_RE.search(one):
                add("ATL-ONELINE", f.name, "「一句話」不得含數字")
            pic = "\n".join(ch["sections"].get("畫面", []))
            fig_ids = re.findall(r"<!-- figure:(F\d{3,}) evidence:([^>]*) -->", pic)
            if not fig_ids and C.NO_FIGURE_SENTENCE not in pic:
                add("ATL-FIGURE", f.name, "「畫面」段無 figure 也無「影片未拍到」固定句")
            for fid, evs in fig_ids:
                if fid not in fig_by_id:
                    add("ATL-FIGURE", f.name, f"{fid} 不在 figures.json")
                elif not (book / fig_by_id[fid]["file"]).exists():
                    add("ATL-FIGURE", f.name, f"{fid} 圖檔不存在")
                for e in [x.strip() for x in evs.split(",") if x.strip()]:
                    if e not in ev_ids:
                        add("ATL-FIGURE", f.name, f"{fid} 引用不存在的 evidence {e}")
            for l in ch["sections"].get("規則", []):
                if l.startswith("- ") and not TAG_RE.match(l) and not l.startswith("- 本節無") and not l.startswith("- 無"):
                    add("ATL-PROV", f.name, f"規則 bullet 缺 provenance 標記: {l[:60]}")
        # 數字追溯（frontmatter、標題、表格分隔線、圖 alt 例外）
        body_lines = [l for l in ch["body"].splitlines() if not l.startswith(("#", "|", "![", "<!--", "```")) and not l.strip().startswith("|")]
        in_fence = False
        for l in body_lines:
            if l.strip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for num in numbers_in(l) - allowed_nums:
                add("ATL-NUM", f.name, f"數字 {num!r} 無法回溯到 spec: {l.strip()[:70]}")
        body_no_fence = re.sub(r"```.*?```", "", ch["body"], flags=re.S)
        for tick in re.findall(r"`([^`]+)`", body_no_fence):
            if tick in allowed_names or tick in kb_ids or re.match(r"^(E|Q|D|F)\d{3,}$", tick) or re.match(r"^GKB-", tick):
                continue
            if tick.startswith("sources/") or tick == fm.get("slug") or re.match(r"^[0-9a-f]{8,}…?$", tick) or tick == game.get("run_id") or tick == game.get("domain") or tick.startswith("distribution"):
                continue
            add("ATL-NAME", f.name, f"未宣告的名稱 `{tick}`")
    errors = [v for v in V if v["severity"] == "error"]
    return {"summary": {"errors": len(errors), "warnings": len(V) - len(errors), "chapters": len(files), "figures": len(figs)}, "violations": V}


def main() -> None:
    ap = argparse.ArgumentParser(description="atlas lint")
    ap.add_argument("--book", required=True)
    a = ap.parse_args()
    book = C.atlas_dir(a.book)
    with C.Timer() as t:
        rep = lint(book)
    C.atomic_write(book / "lint-report.json", json.dumps(rep, ensure_ascii=False, indent=1))
    if rep["summary"]["errors"]:
        C.fail("GATE_BLOCKED", f"{rep['summary']['errors']} 個 lint error", "見 lint-report.json；修 compile / pack，不手改章節繞 lint", data=rep)
    C.emit(rep, {"stage": "lint", "elapsed_ms": t.elapsed_ms})


if __name__ == "__main__":
    main()
