#!/usr/bin/env python3
"""atlas_from_gdd — gdd-pack（企劃樣板資料層）→ atlas/<slug>/（圖文規格書，契約 v1.1）。

與 atlas_compile（影片 run）平行的第二個入口：同一本書格式、同一套 lint / build / register。
- 規則逐條繼承 rules/*.md：清單項前置 **SPEC**（來源＝規格書）；表格原樣；標題成 ###。
- 一玩法一章：gdd.yaml.features 動態展開；圖騰牆為獨立章（symbol_table figure）；首頁 spec kv 為「一眼看懂」章。
- figures：type `asset`（示意圖，無時間碼，記來源檔 sha）/ `symbol_table`（PIL 拼圖騰牆）；hero = 主遊戲第一張示意圖。
- provenance：SPEC；sources/gdd/ 為唯讀複本；spec_sha256 = 全部來源串接 sha。
用法: python atlas_from_gdd.py --gdd data/gdd/<slug> [--slug <book-slug>] [--out atlas] [--max-figs 6] [--title ...]
"""
from __future__ import annotations

import argparse
import csv
import datetime as _dt
import hashlib
import io
import json
import os
import pathlib
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))  # skill root（_lib）
from _lib import run_common as C  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
SOURCE_FILES = ["gdd.yaml", "symbols.yaml", "screens.yaml", "info.yaml", "i18n.csv"]
NUM_RE = re.compile(r"\d")


def _pil():
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
        return Image, ImageDraw, ImageFont
    except ImportError:
        C.fail("MISSING_DEP", "需要 Pillow", "pip install Pillow")


def font(ImageFont, size: int):
    for p in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/msjh.ttc"):
        if pathlib.Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:  # noqa: BLE001
                pass
    return ImageFont.load_default()


def save_asset(src: pathlib.Path, dst: pathlib.Path, caption: str, max_w: int, Image, ImageDraw, ImageFont) -> dict:
    im = Image.open(src).convert("RGB")
    if im.width > max_w:
        im = im.resize((max_w, int(im.height * max_w / im.width)))
    d = ImageDraw.Draw(im)
    f = font(ImageFont, 18)
    pad = 8
    tw = d.textlength(caption, font=f) if hasattr(d, "textlength") else len(caption) * 10
    d.rectangle([0, im.height - 30, min(im.width, tw + 2 * pad), im.height], fill=(0, 0, 0))
    d.text((pad, im.height - 27), caption, fill=(255, 223, 138), font=f)
    im.save(dst, "JPEG", quality=85)
    return {"w": im.width, "h": im.height}


