#!/usr/bin/env python3
"""atlas_compile — run（game-spec.v1.md + evidence + decisions + kb-refs）→ atlas/<slug>/（圖文遊戲規格書的 source of truth）。

用法:
  python atlas_compile.py --run <run> --slug <game-slug> [--out atlas] [--from v1|draft] [--title "..."]
產出：
  atlas/<slug>/atlas.yaml          書契約（game 區塊：domain / run_id / video_sha256 / spec_sha256 / distribution: internal）
  atlas/<slug>/00-preface.md       序：這是什麼遊戲 / 這本書怎麼讀 / 來源與版本 / 全書地圖
  atlas/<slug>/NN-<chapter>.md     五段：一句話 / 畫面 / 規則 / 未知與決議 / 相關機制（文字逐條繼承 spec bullet）
  atlas/<slug>/assets/figures/     figure（atlas_figures）
  atlas/<slug>/sources/            唯讀：spec、evidence.jsonl、decisions、kb-refs、manifest 摘要
規則：文字只能來自 spec（不呼叫 LLM）；--from draft 的書鎖 status: draft、封面水印。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import atlas_common as C  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
ORDER = ["OBSERVED", "INFERRED", "DECIDED", "FROM_KB", "PROPOSED", "UNKNOWN"]
KEY_ZH = {  # claim key 前綴 → 術語表中文
    "game": "遊戲身分", "flow": "主流程", "ui": "介面", "fx": "動畫與回饋", "reel": "轉輪", "symbols": "符號", "wild": "Wild",
    "scatter": "Scatter", "win": "中獎判定", "free_spin": "免費遊戲", "bonus": "Bonus", "jackpot": "Jackpot", "room": "房間",
    "cannon": "砲台", "fish": "魚種", "special": "特殊武器", "boss": "Boss", "multiplayer": "多人", "fast": "快速遊戲",
    "round": "回合", "bet": "下注", "result": "結果機制", "payout": "賠付", "action": "回合內操作",
}


def bullet_md(b: dict, tag: str) -> str:
    """spec bullet → atlas bullet（保留全部欄位，前置 provenance 標記）。"""
    return f"- **{tag}** {b['raw']}"


def section_blocks(spec_doc: dict, sid: str) -> dict:
    s = next((x for x in spec_doc["sections"] if x["id"] == sid), None)
    return s or {"blocks": {}, "lines": [], "title": sid}


def main() -> None:
    ap = argparse.ArgumentParser(description="compile atlas from run")
    ap.add_argument("--run", required=True)
    ap.add_argument("--slug", required=True, help="kebab-case 遊戲代號（書的唯一 id）")
    ap.add_argument("--out", default="atlas")
    ap.add_argument("--from", dest="src", default="v1", choices=["v1", "draft"])
    ap.add_argument("--title")
    ap.add_argument("--author", default=os.getenv("ARK_AUTHOR", "paddyyang"))
    a = ap.parse_args()
    if not re.match(r"^[a-z][a-z0-9-]{1,48}$", a.slug):
        C.fail("BAD_INPUT", "slug 需 kebab-case", "例: dragon-fortune")
    run = C.run_dir(a.run)
    m = C.load_manifest(run)
    resolved, atlas_pack, stale = C.load_atlas_pack(run)
    spec_name = "game-spec.v1.md" if a.src == "v1" else "game-spec.draft.md"
    if not (run / spec_name).exists():
        C.fail("BAD_INPUT", f"缺 {spec_name}", "先跑 ark-game-spec 的 gs_run --stage decide（或 --from draft）")
    spec_md = (run / spec_name).read_text(encoding="utf-8")
    spec = C.parse_spec(spec_md)
    analysis = C.yaml_load(run / "game-analysis.yaml")
    kb = C.yaml_load(run / "kb-refs.yaml") if (run / "kb-refs.yaml").exists() else {"items": []}
    decisions = C.yaml_load(run / "decisions.yaml") if (run / "decisions.yaml").exists() else {"decisions": []}
    evidence = C.load_evidence(run)
    chapters_spec = atlas_pack.get("chapters")
    if not chapters_spec:
        C.fail("BAD_INPUT", "pack 沒有 atlas outline（resolved.atlas.chapters 為空）", "ark-game-domains 的 _core/atlas/outline.yaml")

    book = pathlib.Path(a.out) / a.slug
    if book.exists():
        for p in book.glob("[0-9][0-9]-*.md"):
            p.unlink()
    (book / "sources").mkdir(parents=True, exist_ok=True)
    with C.Timer() as t:
        # sources（唯讀複本）
        for f in (spec_name, "evidence.jsonl", "game-analysis.yaml", "kb-refs.yaml", "decisions.yaml", "entities.json"):
            if (run / f).exists():
                shutil.copy2(run / f, book / "sources" / f)
                os.chmod(book / "sources" / f, 0o444)
        C.atomic_write(book / "sources" / "run-manifest.json", json.dumps(
            {k: m.get(k) for k in ("run_id", "video", "domain", "domain_source", "pack_version", "pack_sha256", "skill_versions", "created_at")},
            ensure_ascii=False, indent=1))
        # figures
        r = subprocess.run([sys.executable, str(HERE / "atlas_figures.py"), "--run", str(run), "--book", str(book)],
                           capture_output=True, text=True, encoding="utf-8")
        try:
            figj = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:  # noqa: BLE001
            C.fail("QUERY_FAILED", f"atlas_figures 失敗: {r.stderr[-300:]}", "")
        if not figj.get("success"):
            print(json.dumps(figj, ensure_ascii=False)); sys.exit(1)
        figures = json.loads((book / "figures.json").read_text(encoding="utf-8"))["figures"]
        fig_by_ch: dict[str, list[dict]] = {}
        for f in figures:
            fig_by_ch.setdefault(f["chapter"], []).append(f)
        hero = next((f for f in figures if f["type"] == "hero"), None)

        # 統計
        claims = [c for it in analysis["items"] for c in it["claims"]]
        dapp = json.loads((run / "decisions-applied.json").read_text(encoding="utf-8")) if (run / "decisions-applied.json").exists() else {"applied": {}}
        unknown_n = sum(1 for c in claims if c["provenance"] in ("UNKNOWN", "NOT_OBSERVED") and c["key"] not in dapp["applied"])
        tags = sorted({t for it in resolved["analysis"]["items"] for t in it.get("kb_tags", [])} | {resolved["domain"]})
        title = a.title or f"{resolved['display_name']}競品規格書 — {a.slug}"
        status = "draft" if a.src == "draft" else "review"

        chapter_list, n = [], 0
        for ch in chapters_spec:
            if ch.get("anchor"):
                continue
            n_str = f"{n:02d}"
            fname = f"{n_str}-{ch['id'].replace('_', '-')}.md"
            figs = fig_by_ch.get(ch["id"], [])
            sec_items = {si for sid in ch.get("sections", []) for si in (next((x.get("source_items") or [] for x in resolved["spec"]["sections"] if x["id"] == sid), []))}
            ch_tags = sorted({t2 for it in resolved["analysis"]["items"] if it["id"] in sec_items for t2 in it.get("kb_tags", [])} | {resolved["domain"]})
            fm = {"chapter": n, "slug": ch["id"], "title": ch["title"], "type": ch.get("type", "chapter"),
                  "sections": ch.get("sections", []), "figures": [f["figure_id"] for f in figs], "tags": ch_tags,
                  "sources": [f"sources/{spec_name}", "sources/evidence.jsonl"], "trust": "deterministic"}
            lines = ["---", C.yaml_dump(fm).rstrip(), "---", "", f"# {n}. {ch['title']}", ""]
            sec_titles = [section_blocks(spec, sid)["title"] for sid in ch.get("sections", [])]
            if ch.get("type") == "preface":
                ov = section_blocks(spec, "overview")
                lines += ["## 這是什麼遊戲", ""]
                if hero:
                    lines += [f"![{hero['caption']}]({hero['file']})", f"<!-- figure:{hero['figure_id']} evidence:{', '.join(hero['evidence'])} -->", ""]
                obs = [b for tag in ("OBSERVED", "INFERRED", "DECIDED") for b in ov["blocks"].get(tag, [])]
                lines += ([bullet_md(b, b["tag"]) for b in obs] or ["- 影片可辨識的遊戲身分見「一句話」章節；本序不下結論。"]) + [""]
                lines += ["## 這本書怎麼讀", "",
                          "- **OBSERVED**：影片直接看到，每條附 evidence 編號（E），對應「證據索引」章的圖與時間碼。",
                          "- **INFERRED**：需要推論才成立，附推論理由；把它當假設，不當事實。",
                          "- **DECIDED**：企畫已決議的值，附決議編號（D）與理由；這是研發要照做的。",
                          "- **FROM_KB**：來自知識庫的既有 pattern（GKB），不是這款遊戲的觀察。",
                          "- **PROPOSED**：知識庫建議、尚未決議；不可當規格。",
                          "- **UNKNOWN**：影片看不到，對應「數值與待決」章的 Q；沒有人可以替影片補數字。",
                          "- 本書所有數字都能回溯到規格書的一條主張；圖上的時間碼可回到原始影片核對。", ""]
                lines += ["## 來源與版本", "",
                          f"- 來源 run：`{m['run_id']}`（domain `{resolved['domain']}`，pack v{resolved['version']}）",
                          f"- 影片 sha256：`{m['video']['sha256'][:16]}…`，長度 {C.fmt_ts(m['video'].get('duration_s', 0))}",
                          f"- 規格來源：`sources/{spec_name}`" + ("（**草稿版**，含未決議項）" if a.src == "draft" else "（已決議 v1）"),
                          f"- 決議數：{len(decisions.get('decisions') or [])}；仍為 UNKNOWN：{unknown_n}",
                          "- 用途：內部競品研究，不得外傳（`distribution: internal`）。", ""]
                lines += ["## 全書地圖", ""]
                for ch2 in chapters_spec:
                    if not ch2.get("anchor") and ch2.get("type") != "preface":
                        lines.append(f"- {ch2['title']}")
                lines.append("")
            elif ch.get("special") == "figure_index":
                lines += ["## 一句話", "", "本章列出全書所有圖與其對應的證據編號、時間碼與偵測事件，供回到原始影片核對。", ""]
                lines += ["## 畫面", ""]
                for f in figures:
                    lines += [f"![{f['caption']}]({f['file']})", f"<!-- figure:{f['figure_id']} evidence:{', '.join(f['evidence'])} -->", ""]
                lines += ["## 規則", "", "| figure | 型別 | 章 | evidence | 時間碼 | 事件 |", "|---|---|---|---|---|---|"]
                lines += [f"| {f['figure_id']} | {f['type']} | {f['chapter']} | {', '.join(f['evidence'])} | {', '.join(f['ts'])} | {', '.join(f['labels'])} |" for f in figures]
                lines += ["", "## 未知與決議", "", "- 無", "", "## 相關機制", "", f"- 全部 evidence 共 {len(evidence)} 筆，見 `sources/evidence.jsonl`。", ""]
            elif ch.get("special") == "glossary":
                lines += ["## 一句話", "", "本章是術語對照、實體清單與知識庫命中頁。", ""]
                lines += ["## 畫面", "", C.NO_FIGURE_SENTENCE, ""]
                lines += ["## 規則", "", "### 主張鍵值對照", "", "| claim key | 中文 | 項目 |", "|---|---|---|"]
                for it in resolved["analysis"]["items"]:
                    for c in it.get("claims", []):
                        lines.append(f"| `{c['key']}` | {KEY_ZH.get(c['key'].split('.')[0], '')} | {it['id']} {it['name']} |")
                lines += ["", "### 實體清單", ""]
                ents = [e for it in analysis["items"] for e in it["entities"]]
                lines += ([f"- **{e['provenance']}** entity `{e['id']}` = {e['entity_type']} — evidence: {', '.join(e['evidence'])}" for e in ents] or ["- 無"])
                lines += ["", "## 未知與決議", "", "- 無", "", "## 相關機制", ""]
                refs = {r["id"]: r for itm in kb.get("items", []) for r in itm.get("refs", [])}
                lines += ([f"- `{r['id']}` {r.get('title') or ''} — trust: {r.get('trust')}" + (" — 跨 domain" if r.get("cross_domain") else "") for r in refs.values()] or ["- 無"]) + [""]
            else:
                lines += ["## 一句話", "", f"本章描述 {' / '.join(sec_titles)}。", ""]
                lines += ["## 畫面", ""]
                if figs:
                    for f in figs:
                        lines += [f"![{f['caption']}]({f['file']})", f"<!-- figure:{f['figure_id']} evidence:{', '.join(f['evidence'])} -->", ""]
                else:
                    lines += [C.NO_FIGURE_SENTENCE, ""]
                lines += ["## 規則", ""]
                unk, dec, kbs = [], [], []
                for sid in ch.get("sections", []):
                    s = section_blocks(spec, sid)
                    if s.get("special") == "state_machine":
                        fence = [l for _ln, l, _t in s["lines"]]  # parse_spec 不收 fence → 直接從原文抓
                        mm = re.search(r"special:state_machine -->\s*```mermaid\n(.*?)```", spec_md, re.S)
                        lines += [f"### {s['title']}", "", "```mermaid", (mm.group(1).rstrip() if mm else "stateDiagram-v2"), "```", ""]
                        continue
                    if s.get("special") == "configuration":
                        lines += [f"### {s['title']}", "", "數值一律由 Math 決定；下列為競品觀察值（competitor_reference），不是我們的規格值。", ""]
                    elif s.get("special") == "open_questions":
                        qs = [l for _ln, l, _t in s["lines"] if l.startswith("- Q")]
                        unk += [f"- **UNKNOWN** {l[2:]}" for l in qs]
                        continue
                    else:
                        lines += [f"### {s['title']}", ""]
                    body = []
                    for tag in ORDER:
                        for b in s["blocks"].get(tag, []):
                            if tag == "UNKNOWN":
                                unk.append(bullet_md(b, tag))
                            elif tag == "DECIDED":
                                dec.append(bullet_md(b, tag))
                                body.append(bullet_md(b, tag))
                            elif tag == "FROM_KB":
                                kbs.append(bullet_md(b, tag))
                            elif tag == "PROPOSED":
                                unk.append(bullet_md(b, tag))
                            else:
                                body.append(bullet_md(b, tag))
                    for _ln, l, tag in s["lines"]:
                        if l.startswith("|"):
                            body.append(l)
                    lines += (body or ["- 本節無已觀察或已決議的主張。"]) + [""]
                dec_short = []
                for b in dec:
                    mm2 = re.search(r"`([^`]+)`.*?decision: (D\d{3,})(?: — rationale: (.*))?$", b)
                    if mm2:
                        dec_short.append(f"- **DECIDED** {mm2.group(2)} `{mm2.group(1)}`" + (f" — 理由：{mm2.group(3)}" if mm2.group(3) else ""))
                dec_short = list(dict.fromkeys(dec_short))
                lines += ["## 未知與決議", ""] + ((list(dict.fromkeys(unk)) + dec_short) or ["- 無"]) + [""]
                lines += ["## 相關機制", ""] + (sorted(set(kbs), key=kbs.index) or ["- 無"]) + [""]
            C.atomic_write(book / fname, "\n".join(lines))
            chapter_list.append({"n": n, "slug": ch["id"], "title": ch["title"], "type": ch.get("type", "chapter"), "file": fname,
                                 "figures": [f["figure_id"] for f in figs]})
            n += 1

        atlas_yaml = {
            "contract": C.CONTRACT, "genre": "atlas", "slug": a.slug, "title": title,
            "subtitle": f"由 {len(evidence)} 筆影片證據與 {len(claims)} 條主張編成", "author": a.author, "version": 1,
            "status": status, "language": "zh-Hant", "distribution": "internal",
            "game": {"domain": resolved["domain"], "display_name": resolved["display_name"], "run_id": m["run_id"],
                     "video_sha256": m["video"]["sha256"], "spec_source": spec_name, "spec_sha256": C.sha_text(spec_md),
                     "evidence_sha256": C.sha_file(run / "evidence.jsonl"), "pack_version": resolved["version"], "pack_sha256": resolved["pack_sha256"],
                     "decisions": len(decisions.get("decisions") or []), "open_questions": unknown_n, "claims": len(claims)},
            "cover": {"image": hero["file"] if hero else None, "accent": atlas_pack.get("style", {}).get("tokens", {}).get("--accent", "#D4B15C")},
            "style": atlas_pack.get("style", {}),
            "shelf": f"games/{resolved['domain']}", "tags": tags, "chapters": chapter_list,
            "created": str(_dt.date.today()), "updated": str(_dt.date.today()),
        }
        C.atomic_write(book / "atlas.yaml", C.yaml_dump(atlas_yaml))
    C.emit({"book": str(book), "chapters": len(chapter_list), "figures": len(figures), "status": status,
            "next": f"python atlas_lint.py --book {book} && python atlas_build.py --book {book}"}, {"stage": "compile", "elapsed_ms": t.elapsed_ms})


if __name__ == "__main__":
    main()
