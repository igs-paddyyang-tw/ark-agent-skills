#!/usr/bin/env python3
"""gdd_from_spec — A 段的 run（game-spec.v1.md / draft + game-analysis + entities + keyframes）→ gdd-pack 草稿。

橋接原則：**逐條繼承、不改寫**。規則 md 直接搬 spec 章節的 provenance bullet（OBSERVED / INFERRED / FROM_KB / PROPOSED /
DECIDED / UNKNOWN），每章開頭留 `<!-- spec:<section_id> sha16 -->` 錨點；spec kv 由 claim 值換算（來源 key 記在 gdd.yaml.extract.claims）；
symbols 骨架來自 entities（無圖，lint 依 gdd.yaml.lint.missing_symbol_file 政策降 warn）；screens 來自 keyframes（複製進 assets/全示意圖）。

用法:
    python gdd_from_spec.py --run artifacts/cva/<run_id> --out data/gdd/<slug> [--slug <slug>] [--from draft|v1]
之後：python gdd_run.py --pack data/gdd/<slug>
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gdd_common as C  # noqa: E402

SECTION_RE = re.compile(r"^## (\d+)\. (.+?)\n<!-- section:([a-z_]+)([^>]*)-->\n(.*?)(?=^## \d+\. |\Z)", re.M | re.S)
BULLET_RE = re.compile(r"^- `([^`]+)` = (.+?)(?: — evidence: ([^—]+?))?(?: — reasoning: .+?)?(?: — confidence: (\w+))?$")
FEATURE_MAP = [  # spec section → gdd feature（一玩法一章）；未列者併入 main
    ("main", "主遊戲", ["overview", "game_flow", "core_rules", "reel_config", "symbol_spec", "paytable", "wild", "scatter", "win_lines", "win_calc"]),
    ("fg", "免費遊戲", ["free_spin", "multiplier"]),
    ("feature", "特殊玩法", ["bonus"]),
    ("jp", "彩金遊戲", ["jackpot"]),
    ("win", "表現與回饋", ["animation", "sound", "ui_ux"]),
]
LABEL_FEATURE = {"fallback": "main", "scene": "main", "reel_stop": "main", "win_change": "main", "big_win": "win",
                 "feature_transition": "feature", "result_reveal": "win", "special_weapon": "feature"}
SECTION_TITLE_ZH = {"overview": "遊戲概述", "game_flow": "遊戲流程", "core_rules": "核心規則", "reel_config": "轉輪配置", "symbol_spec": "符號規格",
                    "paytable": "賠率表", "wild": "Wild", "scatter": "Scatter", "win_lines": "對獎方式", "win_calc": "贏分計算", "free_spin": "免費遊戲",
                    "bonus": "特殊玩法", "multiplier": "乘倍", "jackpot": "彩金", "animation": "動畫表現", "sound": "音效回饋", "ui_ux": "介面",
                    "state_machine": "狀態機", "configuration": "參數", "edge_cases": "邊界情況", "evidence": "證據", "open_questions": "待決問題"}


def parse_spec(text: str) -> list[dict]:
    out = []
    for m in SECTION_RE.finditer(text):
        body = m.group(5).strip("\n")
        claims = {}
        for ln in body.splitlines():
            b = BULLET_RE.match(ln.strip())
            if b:
                claims[b.group(1)] = b.group(2).strip()
        out.append({"n": int(m.group(1)), "title": m.group(2).strip(), "id": m.group(3), "body": body, "claims": claims,
                    "unknown": re.findall(r"^- `([^`]+)` — question: (Q\d+)", body, re.M)})
    return out


def val(claims: dict, key: str):
    v = claims.get(key)
    if v is None:
        return None
    v = v.strip()
    if v in ("true", "True"):
        return True
    if v in ("false", "False"):
        return False
    return v.strip("[]")


def build_spec_kv(sections: list[dict]) -> tuple[list[dict], dict]:
    claims = {k: v for s in sections for k, v in s["claims"].items()}
    kv, src = [], {}

    def add(k, v, key, short=None, short_k=None):
        if v is None:
            return
        ent = {"k": k, "v": str(v)}
        if short is not None:
            ent["short"] = str(short)
        if short_k:
            ent["short_k"] = short_k
        kv.append(ent)
        src[k] = key

    rows, cols, layout = val(claims, "reel.rows"), val(claims, "reel.columns"), val(claims, "reel.layout")
    if rows and cols:
        add("盤面", f"{rows}×{cols}（主遊戲）", "reel.rows/reel.columns", short=f"{rows}×{cols}")
    elif layout:
        add("盤面", layout, "reel.layout", short=layout)
    lines = val(claims, "win_lines.count") or val(claims, "win_lines.lines")
    ways = val(claims, "win_lines.type") or val(claims, "win_lines.mode")
    if lines:
        add("對獎方式", f"{lines} LINES", "win_lines.count", short=f"{lines} LINES", short_k="對獎")
    elif ways:
        add("對獎方式", str(ways).upper(), "win_lines.type", short=str(ways).upper(), short_k="對獎")
    bet = val(claims, "ui.bet_base") or val(claims, "bet.base") or val(claims, "configuration.bet_base")
    if bet:
        add("基礎收費", bet, "bet.base", short=bet, short_k="收費")
    for k, key, lab in (("Free Game", "free_spin.present", "Free Game"), ("Feature Game", "bonus.present", "Feature Game"), ("JP（彩金）", "jackpot.present", "JP 遊戲")):
        v = val(claims, key)
        if v is not None:
            add(k, "Y" if v is True else ("N" if v is False else v), key, short="Y" if v is True else ("N" if v is False else v), short_k=lab)
    title = val(claims, "game.title")
    if title:
        add("機種名", title, "game.title")
    ori = val(claims, "game.orientation")
    if ori:
        add("版型", ori, "game.orientation", short=ori)
    return kv, src


def rules_md(sec: dict, spec_sha: str) -> str:
    L = [f"<!-- spec:{sec['id']} {spec_sha} -->", f"### {SECTION_TITLE_ZH.get(sec['id'], sec['title'])}（{sec['title']}）", ""]
    body = sec["body"]
    # ### OBSERVED 等子標題轉為粗體行 + 原 bullet；表格 / mermaid 原樣（mini-markdown 不支援 fence → 轉成段落）
    for ln in body.splitlines():
        if ln.startswith("### "):
            L.append(f"- **{ln[4:].strip()}**")
        elif ln.startswith("```"):
            continue
        elif ln.startswith("- "):
            L.append("  " + ln if False else ln)
        elif ln.strip():
            L.append(ln)
        else:
            L.append("")
    return re.sub(r"\n{3,}", "\n\n", "\n".join(L)).strip() + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--slug")
    ap.add_argument("--from", dest="src", choices=["auto", "v1", "draft"], default="auto")
    a = ap.parse_args()
    try:
        import yaml  # type: ignore
    except ImportError:
        C.fail("MISSING_DEP", "需要 pyyaml")
    run = pathlib.Path(a.run).resolve()
    spec_p = run / ("game-spec.v1.md" if a.src == "v1" else "game-spec.draft.md" if a.src == "draft" else
                    ("game-spec.v1.md" if (run / "game-spec.v1.md").exists() else "game-spec.draft.md"))
    if not spec_p.exists():
        C.fail("BAD_INPUT", f"缺 {spec_p}", "先跑 ark-game-spec gs_run --stage draft")
    text = spec_p.read_text(encoding="utf-8")
    fm = yaml.safe_load(text.split("\n---\n", 1)[0].lstrip("-\n")) if text.startswith("---") else {}
    sections = parse_spec(text)
    if not sections:
        C.fail("QUERY_FAILED", "spec 沒解析到任何章節（需 `## NN. Title` + `<!-- section:id -->`）")
    spec_sha = C.sha256_file(spec_p)[:16]
    run_id = fm.get("run_id", run.name)
    stage = fm.get("stage", "draft")
    slug = a.slug or re.sub(r"[^a-z0-9-]+", "-", f"spec-{run_id}".lower()).strip("-")[:48]
    out = pathlib.Path(a.out)
    (out / "rules").mkdir(parents=True, exist_ok=True)
    for d in C.ASSET_DIRS.values():
        (out / "assets" / d).mkdir(parents=True, exist_ok=True)

    # spec kv
    kv, kv_src = build_spec_kv(sections)

    # features + rules
    by_id = {s["id"]: s for s in sections}
    features, used = [], set()
    for fid, title, sids in FEATURE_MAP:
        secs = [by_id[s] for s in sids if s in by_id and (by_id[s]["claims"] or by_id[s]["unknown"] or "FROM_KB" in by_id[s]["body"])]
        if not secs and fid != "main":
            continue
        md = "\n".join(rules_md(s, spec_sha) for s in secs) if secs else f"<!-- spec:none {spec_sha} -->\n### 主遊戲\n\n- 規格尚無本章主張。\n"
        C.atomic_write(out / "rules" / f"{fid}.md", md)
        used.update(s["id"] for s in secs)
        features.append({"id": fid, "title": title, "rules": f"rules/{fid}.md", "screens_title": f"{title}畫面",
                         "screens_note": f"來源：影片關鍵幀（run {run_id}）"})
    skipped = [s["id"] for s in sections if s["id"] not in used]

    # symbols from entities + wild/scatter presence
    ent_p = run / "entities.json"
    ents = json.loads(ent_p.read_text(encoding="utf-8")) if ent_p.exists() else {"entities": {}}
    ga_p = run / "game-analysis.yaml"
    ga = yaml.safe_load(ga_p.read_text(encoding="utf-8")) if ga_p.exists() else {"items": []}
    ent_detail = {e["id"]: e for it in ga.get("items", []) for e in it.get("entities", [])}
    symbols = []
    for i, sid in enumerate(ents.get("entities", {}).get("symbol", []), 1):
        e = ent_detail.get(sid, {})
        desc = " / ".join(f"{k}={v}" for k, v in e.items() if k not in ("id", "entity_type", "provenance", "evidence") and v not in (None, ""))
        symbols.append({"code": f"M{i}", "group": "normal", "sym_id": None, "name": sid, "file": None, "soft": False, "role": "symbol",
                        "ref_files": [], "odds": None, "scene": "主遊戲", "flag": f"影片實體 {sid}（{e.get('provenance', 'OBSERVED')}）", "desc": desc})
    claims_all = {k: v for s in sections for k, v in s["claims"].items()}
    for code, key, name in (("WILD", "wild.present", "Wild"), ("SC", "scatter.present", "Scatter")):
        if val(claims_all, key) is True:
            symbols.append({"code": code, "group": "special", "sym_id": None, "name": name, "file": None, "soft": False, "role": "symbol",
                            "ref_files": [], "odds": None, "scene": "主遊戲", "flag": f"規格 {key}=true", "desc": ""})

    # screens from keyframes
    screens = []
    kf_p = run / "frames" / "keyframes.json"
    if kf_p.exists():
        kfs = json.loads(kf_p.read_text(encoding="utf-8")).get("keyframes", [])
        counters: dict[str, int] = {}
        fids = {f["id"] for f in features}
        for kf in kfs:
            src = run / kf["file"]
            if not src.exists():
                continue
            fid = LABEL_FEATURE.get(kf.get("label", ""), "main")
            if fid not in fids:
                fid = "main"
            counters[fid] = counters.get(fid, 0) + 1
            fn = f"E{kf['idx'] + 1:03d}_{kf.get('label', 'frame')}_{kf.get('ts', '').replace(':', '-').replace('.', '_')}{src.suffix}"
            dst = out / "assets" / C.ASSET_DIRS["screens"] / fn
            if not dst.exists() or dst.read_bytes() != src.read_bytes():
                shutil.copy2(src, dst)
            screens.append({"feature": fid, "step": str(counters[fid]), "title": f"{kf.get('label', 'frame')} @ {kf.get('ts', '')}", "file": fn,
                            "desc": (kf.get("extra") or {}).get("note") or f"關鍵幀 {kf.get('label', '')}（{kf.get('detector', '')}）", "lang": None})

    # open questions → todo（screens todo 卡不適用，改進 gdd.yaml.open_questions 給 build/報告用）
    oq = [{"q": q, "key": k, "section": s["id"]} for s in sections for k, q in s["unknown"]]

    title = val(claims_all, "game.title") or f"{fm.get('domain', 'game')} run {run_id}"
    gdd = {"contract": "1", "slug": slug, "title": f"{title} 素材總覽（規格草稿）", "short_title": str(title), "domain": fm.get("domain", "slot-game"),
           "status": "draft", "distribution": "internal",
           "subtitle": f"由 gdd_from_spec 自 {spec_p.name}（{stage}）逐條繼承；影片關鍵幀為競品畫面，僅供內部；數值待 quicktest。",
           "assets": {"root": "assets", **C.ASSET_DIRS},
           "spec": kv, "spec_note": "由 spec claims 換算；來源 key 見 extract.claims。",
           "symbol_groups": [{"id": g, "title": t} for g, t in (("normal", "一般圖騰（影片實體，待美術）"), ("special", "特殊圖騰")) if any(s["group"] == g for s in symbols)] or [{"id": "normal", "title": "一般圖騰"}],
           "symbols_note": "符號來自影片分析實體（不為競品符號取名）；圖檔待美術，賠率待數值。",
           "odds_order": [], "features": features,
           "info_note": "INFO 文案尚未撰寫（規格草稿階段）。", "i18n_note": "多國語系尚未建立。",
           "i18n_columns": [{"id": c, "label": l} for c, l in (("en", "英文"), ("tw", "繁中"), ("cn", "簡中"), ("jp", "日文"), ("th", "泰文"), ("id", "印尼文"), ("vi", "越南文"), ("usage", "用途"))],
           "extract": {"run_id": run_id, "spec_source": spec_p.name, "spec_sha16": spec_sha, "stage": stage, "claims": kv_src, "skipped_sections": skipped},
           "open_questions": oq,
           "lint": {"missing_symbol_file": "warn"},
           "build": {"output": "素材總覽.html"}}
    dump = lambda o: yaml.safe_dump(o, allow_unicode=True, sort_keys=False, width=200)  # noqa: E731
    C.atomic_write(out / "gdd.yaml", "# gdd_from_spec 草稿：規格主張逐條繼承；補圖騰圖、INFO、多國後再 review\n" + dump(gdd))
    C.atomic_write(out / "symbols.yaml", dump({"contract": "1", "symbols": symbols}))
    C.atomic_write(out / "screens.yaml", dump({"contract": "1", "screens": screens}))
    C.atomic_write(out / "info.yaml", dump({"contract": "1", "langs": [{"id": "tw", "label": "繁中"}], "default_lang": "tw", "placeholders": {}, "blocks": [], "slots": []}))
    C.atomic_write(out / "i18n.csv", "en,tw,cn,jp,th,id,vi,usage\n")
    L = [f"# gdd_from_spec 報告：{run_id}", "", f"- 來源：`{spec_p.name}`（{stage}，sha16 {spec_sha}）", f"- 章節 {len(sections)}，進 rules 的 {len(used)}，略過 {skipped}",
         f"- spec kv {len(kv)}：{', '.join(f'{k}←{v}' for k, v in kv_src.items())}", f"- symbols {len(symbols)}（全部無圖）、screens {len(screens)}（關鍵幀）、open questions {len(oq)}", "",
         "## 待決問題（來自 spec UNKNOWN）", ""] + [f"- {q['q']} `{q['key']}`（{q['section']}）" for q in oq] + ["", "## 下一步", "",
         "1. `gdd_run.py --pack` 看 lint（符號缺圖降為 warn）", "2. 用 ark-grill-me 決議 Q → gs_decide 產 v1 → 重跑本工具（同 slug 覆寫）", "3. 美術補圖騰檔、企劃補 INFO / 多國", ""]
    C.atomic_write(out / "from-spec-report.md", "\n".join(L))
    C.emit({"out": str(out), "spec": spec_p.name, "stage": stage, "sections": len(sections), "features": [f["id"] for f in features],
            "spec_kv": len(kv), "symbols": len(symbols), "screens": len(screens), "open_questions": len(oq), "skipped": skipped,
            "next": f"python gdd_run.py --pack {out}"}, {"stage": "gdd_from_spec"})


if __name__ == "__main__":
    main()
