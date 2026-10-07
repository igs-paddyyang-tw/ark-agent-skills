#!/usr/bin/env python3
"""gdd_lint — gdd-pack 守門（deterministic）。error → exit 3；warn 只列入 lint-report.json 與 todo.md。

規則（見 references/gdd-contract.md「lint」）：
  GDD-YAML     gdd.yaml 契約欄位、features/symbol_groups id 唯一
  GDD-SYM      每個圖騰：code/group/name/file 必填；group 在 symbol_groups；file 存在於 assets.symbols；
               role=symbol 的 sym_id 不重複；odds 恰 3 個整數且 normal 組必有；ref_files 存在於 assets.reference；
               file 不得是 reference 夾的檔（參考圖不當定案）
  GDD-SCR      每張畫面：feature 在 features；file 存在於 assets.screens，或 file 為 null 且附 from（todo）；
               [warn] issue 待修；[warn] 檔名雙副檔名 .png.png；[warn] 泛用檔名（Snipaste_/圖層）
  GDD-INFO     blocks t ∈ h|s|p；{佔位符} 全部可解析到 symbol code；slots.after 對到 block id；slot 圖存在或 null
  GDD-I18N     欄數與 gdd.i18n_columns 一致；每列欄數一致；{佔位符} 可解析（允許數字型 {25}、{000,000,000}）
  GDD-RULES    features.rules 檔存在；表格每列欄數與表頭一致
  GDD-INJECT   所有文字欄位無 script/事件屬性/隱形字元

用法: python gdd_lint.py --pack gdd/<slug> [--report lint-report.json]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gdd_common as C  # noqa: E402


def walk_text(obj, path=""):
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_text(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_text(v, f"{path}[{i}]")


def lint(p: dict) -> dict:
    errs: list[dict] = []
    warns: list[dict] = []
    E = lambda rule, msg, where="": errs.append({"rule": rule, "where": where, "msg": msg})  # noqa: E731
    W = lambda rule, msg, where="": warns.append({"rule": rule, "where": where, "msg": msg})  # noqa: E731
    g, A = p["gdd"], p["assets"]

    # GDD-YAML
    for k in ("contract", "slug", "title", "domain", "assets", "features", "symbol_groups"):
        if k not in g:
            E("GDD-YAML", f"gdd.yaml 缺 {k}")
    if str(g.get("contract")) != C.CONTRACT:
        E("GDD-YAML", f"contract 應為 {C.CONTRACT}")
    if g.get("distribution", "internal") != "internal":
        E("GDD-YAML", "distribution 必為 internal（含競品參考圖）")
    feat_ids = [f.get("id") for f in g.get("features", [])]
    grp_ids = [s.get("id") for s in g.get("symbol_groups", [])]
    if len(set(feat_ids)) != len(feat_ids):
        E("GDD-YAML", "features.id 重複")
    if len(set(grp_ids)) != len(grp_ids):
        E("GDD-YAML", "symbol_groups.id 重複")
    for kind in ("symbols", "screens", "reference"):
        d = A["root"] / A[kind]
        if not d.is_dir():
            E("GDD-YAML", f"資產夾不存在：{d}", f"assets.{kind}")
    ref_files = set(os.listdir(A["root"] / A["reference"])) if (A["root"] / A["reference"]).is_dir() else set()

    # GDD-SYM
    seen_ids: dict = {}
    codes: dict[str, int] = {}
    for i, s in enumerate(p["symbols"]):
        w = f"symbols[{i}] {s.get('code')}"
        for k in ("code", "group", "name", "file"):
            if not s.get(k) and not (k == "file" and (g.get("lint") or {}).get("missing_symbol_file") == "warn"):
                E("GDD-SYM", f"缺 {k}", w)
        if s.get("group") not in grp_ids:
            E("GDD-SYM", f"group '{s.get('group')}' 不在 symbol_groups", w)
        role = s.get("role", "symbol")
        if role not in C.SYMBOL_ROLES:
            E("GDD-SYM", f"role '{role}' 不在 {C.SYMBOL_ROLES}", w)
        f = s.get("file")
        if not f and (g.get("lint") or {}).get("missing_symbol_file") == "warn":
            W("GDD-SYM-FILE", "圖騰無圖（待美術）", w)
        if f:
            if not C.asset_path(p, "symbols", f).exists():
                E("GDD-SYM", f"圖檔不存在：{A['symbols']}/{f}", w)
            if f in ref_files and not C.asset_path(p, "symbols", f).exists():
                E("GDD-SYM", "file 指向參考圖夾的檔案（參考圖不得當定案）", w)
        if role == "symbol":
            codes[s["code"]] = codes.get(s["code"], 0) + 1
            sid = s.get("sym_id")
            if sid is not None:
                if sid in seen_ids:
                    E("GDD-SYM", f"sym_id {sid} 與 {seen_ids[sid]} 重複", w)
                seen_ids[sid] = s.get("code")
        odds = s.get("odds")
        if s.get("group") == "normal" and not odds:
            W("GDD-SYM-ODDS", "normal 組缺 odds（規格書未給或為 server 值）→ 對照表與 INFO 賠率牆顯示 —", w)
        if odds is not None and not (isinstance(odds, list) and len(odds) == 3 and all(isinstance(x, int) for x in odds)):
            E("GDD-SYM", f"odds 必須是 3 個整數 [5,4,3 連線]：{odds}", w)
        for rf in s.get("ref_files", []) or []:
            if rf not in ref_files:
                E("GDD-SYM", f"參考圖不存在：{A['reference']}/{rf}", w)
        if s.get("flag"):
            W("GDD-SYM", f"標記：{s['flag']}", w)
    for c, n in codes.items():
        if n > 1:
            E("GDD-SYM", f"code '{c}' 有 {n} 筆 role=symbol（同 code 只能一筆為 symbol，其餘標 performance）")

    # GDD-SCR
    for i, s in enumerate(p["screens"]):
        w = f"screens[{i}] {s.get('title')}"
        for k in C.SCREEN_REQUIRED:
            if k not in s or s.get(k) in (None, ""):
                E("GDD-SCR", f"缺 {k}", w)
        if s.get("feature") not in feat_ids:
            E("GDD-SCR", f"feature '{s.get('feature')}' 不在 features", w)
        f = s.get("file")
        if f is None:
            if not s.get("from"):
                E("GDD-SCR", "待補畫面（file: null）必須附 from（分鏡 / 需求表來源）", w)
        else:
            if not C.asset_path(p, "screens", f).exists():
                E("GDD-SCR", f"示意圖不存在：{A['screens']}/{f}", w)
            if C.BAD_EXT_RE.search(f):
                W("GDD-SCR-HYGIENE", f"檔名雙副檔名：{f}（請美術改名）", w)
            if C.GENERIC_NAME_RE.match(f):
                W("GDD-SCR-HYGIENE", f"泛用檔名：{f}（建議依「機種_玩法_畫面_日期」命名）", w)
        if s.get("issue"):
            W("GDD-SCR-ISSUE", f"待修：{s['issue']}", w)

    # GDD-INFO
    info = p["info"]
    sym_idx = C.symbol_index(p)
    ph = info.get("placeholders", {}) or {}
    for k, code in ph.items():
        if code not in sym_idx:
            E("GDD-INFO", f"placeholders.{k} → '{code}' 不是 role=symbol 的 code")
    block_ids: set[str] = set()
    langs = [l["id"] for l in info.get("langs", [])]
    for i, b in enumerate(info.get("blocks", [])):
        w = f"info.blocks[{i}]"
        if b.get("t") not in C.INFO_BLOCK_TYPES:
            E("GDD-INFO", f"t '{b.get('t')}' 不在 {C.INFO_BLOCK_TYPES}", w)
        if b.get("id"):
            if b["id"] in block_ids:
                E("GDD-INFO", f"block id 重複：{b['id']}", w)
            block_ids.add(b["id"])
        for lang in langs:
            for m in C.PLACEHOLDER_RE.findall(str(b.get(lang, "") or "")):
                if re.fullmatch(r"[\d,.\sxX×~～+\-N]+", m):
                    continue  # 數字型佔位符 {N} {80} {000,000}
                if m not in ph:
                    E("GDD-INFO", f"{lang} 佔位符 {{{m}}} 未在 placeholders 定義", w)
    for i, sl in enumerate(info.get("slots", [])):
        w = f"info.slots[{i}]"
        if sl.get("after") not in block_ids:
            E("GDD-INFO", f"slot 錨點 '{sl.get('after')}' 不是任何 block 的 id", w)
        for it in sl.get("items", []):
            if it.get("file") and not C.asset_path(p, "screens", it["file"]).exists():
                E("GDD-INFO", f"slot 圖不存在：{it['file']}", w)
            if not it.get("file"):
                W("GDD-INFO-TODO", f"INFO 插圖待補：{it.get('label')}", w)

    # GDD-I18N
    cols = [c["id"] for c in g.get("i18n_columns", [])]
    if p["i18n_header"] and cols and p["i18n_header"] != cols:
        E("GDD-I18N", f"i18n.csv 表頭 {p['i18n_header']} 與 gdd.i18n_columns {cols} 不一致")
    for i, r in enumerate(p["i18n_rows"]):
        if len(r) != len(p["i18n_header"]):
            E("GDD-I18N", f"第 {i + 1} 列欄數 {len(r)} ≠ {len(p['i18n_header'])}")
        for cell in r:
            for m in C.PLACEHOLDER_RE.findall(cell):
                if m not in ph and not m.replace(",", "").replace("0", "").strip("0123456789") == "" and not m.isdigit():
                    W("GDD-I18N", f"第 {i + 1} 列佔位符 {{{m}}} 非圖騰亦非數字型")

    # GDD-RULES
    for f in g.get("features", []):
        rp = f.get("rules")
        if rp and not (p["dir"] / rp).exists():
            E("GDD-RULES", f"rules 檔不存在：{rp}", f"features.{f.get('id')}")
        for t_i, t in enumerate(C.md_tables(p["rules"].get(f.get("id"), ""))):
            n = len(t[0])
            for r_i, r in enumerate(t):
                if len(r) != n:
                    E("GDD-RULES", f"表格 {t_i + 1} 第 {r_i + 1} 列欄數 {len(r)} ≠ 表頭 {n}", f"features.{f.get('id')}")

    # GDD-INJECT
    for path, t in list(walk_text(g, "gdd")) + list(walk_text(p["symbols"], "symbols")) + list(walk_text(p["screens"], "screens")) + \
            list(walk_text(info, "info")) + [(f"i18n[{i}]", " ".join(r)) for i, r in enumerate(p["i18n_rows"])] + \
            [(f"rules.{k}", v) for k, v in p["rules"].items()]:
        if C.INJECT_RE.search(t):
            E("GDD-INJECT", "含 script / iframe / 事件屬性", path)
        if C.INVISIBLE_RE.search(t):
            E("GDD-INJECT", "含隱形字元", path)

    counts = {"symbols": len(p["symbols"]), "screens": len(p["screens"]),
              "screens_todo": sum(1 for s in p["screens"] if s.get("file") is None),
              "info_blocks": len(info.get("blocks", [])), "i18n_rows": len(p["i18n_rows"])}
    return {"contract": C.CONTRACT, "pack": p["gdd"].get("slug"), "status": "PASS" if not errs else "FAIL",
            "errors": errs, "warnings": warns, "counts": counts}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", required=True)
    ap.add_argument("--report", help="lint-report.json 路徑（預設 <pack>/lint-report.json）")
    a = ap.parse_args()
    pack = C.pack_dir(a.pack)
    rep = lint(C.load_pack(pack))
    out = pathlib.Path(a.report) if a.report else pack / "lint-report.json"
    C.atomic_write(out, json.dumps(rep, ensure_ascii=False, indent=1))
    data = {"report": str(out), "status": rep["status"], "errors": len(rep["errors"]), "warnings": len(rep["warnings"]),
            "counts": rep["counts"], "first_errors": rep["errors"][:8]}
    if rep["errors"]:
        C.fail("GATE_BLOCKED", f"gdd_lint FAIL：{len(rep['errors'])} 個 error", "讀 lint-report.json；修資料或資產，不繞 lint", data)
    C.emit(data, {"stage": "gdd_lint"})


if __name__ == "__main__":
    main()
