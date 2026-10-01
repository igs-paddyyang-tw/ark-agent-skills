#!/usr/bin/env python3
"""qt_lint — 快測可跑前守門：odds_<ver>.json 無 null、非 null 欄位有 provenance（P-002）、符號/輪帶/權重自洽。

規則：
  QT-NULL     任何欄位為 null → error（列出路徑）；fake_reel 可空陣列
  QT-PROV     extra_odds 非 null 的參數欄位（除 odds / is_item_card 預設）在 qt-config.yaml.provenance 無來源 → error
  QT-SYM      輪帶內符號 ID 必須在 structure.symbols；odds 表 key 必須是已知符號；每個會付錢的符號 odds 長度 = reels
  QT-REEL     main/free reel_data 每組軸數 = reels；index_set 引用的組別存在；weight 長度 = index_set 長度；權重和 > 0
  QT-RANGE    free_game_num > 0、gate ≥ 1、max_win ≥ 0
用法: python qt_lint.py --dir data/quicktest/<slug> [--version 1.0.0]   → lint-report.json；error exit 3
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qt_common as C  # noqa: E402


def walk_null(obj, path="") -> list[str]:
    out = []
    if obj is None:
        return [path or "<root>"]
    if isinstance(obj, dict):
        for k, v in obj.items():
            out += walk_null(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += walk_null(v, f"{path}[{i}]")
    return out


def lint(d: pathlib.Path, version: str) -> dict:
    errs, warns = [], []
    E = lambda r, m: errs.append({"rule": r, "msg": m})  # noqa: E731
    W = lambda r, m: warns.append({"rule": r, "msg": m})  # noqa: E731
    jp = d / "odds" / f"odds_{version}.json"
    qp = d / "qt-config.yaml"
    if not jp.exists():
        E("QT-NULL", f"缺 {jp}")
        return {"status": "FAIL", "errors": errs, "warnings": warns}
    j = json.loads(jp.read_text(encoding="utf-8"))
    qc = C.yaml_load(qp) if qp.exists() else {}
    for p in walk_null(j):
        E("QT-NULL", f"{p} 為 null（TO_BE_DECIDED）")
    prov = qc.get("provenance") or {}
    extra = j.get("extra_odds") or {}
    for k, v in extra.items():
        if v is not None and k not in ("odds",) and f"extra_odds.{k}" not in prov:
            E("QT-PROV", f"extra_odds.{k}={v!r} 無來源（provenance）——P-002 不得無決議填值")
    st = qc.get("structure") or {}
    reels = st.get("reels")
    ids = {int(s["sym_id"]) for s in st.get("symbols") or []}
    odds = extra.get("odds") or {}
    for k, v in odds.items():
        if ids and int(k) not in ids:
            E("QT-SYM", f"odds 表符號 {k} 不在 structure.symbols")
        if v is not None and reels and len(v) != reels:
            E("QT-SYM", f"odds[{k}] 長度 {len(v)} ≠ reels {reels}")
    for key in ("main_game_reel_data", "free_game_reel_data"):
        groups = j.get(key)
        if not groups:
            continue
        for gi, g in enumerate(groups):
            if reels and len(g) != reels:
                E("QT-REEL", f"{key}[{gi}] 軸數 {len(g)} ≠ reels {reels}")
            for ri, strip in enumerate(g):
                bad = sorted({x for x in strip if ids and x not in ids})
                if bad:
                    E("QT-SYM", f"{key}[{gi}][{ri}] 含未知符號 {bad}")
                if len(strip) < (st.get("rows") or 1):
                    E("QT-REEL", f"{key}[{gi}][{ri}] 帶長 {len(strip)} < rows")
        idx_key = "main_game_reel_index_set" if key.startswith("main") else "free_game_reel_index_set"
        w_key = "main_game_reel_set_weight" if key.startswith("main") else "free_game_reel_set_weight"
        idx, w = extra.get(idx_key), extra.get(w_key)
        # 範本語意：index_set[i] = 第 i 個「輪帶組合」在每一軸用哪組帶（長度 = reels，值 < 組數）；
        # main 的 weight[i] 對應組合 i；free 的 weight[type][i]（type = 超強/強/中/弱 四種）
        if idx is not None:
            for i, combo in enumerate(idx):
                if reels and len(combo) < reels:
                    E("QT-REEL", f"{idx_key}[{i}] 長度 {len(combo)} < reels {reels}")
                elif reels and len(combo) > reels:
                    W("QT-REEL", f"{idx_key}[{i}] 長度 {len(combo)} > reels {reels}（多餘項引擎忽略；範本遺留）")
                for x in combo:
                    if x >= len(groups):
                        E("QT-REEL", f"{idx_key}[{i}] 引用組別 {x} 不存在（共 {len(groups)} 組）")
        if idx is not None and w is not None:
            if key.startswith("main"):
                if len(w) != len(idx):
                    E("QT-REEL", f"{w_key} 長度 {len(w)} ≠ {idx_key} 組合數 {len(idx)}")
                if w and sum(w) <= 0:
                    E("QT-REEL", f"{w_key} 權重和 ≤ 0")
            else:
                for t, wt in enumerate(w):
                    if len(wt) != len(idx):
                        E("QT-REEL", f"{w_key}[{t}] 長度 {len(wt)} ≠ {idx_key} 組合數 {len(idx)}")
                tw = extra.get("free_game_type_weight")
                if tw is not None and len(tw) != len(w):
                    E("QT-REEL", f"free_game_type_weight 長度 {len(tw)} ≠ {w_key} 型別數 {len(w)}")
    for k, cond, msg in (("free_game_num", lambda v: v > 0, "> 0"), ("enter_free_game_gate", lambda v: v >= 1, "≥ 1"), ("max_win", lambda v: v >= 0, "≥ 0")):
        v = extra.get(k)
        if v is not None and not cond(v):
            E("QT-RANGE", f"{k}={v} 應 {msg}")
    if not ids:
        W("QT-SYM", "structure.symbols 為空，無法驗輪帶符號")
    return {"status": "PASS" if not errs else "FAIL", "errors": errs, "warnings": warns,
            "counts": {"null": sum(1 for e in errs if e["rule"] == "QT-NULL"), "symbols": len(ids)}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--version", default="1.0.0")
    a = ap.parse_args()
    d = pathlib.Path(a.dir)
    rep = lint(d, a.version)
    C.atomic_write(d / "lint-report.json", json.dumps(rep, ensure_ascii=False, indent=1))
    data = {"report": str(d / "lint-report.json"), "status": rep["status"], "errors": len(rep["errors"]), "warnings": len(rep["warnings"]),
            "first_errors": rep["errors"][:10]}
    if rep["errors"]:
        C.fail("GATE_BLOCKED", f"qt_lint FAIL：{len(rep['errors'])} 個 error（{rep.get('counts', {}).get('null', 0)} 個 null）", "補決議 / 輪帶後重跑；不可手填競品值", data)
    C.emit(data, {"stage": "qt_lint"})


if __name__ == "__main__":
    main()
