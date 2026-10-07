#!/usr/bin/env python3
"""gdd_extract — 企劃規格書 xlsx → gdd-pack 草稿（v1）。

三層：
  1. 分頁分類器（deterministic）：同義詞 + 內容特徵，把每個分頁貼上 role；貼不上 → unknown，不猜。
  2. extract-map.yaml：分類結果 + 人工覆寫（role / feature_id / 表頭列）。第一次 --classify 產草稿，人看一眼，之後全自動。
  3. 抽取：依 map 產 gdd.yaml / symbols.yaml / screens.yaml / rules/*.md / info.yaml / i18n.csv，
     內嵌圖依儲存格錨點抽到 assets/{圖騰,全示意圖,規格書競品圖}/，最後交 gdd_lint（lint 紅 = 需要人補的地方，是預期訊號）。

role：version_log / design_points / spec / odds / symbols / rules / ui / info / i18n / art_list / audio / prob / flow / storyboard / protocol / dev_notes / unknown

用法:
    python gdd_extract.py --xlsx <規格書.xlsx> --out gdd/<slug> --classify        # 只產 extract-map.yaml 草稿 + 報告
    python gdd_extract.py --xlsx <規格書.xlsx> --out gdd/<slug> [--map <map.yaml>] # 抽取（無 map 則先自動分類）
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gdd_common as C  # noqa: E402

# ── 分類器 ────────────────────────────────────────────────────────────────

ROLE_NAMES = {
    "version_log": ["版本紀錄", "版本異動", "競品參考與版本", "版本"],
    "design_points": ["設計要點", "討論", "讨论", "優化", "規格概要", "總覽", "研七規格"],
    "spec": ["規格玩法", "基本規格", "遊戲概述", "規格概述", "玩法說明", "規格"],
    "symbols": ["圖騰設計", "圖騰", "symbol"],
    "ui": ["介面設計", "介面說明", "介面", "ui", "loading頁", "loading"],
    "info": ["info"],
    "i18n": ["多國語系", "多國翻譯", "多國", "翻譯", "語系"],
    "art_list": ["美術需求", "美術清單", "美術"],
    "audio": ["音樂音效", "音效", "音樂"],
    "prob": ["機率設計", "機率隱性", "機率", "隱性設定", "rtp"],
    "flow": ["流程圖", "玩法流程", "流程"],
    "storyboard": ["動態分鏡", "表演流程", "分鏡", "演出流程", "演出說明", "表演項目"],
    "protocol": ["protocol", "porotol", "協定", "start_game", "spin"],
    "dev_notes": ["會議", "議題", "開發紀錄", "調整項目", "資料收集", "確認單", "回饋單", "code review", "cheat", "外部連結",
                  "工作表", "动画命名", "動畫命名", "特殊需求", "cocos", "unity", "討論", "讨论"],
    "rules": ["main game", "maingame", "free game", "freegame", "feature game", "featuregame", "feature", "jackpot", "jp game",
              "bonus game", "cash game", "玩法", "主遊戲", "免費遊戲", "彩金", "特殊遊戲", "extra bet", "額外系統", "道具卡",
              "trigger", "respin", "假轉", "押注段", "paylines"],
}
SHORT_EXACT = {"spin", "rtp", "ui", "流程", "工作表", "feature", "trigger", "respin", "start_game"}
ROLE_ORDER = ["protocol", "audio", "art_list", "i18n", "info", "symbols", "ui", "prob", "flow", "storyboard", "version_log",
              "dev_notes", "design_points", "spec", "rules"]
SPEC_KEYS = ["盤面", "對獎方式", "對獎", "收費", "成本", "Free Game", "Feature Game", "JP", "JP Game", "Jackpot", "Extra Bet",
             "道具卡", "Play Bonus", "爆獎卡", "版型", "寬高", "機種名", "圖騰"]
FEATURE_ALIAS = [("main", ["main", "主遊戲"]), ("fg", ["free", "免費"]), ("jp", ["jackpot", "彩金", "jp"]),
                 ("feature", ["feature", "特殊"]), ("win", ["報獎", "面板"]), ("extra", ["extra bet"]),
                 ("green", ["綠"]), ("blue", ["藍"]), ("red", ["紅"]), ("gold", ["金"]), ("yellow", ["黃"]), ("purple", ["紫"])]
I18N_HEADERS = {"en": ["英文", "english", "en"], "tw": ["繁中", "繁體", "tw"], "cn": ["簡中", "简中", "簡體", "cn"], "jp": ["日文", "日本", "jp"],
                "th": ["泰文", "th"], "id": ["印尼", "id"], "vi": ["越南", "vi"], "usage": ["用途", "類型", "備註"]}
SYMBOL_HEADERS = {"code": ["圖騰", "代號", "symbol"], "name": ["名稱", "樣式說明"], "type": ["類型"], "size": ["面積"], "frame": ["外框"],
                  "tone": ["色調"], "desc": ["說明"], "note": ["備註"], "ref": ["參考"]}
CODE_RE = re.compile(r"^(M\d{1,2}|[AKQJ]|10|9|8|SC\w*|SSC|W|WILD|Wild|Scatter|BONUS|B\d?)$", re.I)


def norm(s) -> str:
    return re.sub(r"^\d+[\.\s、]*", "", str(s or "")).strip().lower()


def rows_of(ws) -> list[list]:
    """回傳 [(row_idx1, [(col_idx0, text)])]，只含非空列。"""
    out = []
    for i, r in enumerate(ws.iter_rows(values_only=True), 1):
        cells = [(j, str(c).strip()) for j, c in enumerate(r) if c not in (None, "") and str(c).strip() != ""]
        if cells:
            out.append((i, cells))
    return out


def features_of(rows: list) -> dict:
    texts = [t for _, cells in rows for _, t in cells]
    joined = " ".join(texts)
    return {
        "rows": len(rows),
        "spec_keys": sum(1 for t in texts if t in SPEC_KEYS),
        "symid": any(t in ("SymID", "Symbol ID", "程式代號", "程式\n代號") or "SymID" in t for t in texts),
        "odds_hdr": sum(1 for t in texts if re.match(r"^[2-5]連線$|^x[3-5]$|^[3-5]:\s*$", t)),
        "placeholders": len(re.findall(r"\{[^{}]+圖\}|\(SC[^)]*圖\)", joined)),
        "lang_hdr": sum(1 for t in texts if t in ("英文", "繁中", "簡中", "日文", "泰文", "印尼文", "印尼", "越南文")),
        "sym_hdr": sum(1 for t in texts if t in ("圖騰", "參考", "名稱", "類型", "面積", "外框", "色調")),
        "codes": sum(1 for t in texts if CODE_RE.match(t)),
        "bullets": sum(1 for t in texts if re.match(r"^[❖◆●※•]|^\d+[\.\)]", t)),
        "page": sum(1 for t in texts if re.match(r"^Page \d+$", t)),
    }


def classify_sheet(name: str, rows: list) -> tuple[str, float, str]:
    n = norm(name)
    f = features_of(rows)
    texts = {t for _, cells in rows for _, t in cells}
    # 1) 名字明確的支援類分頁先排除（美術/音效/協定/多國），避免內容特徵誤判
    for role in ("protocol", "audio", "art_list", "i18n", "version_log", "dev_notes", "prob", "storyboard", "flow", "ui"):
        for kw in ROLE_NAMES[role]:
            k = kw.lower()
            hit = (n == k or n.startswith(k)) if k in SHORT_EXACT else (k in n)
            if hit:
                return role, 0.8, f"名稱命中「{kw}」"
    # 2) 內容特徵
    if f["lang_hdr"] >= 3:
        return "i18n", 0.95, f"表頭含 {f['lang_hdr']} 個語系欄"
    if f["sym_hdr"] >= 4 and "參考" in texts and "圖騰" in texts:
        return "symbols", 0.9, "圖騰設計表頭（圖騰/參考/名稱…）"
    if n == "info" or (f["placeholders"] >= 3 and f["page"] >= 1):
        return "info", 0.9, "INFO 分頁 / 佔位符 + Page"
    if any(kw in n for kw in ROLE_NAMES["rules"]) and not any(kw in n for kw in ("規格玩法", "基本規格")):
        return "rules", 0.75, "名稱為玩法頁"
    if "盤面" in texts and ({"對獎方式", "對獎", "收費", "成本"} & texts) and f["spec_keys"] >= 3:
        return "spec", 0.9, f"含盤面/對獎/收費等 {f['spec_keys']} 個基本規格鍵"
    for role in ROLE_ORDER:
        for kw in ROLE_NAMES[role]:
            if kw.lower() in n:
                conf = 0.8 if role != "rules" else 0.7
                return role, conf, f"名稱命中「{kw}」"
    if f["bullets"] >= 5 and f["rows"] >= 15:
        return "rules", 0.5, "條列文字為主（推測玩法頁）"
    return "unknown", 0.0, "無命中"


def feature_id_for(name: str, used: set) -> str:
    n = norm(name)
    for fid, kws in FEATURE_ALIAS:
        if any(k in n for k in kws) and fid not in used:
            used.add(fid)
            return fid
    base = re.sub(r"[^a-z0-9]+", "", n) or "f"
    fid, k = base, 1
    while fid in used:
        k += 1
        fid = f"{base}{k}"
    used.add(fid)
    return fid


def build_map(wb, xlsx: pathlib.Path) -> dict:
    sheets = []
    used: set = set()
    for ws in wb.worksheets:
        rows = rows_of(ws)
        role, conf, why = classify_sheet(ws.title, rows)
        ent = {"name": ws.title, "role": role, "confidence": conf, "why": why, "rows": len(rows),
               "images": len(getattr(ws, "_images", []))}
        if role == "rules":
            ent["feature_id"] = feature_id_for(ws.title, used)
            ent["feature_title"] = re.sub(r"^\d+[\.\s、]*", "", ws.title).strip()
        if role == "spec" and features_of(rows)["odds_hdr"] + int(features_of(rows)["symid"]) >= 1:
            ent["has_odds_table"] = True
        sheets.append(ent)
    return {"contract": "1", "source": {"xlsx": xlsx.name, "sha256": C.sha256_file(xlsx)},
            "slug": slug_of(xlsx.stem), "sheets": sheets,
            "notes": ["role 可手改：version_log/design_points/spec/odds/symbols/rules/ui/info/i18n/art_list/audio/prob/flow/storyboard/protocol/dev_notes/unknown",
                      "rules 分頁需 feature_id（main/fg/jp/feature/win/…）；一玩法一章",
                      "改完重跑 gdd_extract --map 即可，分類不會覆蓋手改"]}


def slug_of(stem: str) -> str:
    s = re.sub(r"[\[\]【】()（）]", " ", stem)
    s = re.sub(r"[^a-z0-9一-鿿]+", "-", s.lower()).strip("-")
    return (s or "game")[:48]


# ── 圖片 ──────────────────────────────────────────────────────────────────

def sheet_images(ws) -> list[dict]:
    out = []
    for k, img in enumerate(getattr(ws, "_images", [])):
        a = getattr(img, "anchor", None)
        fr = getattr(a, "_from", None)
        row = (fr.row + 1) if fr is not None else 0
        col = fr.col if fr is not None else 0
        try:
            data = img._data()
        except Exception:  # noqa: BLE001
            continue
        out.append({"row": row, "col": col, "data": data, "fmt": (getattr(img, "format", "png") or "png").lower(), "k": k})
    out.sort(key=lambda x: (x["row"], x["col"], x["k"]))
    return out


def save_image(img: dict, folder: pathlib.Path, name: str) -> str:
    folder.mkdir(parents=True, exist_ok=True)
    ext = "jpg" if img["fmt"] in ("jpeg", "jpg") else "png"
    fn = f"{name}.{ext}"
    p = folder / fn
    if not p.exists() or p.read_bytes() != img["data"]:
        p.write_bytes(img["data"])
    return fn


def safe_name(t: str, limit: int = 40) -> str:
    t = re.sub(r"[\\/:*?\"<>|\s]+", "_", str(t)).strip("_")
    return (t or "img")[:limit]


# ── 各 role 抽取 ──────────────────────────────────────────────────────────

def extract_spec(rows: list) -> list[dict]:
    spec, seen = [], set()
    for _, cells in rows:
        for idx, (j, t) in enumerate(cells):
            if t in SPEC_KEYS and t not in seen and idx + 1 < len(cells):
                v = cells[idx + 1][1]
                seen.add(t)
                ent = {"k": t, "v": v}
                if t in ("盤面", "對獎方式", "對獎", "收費", "成本", "版型", "Free Game", "JP", "JP Game", "Jackpot"):
                    ent["short"] = v.split("；")[0].split("(")[0].split("（")[0].strip()[:18]
                spec.append(ent)
    return spec


def extract_odds(rows: list) -> tuple[list[dict], list[str]]:
    """公版 Odds Table：表頭列含 SymID 與 N連線 → [{code,name,sym_id,odds5/4/3}]。"""
    notes = []
    hdr = None
    for i, (ri, cells) in enumerate(rows):
        texts = [t for _, t in cells]
        if any("SymID" in t for t in texts) and any(re.match(r"^[2-5]連線$", t) for t in texts):
            hdr = (i, {t: j for j, t in cells})
            break
    if not hdr:
        return [], ["找不到 SymID + N連線 表頭（非公版 odds 版型，需人工補 symbols.odds）"]
    i0, cols = hdr
    name_c = next((j for t, j in cols.items() if t in ("名稱",)), None)
    code_c = next((j for t, j in cols.items() if t in ("圖騰",)), None)
    id_c = next((j for t, j in cols.items() if "SymID" in t), None)
    line_c = {int(t[0]): j for t, j in cols.items() if re.match(r"^[2-5]連線$", t)}
    out = []
    for ri, cells in rows[i0 + 1:]:
        d = dict(cells)
        if len(cells) == 1 and cells[0][1] in ("一般圖騰", "特殊圖騰"):
            continue
        code = d.get(code_c)
        if not code:
            if any(t.startswith("玩法") for _, t in cells):
                break
            continue
        rec = {"code": code, "name": d.get(name_c, code), "sym_id": None, "odds": None}
        sid = d.get(id_c)
        if sid and re.match(r"^\d+$", sid):
            rec["sym_id"] = int(sid)
        vals = []
        for n in (5, 4, 3):
            v = d.get(line_c.get(n))
            vals.append(int(float(v)) if v and re.match(r"^\d+(\.\d+)?$", v) else None)
        if all(v is not None for v in vals):
            rec["odds"] = vals
        out.append(rec)
    return out, notes


def extract_symbols(ws, rows: list, folders: dict, pack: pathlib.Path) -> tuple[list[dict], list[str]]:
    """圖騰設計分頁：表頭列（圖騰/參考/名稱/…）+ 錨在列上的參考圖。"""
    notes, out = [], []
    imgs = sheet_images(ws)
    section = "normal"
    hdr = None
    for ri, cells in rows:
        texts = [t for _, t in cells]
        if len(cells) == 1 and texts[0] in ("一般圖騰", "特殊圖騰"):
            section = "normal" if texts[0] == "一般圖騰" else "special"
            hdr = None
            continue
        if sum(1 for t in texts if t in ("圖騰", "參考", "名稱", "類型", "面積", "外框", "色調", "說明", "樣式說明")) >= 4:
            hdr = {}
            for key, syns in SYMBOL_HEADERS.items():
                for j, t in cells:
                    if t in syns:
                        hdr[key] = j
            continue
        if not hdr:
            continue
        d = dict(cells)
        code = d.get(hdr.get("code"))
        typ = d.get(hdr.get("type"), "")
        if not code and typ:
            m = re.search(r"(WILD|SC|SCATTER|BONUS)", typ.upper())
            code = m.group(1) if m else None
        if not code:
            continue
        name = d.get(hdr.get("name")) or code
        if any(x["code"] == code for x in out):
            k = sum(1 for x in out if x["code"].split("-")[0] == code) + 1
            code = f"{code}-{k}"
        rec = {"code": code, "group": section, "sym_id": None, "name": name, "file": None, "soft": False,
               "role": "symbol", "ref": d.get(hdr.get("ref")), "ref_files": [], "odds": None,
               "scene": "主遊戲", "flag": "規格書參考（非定案）",
               "desc": " / ".join(x for x in [typ, d.get(hdr.get("size")), d.get(hdr.get("frame")), d.get(hdr.get("tone")), d.get(hdr.get("desc"))] if x)}
        row_imgs = [im for im in imgs if im["row"] == ri]
        if row_imgs:
            base = safe_name(f"{code}_{name}")
            rec["file"] = save_image(row_imgs[0], folders["symbols"], f"{base}_spec")
            for k, im in enumerate(row_imgs):
                rec["ref_files"].append(save_image(im, folders["reference"], f"{base}_參考{k + 1 if k else ''}"))
        else:
            notes.append(f"圖騰 {code}（{name}）該列無內嵌圖，file 留空需補")
        out.append(rec)
    if not out:
        notes.append("圖騰設計分頁沒有解析到任何圖騰列（表頭需含 圖騰/參考/名稱/類型…）")
    return out, notes


def extract_symbols_horizontal(ws, rows: list, folders: dict) -> tuple[list[dict], list[str]]:
    """研七版基本規格：一列 M1..M6 代號、下方「程式代號」列給 sym_id、代號上下區間錨的圖 → symbols。"""
    imgs = sheet_images(ws)
    out, notes = [], []
    idx = {ri: cells for ri, cells in rows}
    keys = list(idx)
    for k, ri in enumerate(keys):
        cells = idx[ri]
        codes = [(j, t) for j, t in cells if re.match(r"^M\d{1,2}$", t)]
        if len(codes) < 3:
            continue
        id_row = next((r for r in keys[k + 1:k + 12] if any(re.sub(r"\s", "", t) == "程式代號" for _, t in idx[r])), None)
        ids = dict(idx[id_row]) if id_row else {}
        for j, code in codes:
            sid = next((int(v) for jj, v in ids.items() if jj == j and re.match(r"^\d+$", v)), None)
            rec = {"code": code, "group": "normal", "sym_id": sid, "name": code, "file": None, "soft": False, "role": "symbol",
                   "ref_files": [], "odds": None, "scene": "主遊戲", "flag": "規格書參考（非定案）", "desc": f"規格書「{ws.title}」一般圖騰區"}
            near = [im for im in imgs if ri <= im["row"] <= (id_row or ri + 10) and j - 1 <= im["col"] <= j + 2]
            if near:
                rec["file"] = save_image(near[0], folders["symbols"], safe_name(f"{code}_spec"))
                rec["ref_files"] = [save_image(near[0], folders["reference"], safe_name(f"{code}_參考"))]
            out.append(rec)
    # 特殊圖騰：「程式代號 / 圖像 / 說明」表頭
    for k, ri in enumerate(keys):
        cells = idx[ri]
        texts = [re.sub(r"\s", "", t) for _, t in cells]
        if "程式代號" in texts and "說明" in texts:
            id_c = [j for j, t in cells if re.sub(r"\s", "", t) == "程式代號"][0]
            desc_c = [j for j, t in cells if t == "說明"][0]
            cur = None
            for r in keys[k + 1:]:
                d = dict(idx[r])
                if re.match(r"^[一二三四五六七八九十]+、", d.get(idx[r][0][0], "")) and len(idx[r]) == 1:
                    break
                if d.get(id_c) and re.match(r"^\d+$", d[id_c]):
                    name = d.get(desc_c, f"S{d[id_c]}")
                    base = "WILD" if "wild" in name.lower() else "SC" if "scatter" in name.lower() else re.sub(r"[^A-Za-z0-9]+", "", name)[:8] or "S"
                    qual = re.search(r"[（(]\s*([^()（）]+?)\s*[)）]", name)
                    code = f"{base}_{qual.group(1).strip()}" if qual else base
                    if any(x["code"] == code for x in out):
                        code = f"{code}{d[id_c]}"
                    cur = {"code": code, "group": "special", "sym_id": int(d[id_c]), "name": name, "file": None, "soft": False,
                           "role": "symbol", "ref_files": [], "odds": None, "scene": "主遊戲", "flag": "規格書參考（非定案）", "desc": ""}
                    near = [im for im in imgs if r <= im["row"] <= r + 6 and id_c <= im["col"] <= desc_c]
                    if near:
                        cur["file"] = save_image(near[0], folders["symbols"], safe_name(f"{code}_spec"))
                        cur["ref_files"] = [save_image(near[0], folders["reference"], safe_name(f"{code}_參考"))]
                    out.append(cur)
                elif cur and d.get(desc_c):
                    cur["desc"] = (cur["desc"] + " " + d[desc_c]).strip()
            break
    if not out:
        notes.append("基本規格分頁沒有找到 M1..Mn 代號列（水平版型），需人工建 symbols")
    return out, notes


def sheet_to_md_and_screens(ws, rows: list, feature_id: str, folders: dict) -> tuple[str, list[dict]]:
    """玩法/介面分頁 → mini-markdown（條列、表格、段落）+ 錨點圖 → screens。"""
    imgs = sheet_images(ws)
    md: list[str] = []
    screens: list[dict] = []
    table: list[list[str]] = []
    last_text = ""
    step = 0

    def flush_table():
        nonlocal table
        if len(table) >= 2:
            w = max(len(r) for r in table)
            rows_ = [r + [""] * (w - len(r)) for r in table]
            md.append("| " + " | ".join(rows_[0]) + " |")
            md.append("|" + "---|" * w)
            for r in rows_[1:]:
                md.append("| " + " | ".join(r) + " |")
            md.append("")
        elif table:
            md.append("- " + "　".join(table[0]))
            md.append("")
        table = []

    text_rows = [ri for ri, _ in rows]
    img_at: dict[int, list] = {}
    for im in imgs:
        anchor = max([r for r in text_rows if r <= im["row"]] or [text_rows[0] if text_rows else im["row"]])
        img_at.setdefault(anchor, []).append(im)
    for ri, cells in rows:
        texts = [t.replace("\n", " ").replace("|", "／") for _, t in cells]
        if len(texts) == 1:
            last_text = texts[0]
        for im in img_at.get(ri, []):
            step += 1
            title = (last_text or f"{feature_id} 畫面 {step}")[:30]
            fn = save_image(im, folders["screens"], safe_name(f"{feature_id}_{step:02d}_{title}"))
            screens.append({"feature": feature_id, "step": str(step), "title": title, "file": fn,
                            "desc": f"規格書「{ws.title}」第 {im['row']} 列內嵌圖", "lang": None})
        if len(texts) == 1:
            flush_table()
            t = texts[0]
            if re.match(r"^[❖◆●※•\-]\s*", t):
                md.append("- " + re.sub(r"^[❖◆●※•\-]\s*", "", t))
            elif re.match(r"^\d+[\.\)]\s*|^[a-z][\.\)]\s*", t) and not re.match(r"^\d+\)\s*\S{1,12}$", t):
                md.append("- " + t)
            elif re.match(r"^[一二三四五六七八九十]+、|^\d+\)\s*|^Page \d+", t) or (len(t) <= 14 and not re.search(r"[。：:，,]", t)):
                heading = re.sub(r"^\d+\)\s*", "", t)
                md.append(f"### {heading}")
                md.append("")
            else:
                md.append(t)
                md.append("")
            last_text = t
        else:
            table.append(texts)
            last_text = texts[-1] if len(texts[-1]) > len(texts[0]) else texts[0]
    flush_table()
    # 讓連續 bullet 之後有空行
    out, prev_bullet = [], False
    for ln in md:
        if prev_bullet and ln and not ln.startswith("- "):
            out.append("")
        out.append(ln)
        prev_bullet = ln.startswith("- ")
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() + "\n"
    return text, screens


def extract_ui(ws, rows: list, folders: dict) -> list[dict]:
    """介面設計：主遊戲/免費遊戲/彈窗/階層報獎 區段 + 錨點圖 → screens（feature 依區段）。"""
    imgs = sheet_images(ws)
    screens, section, step = [], "main", 0
    sec_map = [("main", ["主遊戲"]), ("fg", ["免費遊戲"]), ("win", ["階層報獎", "報獎"]), ("popup", ["彈窗"]), ("loading", ["Loading", "特色介紹"])]
    desc_by_row = {ri: max((t for _, t in cells), key=len) for ri, cells in rows}
    for ri, cells in rows:
        texts = [t for _, t in cells]
        if len(cells) == 1:
            for sid, kws in sec_map:
                if any(k in texts[0] for k in kws):
                    section = sid
                    step = 0
    for im in imgs:
        # 找該圖所在或之上最近的區段
        sec = "main"
        for ri, cells in rows:
            if ri > im["row"]:
                break
            if len(cells) == 1:
                for sid, kws in sec_map:
                    if any(k in cells[0][1] for k in kws):
                        sec = sid
        step += 1
        near = desc_by_row.get(im["row"]) or next((desc_by_row[r] for r in sorted(desc_by_row) if r > im["row"]), "")
        title = (near.split("\n")[0] if near else f"{sec} 畫面")[:30]
        fn = save_image(im, folders["screens"], safe_name(f"ui_{sec}_{step:02d}"))
        screens.append({"feature": sec, "step": str(step), "title": title, "file": fn, "desc": near[:200] if near else "介面設計參考畫面", "lang": None})
    return screens


def extract_info(ws, rows: list) -> tuple[list[dict], dict]:
    blocks, ph = [], {}
    for ri, cells in rows:
        texts = [t for _, t in cells if t != "★"]
        if not texts or re.match(r"^Page \d+$", texts[0]) or texts[0] in ("zone", "INFO"):
            continue
        if texts[0].startswith("「") or texts[0].startswith("INFO若") or texts[0].startswith("新板"):
            continue
        if len(texts) >= 4 and all(t in ("{N}",) or re.match(r"^[3-5]:\s*$", t) for t in texts):
            continue  # 賠率表 {N} 佔位列
        t = " ".join(texts)
        t = re.sub(r"\((SC[^)]*圖)\)", r"{\1}", t)  # (SC 藍圖) → {SC 藍圖}
        t = re.sub(r"\{([^{}]+)\}", lambda m: "{" + m.group(1).replace(" ", "") + "}", t)
        for m in re.findall(r"\{([^{}]+圖)\}", t):
            ph.setdefault(m, None)
        kind = "p"
        if len(t) <= 12 and not re.search(r"[。，,：:]", t) and not t.startswith("●"):
            kind = "h" if t in ("賠率", "賠率表", "特殊圖騰說明", "特色玩法說明", "免費遊戲說明", "遊戲規則(線型)", "遊戲規則", "特殊玩法", "免費遊戲", "彩金轉輪") else "s"
        blocks.append({"t": kind, "tw": re.sub(r"^●\s*", "", t), "id": f"info-{len(blocks):02d}"})
        if t in ("賠率", "賠率表"):
            blocks[-1]["widget"] = "odds_grid"
    return blocks, ph


def extract_i18n(rows: list, columns: list[str]) -> list[list[str]]:
    hdr = None
    for i, (ri, cells) in enumerate(rows):
        texts = {t: j for j, t in cells}
        hit = {k: next((texts[t] for t in texts if any(t.lower().startswith(s.lower()) for s in syns)), None) for k, syns in I18N_HEADERS.items()}
        if sum(1 for v in hit.values() if v is not None) >= 3:
            hdr = (i, hit)
            break
    if not hdr:
        return []
    i0, hit = hdr
    out = []
    for ri, cells in rows[i0 + 1:]:
        d = dict(cells)
        if not any(d.get(hit[c]) for c in ("en", "tw") if hit.get(c) is not None):
            continue
        out.append([(d.get(hit[c]) or "").replace("\n", " / ") if hit.get(c) is not None else "" for c in columns])
    return out


# ── 主流程 ────────────────────────────────────────────────────────────────

def extract(xlsx: pathlib.Path, out: pathlib.Path, mp: dict) -> dict:
    import yaml  # type: ignore
    import openpyxl  # type: ignore
    wb = openpyxl.load_workbook(str(xlsx), data_only=True)
    out.mkdir(parents=True, exist_ok=True)
    (out / "rules").mkdir(exist_ok=True)
    folders = {k: out / "assets" / v for k, v in (("symbols", "圖騰"), ("screens", "全示意圖"), ("reference", "規格書競品圖"))}
    for f in folders.values():
        f.mkdir(parents=True, exist_ok=True)
    columns = ["en", "tw", "cn", "jp", "th", "id", "vi", "usage"]
    report: dict = {"sheets": [], "notes": [], "counts": {}}
    spec, odds, symbols, screens, rules, i18n = [], [], [], [], {}, []
    info_blocks, ph = [], {}
    features: list[dict] = []
    by_name = {s["name"]: s for s in mp["sheets"]}
    for ws in wb.worksheets:
        ent = by_name.get(ws.title, {"role": "unknown"})
        role = ent.get("role", "unknown")
        rows = rows_of(ws)
        line = {"name": ws.title, "role": role, "images": len(getattr(ws, "_images", []))}
        if role == "spec":
            spec += [s for s in extract_spec(rows) if s["k"] not in {x["k"] for x in spec}]
            o, notes = extract_odds(rows)
            if o:
                odds += o
            else:
                hs, hnotes = extract_symbols_horizontal(ws, rows, folders)
                if hs:
                    symbols += [x for x in hs if x["code"].upper() not in {y["code"].upper() for y in symbols}]
                    notes = hnotes
            report["notes"] += [f"{ws.title}: {n}" for n in notes]
            k = next((i for i, (_, cells) in enumerate(rows) if len(cells) == 1 and cells[0][1] in ("玩法敘述", "玩法說明")), None)
            if k is not None and "main" not in rules:
                md, scr = sheet_to_md_and_screens(ws, rows[k + 1:], "main", folders)
                rules["main"] = md
                screens += scr
                features.append({"id": "main", "title": "主遊戲與玩法", "rules": "rules/main.md", "screens_title": "主遊戲畫面"})
        elif role == "symbols":
            s, notes = extract_symbols(ws, rows, folders, out)
            symbols += s
            report["notes"] += [f"{ws.title}: {n}" for n in notes]
        elif role == "rules":
            fid = ent.get("feature_id") or feature_id_for(ws.title, {f["id"] for f in features})
            md, scr = sheet_to_md_and_screens(ws, rows, fid, folders)
            rules[fid] = md
            screens += scr
            features.append({"id": fid, "title": ent.get("feature_title") or ws.title, "rules": f"rules/{fid}.md",
                             "screens_title": f"{ent.get('feature_title') or ws.title}畫面"})
        elif role == "ui":
            screens += extract_ui(ws, rows, folders)
        elif role == "info":
            b, p = extract_info(ws, rows)
            info_blocks += b
            ph.update({k: v for k, v in p.items() if k not in ph})
        elif role == "i18n":
            i18n += extract_i18n(rows, columns)
        line["handled"] = role in ("spec", "symbols", "rules", "ui", "info", "i18n")
        report["sheets"].append(line)

    # symbols：odds 表補 sym_id / odds / 名稱；只有 odds 沒圖騰設計時也建骨架
    by_code = {s["code"].upper(): s for s in symbols}
    for o in odds:
        s = by_code.get(o["code"].upper())
        if s:
            s["sym_id"], s["odds"] = o["sym_id"], o["odds"]
            if s["name"] == s["code"] and o["name"] != o["code"]:
                s["name"] = o["name"]
        else:
            symbols.append({"code": o["code"], "group": "normal" if re.match(r"^(M\d+|[AKQJ]|10|9|8)$", o["code"]) else "special",
                            "sym_id": o["sym_id"], "name": o["name"], "file": None, "soft": False, "role": "symbol",
                            "ref_files": [], "odds": o["odds"], "scene": "主遊戲", "flag": "僅 Odds Table，無圖"})
    # placeholders 猜 code（子字串），猜不到留 null 讓 lint 報
    for k in list(ph):
        key = k.replace("圖", "").replace(" ", "").upper()
        ph[k] = next((s["code"] for s in symbols if s["code"].upper() in key or key in s["code"].upper()), None)
    # 分組與 feature 骨架
    for sc in screens:
        if sc["feature"] not in {f["id"] for f in features}:
            features.append({"id": sc["feature"], "title": {"main": "主遊戲", "fg": "免費遊戲", "jp": "彩金遊戲", "win": "階段性面板", "popup": "彈窗", "loading": "特色介紹"}.get(sc["feature"], sc["feature"]),
                             "screens_title": "畫面"})
    if not features:
        features.append({"id": "main", "title": "主遊戲", "screens_title": "主遊戲畫面"})
    groups = [{"id": g, "title": {"normal": "一般圖騰", "special": "特殊圖騰", "fg": "免費遊戲圖騰", "jp": "彩金圖騰"}[g]}
              for g in ("normal", "special", "fg", "jp") if any(s["group"] == g for s in symbols)] or [{"id": "normal", "title": "一般圖騰"}]
    odds_order = [s["code"] for s in symbols if s.get("odds")]
    title = next((s["v"] for s in spec if s["k"] == "機種名"), None) or xlsx.stem
    gdd = {"contract": "1", "slug": mp["slug"], "title": f"{title} 素材總覽", "short_title": title, "domain": "slot-game",
           "status": "draft", "distribution": "internal",
           "subtitle": f"由 gdd_extract 自規格書「{xlsx.name}」抽出的草稿；參考圖為競品/概念素材，非定案。",
           "assets": {"root": "assets", "symbols": "圖騰", "screens": "全示意圖", "reference": "規格書競品圖"},
           "spec": spec, "spec_note": "整理自規格書基本規格區。",
           "symbol_groups": groups, "symbols_note": "圖騰為規格書「圖騰設計 / Odds Table」抽出；最終圖請以美術交付的工程命名檔取代。",
           "odds_order": odds_order, "features": features,
           "info_note": "取自規格書 INFO 分頁；{ } 佔位符對應圖騰。", "i18n_note": f"取自規格書多國語系分頁，共 {len(i18n)} 條。",
           "i18n_columns": [{"id": c, "label": l} for c, l in zip(columns, ["英文", "繁中", "簡中", "日文", "泰文", "印尼文", "越南文", "用途"])],
           "extract": {"xlsx": xlsx.name, "sha256": mp["source"]["sha256"], "map": "extract-map.yaml"},
           "build": {"output": "素材總覽.html"}}
    dump = lambda o: yaml.safe_dump(o, allow_unicode=True, sort_keys=False, width=200)  # noqa: E731
    C.atomic_write(out / "gdd.yaml", "# gdd_extract 草稿：請先看 extract-report.md，再改本檔\n" + dump(gdd))
    C.atomic_write(out / "symbols.yaml", dump({"contract": "1", "symbols": symbols}))
    C.atomic_write(out / "screens.yaml", dump({"contract": "1", "screens": screens}))
    C.atomic_write(out / "info.yaml", dump({"contract": "1", "langs": [{"id": "tw", "label": "繁中"}], "default_lang": "tw",
                                              "placeholders": ph, "blocks": info_blocks, "slots": []}))
    with (out / "i18n.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(columns)
        w.writerows(i18n)
    for fid, md in rules.items():
        C.atomic_write(out / "rules" / f"{fid}.md", md)
    report["counts"] = {"spec": len(spec), "odds": len(odds), "symbols": len(symbols), "screens": len(screens),
                        "rules": len(rules), "info_blocks": len(info_blocks), "placeholders_unresolved": sum(1 for v in ph.values() if v is None),
                        "i18n": len(i18n)}
    # 報告
    L = [f"# gdd_extract 報告：{xlsx.name}", "", f"- slug: `{mp['slug']}`  sha256: `{mp['source']['sha256'][:16]}`", "",
         "## 分頁對應", "", "| 分頁 | role | 處理 | 內嵌圖 |", "|---|---|---|---|"]
    for s in report["sheets"]:
        L.append(f"| {s['name']} | {s['role']} | {'✅' if s.get('handled') else '—'} | {s['images']} |")
    L += ["", "## 抽出數量", ""] + [f"- {k}: {v}" for k, v in report["counts"].items()]
    L += ["", "## 需要人補的地方", ""] + ([f"- {n}" for n in report["notes"]] or ["- （無）"])
    unres = [k for k, v in ph.items() if v is None]
    if unres:
        L.append(f"- INFO 佔位符猜不到圖騰 code：{unres} → 改 info.yaml placeholders")
    if any(s["file"] is None for s in symbols):
        L.append(f"- {sum(1 for s in symbols if s['file'] is None)} 個圖騰沒有圖（file: null）→ 補進 assets/圖騰 後填 file；lint 會擋")
    L += ["", "## 下一步", "", "1. 改 `extract-map.yaml` 的 role / feature_id 後重跑（若分頁對錯）", "2. 補圖騰檔與佔位符", "3. `gdd_run.py --pack <此目錄>`", ""]
    C.atomic_write(out / "extract-report.md", "\n".join(L))
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--map")
    ap.add_argument("--classify", action="store_true", help="只產 extract-map.yaml 草稿")
    a = ap.parse_args()
    try:
        import openpyxl  # type: ignore
        import yaml  # type: ignore
    except ImportError:
        C.fail("MISSING_DEP", "需要 openpyxl 與 pyyaml")
    xlsx = pathlib.Path(a.xlsx)
    if not xlsx.exists():
        C.fail("BAD_INPUT", f"找不到 {xlsx}")
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    map_p = pathlib.Path(a.map) if a.map else out / "extract-map.yaml"
    if map_p.exists() and not a.classify:
        mp = yaml.safe_load(map_p.read_text(encoding="utf-8"))
    else:
        wb = openpyxl.load_workbook(str(xlsx), read_only=True, data_only=True)
        mp = build_map(wb, xlsx)
        wb.close()
        C.atomic_write(map_p, "# gdd_extract 分頁對應（可手改 role / feature_id；重跑不會覆蓋）\n" +
                       yaml.safe_dump(mp, allow_unicode=True, sort_keys=False, width=200))
    if a.classify:
        C.emit({"map": str(map_p), "sheets": [{"name": s["name"], "role": s["role"], "confidence": s["confidence"]} for s in mp["sheets"]]},
               {"stage": "gdd_classify"})
        return
    rep = extract(xlsx, out, mp)
    C.emit({"out": str(out), "map": str(map_p), "report": str(out / "extract-report.md"), "counts": rep["counts"],
            "notes": rep["notes"][:6], "next": f"python gdd_run.py --pack {out}"}, {"stage": "gdd_extract"})


if __name__ == "__main__":
    main()
