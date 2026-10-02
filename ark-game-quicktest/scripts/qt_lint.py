#!/usr/bin/env python3
"""qt_lint — 快測可跑前守門：odds_<ver>.json 無 null、非 null 欄位有 provenance（P-002）、符號/輪帶/權重自洽。

規則：
  QT-NULL     任何欄位為 null → error（列出路徑）；fake_reel 可空陣列
  QT-PROV     extra_odds 非 null 的參數欄位（除 odds / is_item_card 預設）在 qt-config.yaml.provenance 無來源 → error
  QT-SYM      輪帶內符號 ID 必須在 structure.symbols；odds 表 key 必須是已知符號；每個會付錢的符號 odds 長度 = reels
  QT-REEL     main/free reel_data 每組軸數 = reels；index_set 引用的組別存在；weight 長度 = index_set 長度；權重和 > 0
  QT-RANGE    free_game_num > 0、gate ≥ 1、max_win ≥ 0
  QT-ENGINE   結構超出範本能力（3×3、線型、5 線、收費 5、Wild=1、Scatter=2）→ error（範本照跑但結果錯，審查報告 F-3）；
              qt-config.yaml 宣告 engine.customized: true（工程師已改 engine/）時降為 warning；結構欄位未定 → warning
  QT-CAP      範本 Recorder 固定陣列：sym_id ≥ 32 / 主遊戲輪帶組合 > 11 / FG 型 > 4 → error（runtime panic，F-4）；sym_id = 31 → warning（不印）
  QT-SYMID    符號 ID 不在公版慣例（1 Wild、2 Scatter、3～10 特殊、11～20 高倍、21～30 低倍）→ warning
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


# 範本（data/references/prob-workflow/quicktest-template）實際支援的結構；硬編碼位置見 docs/designs/2026-10-01-quicktest-template-design.md §4.2
TEMPLATE_ENGINE = {"reels": 3, "rows": 3, "pay_mode": "line", "lines": 5, "bet_cost": 5, "wild_id": 1, "scatter_id": 2}
ENGINE_FILES = {"reels": "game/game_process.go、checkline/checkline.go（checkReelList）",
                "rows": "game/game_process.go、linedata/linedata.go",
                "pay_mode": "check/check.go（checkline ↔ checkways 切換）",
                "lines": "odds/odds_1.0.0.go（ConstBetLine）、linedata/linedata.go",
                "bet_cost": "odds/odds_1.0.0.go（ConstBetCost / ConstLineBet）",
                "wild_id": "check/check.go、checkline/checkline.go（常數重複定義）",
                "scatter_id": "check/check.go、checkline/checkline.go（常數重複定義）"}
CAP = {"sym_id": 31, "main_combos": 11, "fg_types": 4}


def engine_checks(st: dict, extra: dict, engine: dict, E, W) -> None:
    customized = bool(engine.get("customized"))
    for k, tv in TEMPLATE_ENGINE.items():
        v = st.get(k)
        if v is None:
            W("QT-ENGINE", f"structure.{k} 未定，無法確認範本（{k}={tv}）是否適用")
        elif v != tv:
            msg = f"structure.{k}={v} ≠ 範本 {tv}；範本會照跑但結果錯誤，需改 {ENGINE_FILES[k]}"
            (W if customized else E)("QT-ENGINE", msg + ("（engine.customized: true，降為警告）" if customized else "；改好後在 qt-config.yaml 加 engine.customized: true"))
    for s in st.get("symbols") or []:
        sid = int(s["sym_id"])
        if sid > CAP["sym_id"]:
            E("QT-CAP", f"符號 {s.get('code')} sym_id={sid} ≥ 32：範本 SymbolHitCount[32] 越界 panic（F-4）；改用 ≤ 30 或擴陣列")
        elif sid == CAP["sym_id"]:
            W("QT-CAP", f"符號 {s.get('code')} sym_id=31：會記錄但報表只印到 30")
        group = (s.get("group") or "").lower()
        if sid == 0 or sid > 30 or (group == "normal" and not 11 <= sid <= 30) or (group and group != "normal" and 11 <= sid <= 30):
            W("QT-SYMID", f"符號 {s.get('code')}（group={s.get('group')}）sym_id={sid} 不在公版慣例區段")
    idx = extra.get("main_game_reel_index_set")
    if isinstance(idx, list) and len(idx) > CAP["main_combos"]:
        E("QT-CAP", f"main_game_reel_index_set 有 {len(idx)} 組合 > 11：範本 ReelSetTotalWin[11] 越界 panic（F-4）")
    tw = extra.get("free_game_type_weight")
    if isinstance(tw, list) and len(tw) > CAP["fg_types"]:
        E("QT-CAP", f"free_game_type_weight 有 {len(tw)} 型 > 4：範本 SpecialGame*[4] 越界 panic（F-4）")


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
    engine_checks(st, extra, qc.get("engine") or {}, E, W)
    return {"status": "PASS" if not errs else "FAIL", "errors": errs, "warnings": warns,
            "counts": {"null": sum(1 for e in errs if e["rule"] == "QT-NULL"), "engine": sum(1 for e in errs if e["rule"] == "QT-ENGINE"),
                       "cap": sum(1 for e in errs if e["rule"] == "QT-CAP"), "symbols": len(ids)}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--version", default="1.0.0")
    a = ap.parse_args()
    d = pathlib.Path(a.dir)
    rep = lint(d, a.version)
    C.atomic_write(d / "lint-report.json", json.dumps(rep, ensure_ascii=False, indent=1))
    data = {"report": str(d / "lint-report.json"), "status": rep["status"], "errors": len(rep["errors"]), "warnings": len(rep["warnings"]),
            "first_errors": [e for e in rep["errors"] if e["rule"] != "QT-NULL"][:10] + [e for e in rep["errors"] if e["rule"] == "QT-NULL"][:10]}
    if rep["errors"]:
        cnt = rep.get("counts", {})
        C.fail("GATE_BLOCKED", f"qt_lint FAIL：{len(rep['errors'])} 個 error（null {cnt.get('null', 0)}、engine {cnt.get('engine', 0)}、cap {cnt.get('cap', 0)}）",
               "null → 補決議 / 輪帶；engine / cap → 範本不支援此結構，需工程師改 engine/ 後宣告 engine.customized；不可手填競品值", data)
    C.emit(data, {"stage": "qt_lint"})


if __name__ == "__main__":
    main()