def symbol_table_image(cells: list[dict], dst: pathlib.Path, Image, ImageDraw, ImageFont, cell=180, cols=6) -> dict:
    rows = (len(cells) + cols - 1) // cols
    W, H = cols * cell, rows * (cell + 54)
    im = Image.new("RGB", (W, H), (20, 16, 13))
    d = ImageDraw.Draw(im)
    f1, f2 = font(ImageFont, 16), font(ImageFont, 13)
    for i, c in enumerate(cells):
        x, y = (i % cols) * cell, (i // cols) * (cell + 54)
        d.rectangle([x + 4, y + 4, x + cell - 4, y + cell - 4], fill=(31, 24, 19), outline=(61, 47, 36))
        if c.get("path") and c["path"].exists():
            try:
                s = Image.open(c["path"]).convert("RGBA")
                s.thumbnail((cell - 24, cell - 24))
                im.paste(s, (x + (cell - s.width) // 2, y + (cell - s.height) // 2), s)
            except Exception:  # noqa: BLE001
                pass
        else:
            d.text((x + 50, y + cell // 2 - 8), "待美術", fill=(138, 120, 104), font=f1)
        d.text((x + 8, y + cell + 2), str(c["code"]), fill=(255, 223, 138), font=f1)
        d.text((x + 8, y + cell + 24), str(c.get("odds") or ""), fill=(168, 153, 138), font=f2)
    im.save(dst, "JPEG", quality=88)
    return {"w": W, "h": H}


def rules_to_atlas(md: str) -> tuple[list[str], str]:
    """rules/*.md → 規則段（SPEC bullet / 表格 / ###）與一句話候選。"""
    out, one = [], None
    for ln in md.splitlines():
        s = ln.rstrip()
        if not s.strip() or s.startswith("<!--"):
            continue
        if s.startswith("### "):
            out.append(s)
            out.append("")
        elif s.startswith("- "):
            body = s[2:].strip()
            if re.match(r"^\*\*(OBSERVED|INFERRED|DECIDED|FROM_KB|PROPOSED|UNKNOWN|SPEC)\*\*", body):
                out.append("- " + body)
            else:
                out.append(f"- **SPEC** {body}")
        elif s.startswith("|"):
            out.append(s)
        elif s.startswith("> "):
            out.append(f"- **SPEC** {s[2:].strip()}")
        else:
            if one is None and not NUM_RE.search(s) and 6 <= len(s) <= 80:
                one = s.strip()
            out.append(f"- **SPEC** {s.strip()}")
    return out, one


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gdd", required=True)
    ap.add_argument("--slug")
    ap.add_argument("--out", default="atlas")
    ap.add_argument("--title")
    ap.add_argument("--author", default=os.getenv("ARK_AUTHOR", "paddyyang"))
    ap.add_argument("--max-figs", type=int, default=6, help="每章最多幾張示意圖（其餘進證據索引）")
    a = ap.parse_args()
    Image, ImageDraw, ImageFont = _pil()
    pack = pathlib.Path(a.gdd).resolve()
    if not (pack / "gdd.yaml").exists():
        C.fail("BAD_INPUT", f"{pack} 不是 gdd-pack")
    g = C.yaml_load(pack / "gdd.yaml")
    slug = a.slug or re.sub(r"[^a-z0-9-]+", "-", str(g.get("slug", pack.name)).lower()).strip("-")
    if not re.match(r"^[a-z][a-z0-9-]{1,48}$", slug):
        C.fail("BAD_INPUT", f"slug 需 kebab-case：{slug}")
    symbols = (C.yaml_load(pack / "symbols.yaml").get("symbols") or []) if (pack / "symbols.yaml").exists() else []
    screens = (C.yaml_load(pack / "screens.yaml").get("screens") or []) if (pack / "screens.yaml").exists() else []
    A = g.get("assets") or {}
    root = (pack / (A.get("root") or ".")).resolve()
    sym_dir, scr_dir = root / A.get("symbols", "圖騰"), root / A.get("screens", "全示意圖")
    rules = {}
    for f in g.get("features", []):
        rp = f.get("rules")
        if rp and (pack / rp).exists():
            rules[f["id"]] = (pack / rp).read_text(encoding="utf-8")

    book = pathlib.Path(a.out) / slug
    for p in book.glob("[0-9][0-9]-*.md") if book.exists() else []:
        p.unlink()
    (book / "sources" / "gdd" / "rules").mkdir(parents=True, exist_ok=True)
    fig_dir = book / "assets" / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    for old in fig_dir.glob("*.jpg"):
        old.unlink()
    with C.Timer() as t:
        # sources：唯讀複本 + 串接 sha
        h = hashlib.sha256()
        copied = []
        for name in SOURCE_FILES + [f"rules/{p.name}" for p in sorted((pack / "rules").glob("*.md"))] if (pack / "rules").exists() else SOURCE_FILES:
            src = pack / name
            if src.exists():
                dst = book / "sources" / "gdd" / name
                if dst.exists():
                    os.chmod(dst, 0o644); dst.unlink()
                shutil.copy2(src, dst)
                os.chmod(dst, 0o444)
                h.update(name.encode()); h.update(src.read_bytes())
                copied.append(name)
        spec_sha = h.hexdigest()
        ev_sha = C.sha_file(pack / "screens.yaml") if (pack / "screens.yaml").exists() else spec_sha
        # 名稱字典（lint ATL-NAME 用）
        names = sorted({str(s["code"]) for s in symbols} | {str(s.get("sym_id")) for s in symbols if s.get("sym_id") is not None} | {f["id"] for f in g.get("features", [])} | {slug})
        C.atomic_write(book / "sources" / "gdd" / "names.json", json.dumps({"names": names}, ensure_ascii=False, indent=1))

        # figures
        figs, n = [], 0
        feat_ids = [f["id"] for f in g.get("features", [])]
        by_feat: dict[str, list[dict]] = {}
        for s in screens:
            if s.get("file") and (scr_dir / s["file"]).exists():
                by_feat.setdefault(s["feature"], []).append(s)

        def new_asset(chapter: str, s: dict, kind="asset") -> dict:
            nonlocal n
            n += 1
            fid = f"F{n:03d}"
            dst = fig_dir / f"{fid}.jpg"
            cap = f"{s['title']} · {s['file']}"
            dims = save_asset(scr_dir / s["file"], dst, cap, 1280, Image, ImageDraw, ImageFont)
            rec = {"figure_id": fid, "type": kind, "chapter": chapter, "evidence": [], "t": [], "ts": [], "labels": [s.get("step", "")],
                   "source": {"kind": "screens", "file": s["file"], "sha256": C.sha_file(scr_dir / s["file"]), "feature": s["feature"]},
                   "src_frames_sha256": [C.sha_file(scr_dir / s["file"])], "file": f"assets/figures/{fid}.jpg", "caption": cap, **dims,
                   "ops": {"max_width": 1280, "burn_caption": True}, "sha256": C.sha_file(dst)}
            figs.append(rec)
            return rec

        hero = None
        main_id = feat_ids[0] if feat_ids else None
        if main_id and by_feat.get(main_id):
            hero = new_asset("preface", by_feat[main_id][0], "hero")
        # symbol tables（每組一張）
        groups = g.get("symbol_groups") or [{"id": "normal", "title": "一般圖騰"}]
        sym_figs: list[dict] = []
        for grp in groups:
            cells = [{"code": s["code"], "odds": " / ".join(map(str, s["odds"])) if s.get("odds") else "", "path": (sym_dir / s["file"]) if s.get("file") else None}
                     for s in symbols if s.get("group") == grp["id"]]
            if not cells:
                continue
            n += 1
            fid = f"F{n:03d}"
            dst = fig_dir / f"{fid}.jpg"
            dims = symbol_table_image(cells, dst, Image, ImageDraw, ImageFont)
            rec = {"figure_id": fid, "type": "symbol_table", "chapter": "symbols", "evidence": [], "t": [], "ts": [], "labels": [grp["id"]],
                   "source": {"kind": "symbols", "group": grp["id"], "codes": [c["code"] for c in cells]}, "src_frames_sha256": [],
                   "file": f"assets/figures/{fid}.jpg", "caption": f"{grp['title']} · {len(cells)} 枚", **dims, "ops": {"cell": 180, "cols": 6}, "sha256": C.sha_file(dst)}
            figs.append(rec); sym_figs.append(rec)
        chapter_figs: dict[str, list[dict]] = {}
        overflow: list[dict] = []
        for fid_ in feat_ids:
            lst = by_feat.get(fid_, [])
            for i, s in enumerate(lst):
                rec = new_asset(fid_, s)
                (chapter_figs.setdefault(fid_, []) if i < a.max_figs else overflow).append(rec)
        C.atomic_write(book / "figures.json", json.dumps({"contract": "1.1", "run_id": f"gdd:{slug}", "figures": figs,
                                                           "stats": {"count": len(figs), "by_type": {t2: sum(1 for f in figs if f["type"] == t2) for t2 in ("hero", "asset", "symbol_table")}}},
                                                          ensure_ascii=False, indent=1))

        # chapters
        chapters, cn = [], 0
        feat_title = {f["id"]: f["title"] for f in g.get("features", [])}
        title = a.title or f"{g.get('short_title') or g.get('title')} 圖文規格書"
        spec_kv = g.get("spec") or []

        def fig_lines(recs: list[dict]) -> list[str]:
            L = []
            for f in recs:
                L += [f"![{f['caption']}]({f['file']})", f"<!-- figure:{f['figure_id']} evidence: -->", ""]
            return L or [C.NO_FIGURE_SENTENCE, ""]

        def write(ch_id: str, ch_title: str, body: list[str], ch_type="chapter", figures_=None, sections=None):
            nonlocal cn
            fname = f"{cn:02d}-{ch_id.replace('_', '-')}.md"
            fm = {"chapter": cn, "slug": ch_id, "title": ch_title, "type": ch_type, "sections": sections or [ch_id],
                  "figures": [f["figure_id"] for f in (figures_ or [])], "tags": [g.get("domain", "slot-game"), "gdd"],
                  "sources": ["sources/gdd/gdd.yaml", "sources/gdd/symbols.yaml", "sources/gdd/screens.yaml"] + [f"sources/gdd/rules/{ch_id}.md"] * (ch_id in rules),
                  "trust": "deterministic", "provenance": "SPEC"}
            lines = ["---", C.yaml_dump(fm).rstrip(), "---", "", f"# {cn}. {ch_title}", ""] + body
            C.atomic_write(book / fname, "\n".join(lines))
            chapters.append({"n": cn, "slug": ch_id, "title": ch_title, "type": ch_type, "file": fname, "figures": fm["figures"]})
            cn += 1

        # 00 序
        body = ["## 這是什麼遊戲", ""] + ([f"![{hero['caption']}]({hero['file']})", f"<!-- figure:{hero['figure_id']} evidence: -->", ""] if hero else []) + \
               [f"- **SPEC** {s['k']}：{s['v']}" for s in spec_kv] + [""] + \
               ["## 這本書怎麼讀", "",
                "- **SPEC**：來自企劃正式規格書（gdd-pack），不是影片觀察；每條可在 `sources/gdd/` 找到原文。",
                "- 圖為規格書示意圖或美術資產，無時間碼；圖說為「畫面標題 · 檔名」，可回 `sources/gdd/screens.yaml` 核對。",
                "- 圖騰牆由 `sources/gdd/symbols.yaml` 拼成，標示代號與賠付；「待美術」表示規格尚無定案圖。",
                "- 本書所有數字都能回溯到規格書來源檔的一行。", ""] + \
               ["## 來源與版本", "",
                f"- 來源 gdd-pack：`{slug}`（domain `{g.get('domain')}`，status {g.get('status')}）",
                f"- 來源檔：{', '.join(f'`sources/gdd/{c}`' for c in copied)}",
                f"- 來源 sha256：`{spec_sha[:16]}…`",
                "- 用途：內部規格對照，不得外傳（`distribution: internal`）。", ""] + \
               ["## 全書地圖", "", "- 一眼看懂", "- 圖騰"] + [f"- {feat_title[f]}" for f in feat_ids] + ["- 證據索引", "- 附錄：名稱對照", ""]
        write("preface", f"序：{g.get('short_title') or g.get('title')}", body, "preface", [hero] if hero else [], ["overview"])
        # 01 一眼看懂
        body = ["## 一句話", "", "本章是規格書首頁的基本規格與各玩法開關。", "", "## 畫面", ""] + fig_lines([hero] if hero else []) + \
               ["## 規則", "", "| 項目 | 規格 |", "|---|---|"] + [f"| {s['k']} | {s['v']} |" for s in spec_kv] + ["", "## 未知與決議", "", "- 無", "", "## 相關機制", "", "- 無", ""]
        write("at_a_glance", "一眼看懂", body, figures_=[hero] if hero else [], sections=["spec"])
        # 02 圖騰
        body = ["## 一句話", "", "本章列出全部圖騰的代號、分組與賠付，圖來自規格書圖騰夾。", "", "## 畫面", ""] + fig_lines(sym_figs) + \
               ["## 規則", "", "| 代號 | SymID | 名稱 | 分組 | 5 / 4 / 3 連線 | 場景 |", "|---|---|---|---|---|---|"] + \
               [f"| `{s['code']}` | {s.get('sym_id') if s.get('sym_id') is not None else '—'} | {s.get('name', '')} | {s.get('group', '')} | {' / '.join(map(str, s['odds'])) if s.get('odds') else '—'} | {s.get('scene', '')} |" for s in symbols] + \
               ["", "## 未知與決議", ""] + ([f"- **UNKNOWN** `{s['code']}` 無定案圖（待美術）" for s in symbols if not s.get("file")] or ["- 無"]) + \
               ["", "## 相關機制", "", "- 無", ""]
        write("symbols", "圖騰", body, figures_=sym_figs, sections=["symbols"])
        # 一玩法一章
        for fid_ in feat_ids:
            rl, one = rules_to_atlas(rules.get(fid_, ""))
            ttl = feat_title[fid_]
            one_line = one or (f"本章描述{ttl}的規則與畫面。" if not NUM_RE.search(ttl) else "本章描述本玩法的規則與畫面。")
            unk = [l for l in rl if l.startswith("- **UNKNOWN**") or l.startswith("- **PROPOSED**")]
            kb = [l for l in rl if l.startswith("- **FROM_KB**")]
            body = ["## 一句話", "", one_line, "", "## 畫面", ""] + fig_lines(chapter_figs.get(fid_, [])) + \
                   ["## 規則", ""] + ([l for l in rl if l not in unk and l not in kb] or ["- 本節無已觀察或已決議的主張。"]) + \
                   ["", "## 未知與決議", ""] + (unk or ["- 無"]) + ["", "## 相關機制", ""] + (kb or ["- 無"]) + [""]
            write(fid_, ttl, body, figures_=chapter_figs.get(fid_, []), sections=[fid_])
        # 證據索引
        body = ["## 一句話", "", "本章列出全書所有圖與其來源檔，供回到規格書資產核對。", "", "## 畫面", ""] + fig_lines(overflow) + \
               ["## 規則", "", "| figure | 型別 | 章 | 來源 |", "|---|---|---|---|"] + \
               [f"| {f['figure_id']} | {f['type']} | {f['chapter']} | {f['source'].get('file') or ','.join(f['source'].get('codes', []))} |" for f in figs] + \
               ["", "## 未知與決議", "", "- 無", "", "## 相關機制", "", "- 全部圖見 `sources/gdd/screens.yaml` 與 `sources/gdd/symbols.yaml`。", ""]
        write("evidence_index", "證據索引", body, figures_=overflow, sections=["evidence"])
        # 附錄：名稱對照
        i18n_rows = []
        if (pack / "i18n.csv").exists():
            i18n_rows = list(csv.reader(io.StringIO((pack / "i18n.csv").read_text(encoding="utf-8"))))[1:]
        body = ["## 一句話", "", "本章是符號代號對工程命名、以及多國語系的對照。", "", "## 畫面", "", C.NO_FIGURE_SENTENCE, "",
                "## 規則", "", "### 符號命名", "", "| 代號 | 工程命名 | 美術原檔名 |", "|---|---|---|"] + \
               [f"| `{s['code']}` | {s.get('file') if s.get('soft') else '—'} | {s.get('art_name') or '—'} |" for s in symbols] + \
               ["", "### 多國語系", "", "| 英文 | 繁中 | 用途 |", "|---|---|---|"] + [f"| {r[0]} | {r[1] if len(r) > 1 else ''} | {r[-1] if len(r) > 2 else ''} |" for r in i18n_rows[:60]] + \
               ["", "## 未知與決議", "", "- 無", "", "## 相關機制", "", "- 無", ""]
        write("glossary", "附錄：名稱對照", body, sections=["glossary"])

        atlas_yaml = {"contract": "1.1", "genre": "atlas", "slug": slug, "title": title,
                      "subtitle": f"由企劃規格書 gdd-pack 編成：{len(symbols)} 枚圖騰、{len(screens)} 張示意圖、{len(feat_ids)} 個玩法章", "author": a.author, "version": 1,
                      "status": "draft" if g.get("status", "draft") == "draft" else "review", "language": "zh-Hant", "distribution": "internal",
                      "game": {"domain": g.get("domain", "slot-game"), "display_name": g.get("short_title") or g.get("title"), "run_id": f"gdd:{slug}",
                               "video_sha256": None, "spec_source": "gdd-pack", "spec_sha256": spec_sha, "evidence_sha256": ev_sha,
                               "gdd_pack": str(pack), "pack_version": None, "pack_sha256": None, "decisions": 0,
                               "open_questions": len(g.get("open_questions") or []), "claims": sum(1 for r in rules.values() for l in r.splitlines() if l.startswith("- "))},
                      "cover": {"image": hero["file"] if hero else None, "accent": "#e9b949"},
                      "style": {"name": "planner-brown-gold", "theme": "dark", "tokens": {"--accent": "#e9b949"}},
                      "shelf": f"games/{g.get('domain', 'slot-game')}", "tags": [g.get("domain", "slot-game"), "gdd"], "chapters": chapters,
                      "created": str(_dt.date.today()), "updated": str(_dt.date.today())}
        C.atomic_write(book / "atlas.yaml", C.yaml_dump(atlas_yaml))
    C.emit({"book": str(book), "chapters": len(chapters), "figures": len(figs), "features": feat_ids, "overflow_figs": len(overflow),
            "next": f"python atlas_lint.py --book {book} && python atlas_build.py --book {book}"}, {"stage": "compile_gdd", "elapsed_ms": t.elapsed_ms})


if __name__ == "__main__":
    main()
