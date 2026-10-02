#!/usr/bin/env python3
"""qt_config — 規格 → 快測範本 odds_<ver>.json 骨架 + qt-config.yaml（結構定案、數值留 null；P-002 落到執行層）。

輸入（都選配，但至少一個）：
  --config-spec  gs_dev 的 config-spec.yaml（structure + parameters[value=null, competitor_reference]）
  --gdd          gdd-pack 目錄（symbols.yaml：code / sym_id / odds[x5,x4,x3]；gdd.yaml.spec：盤面）
  --decisions    decisions.yaml（accept/modify 且有 value 的決議才能填進 json，並記 provenance）
輸出：<out>/odds/odds_<ver>.json（範本契約；未定欄位 = null）、<out>/qt-config.yaml（結構常數、符號表、每個非 null 欄位的來源）

用法: python qt_config.py --out data/quicktest/<slug> [--version 1.0.0] [--config-spec …] [--gdd …] [--decisions …] [--reels 5 --rows 3]
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qt_common as C  # noqa: E402

# 範本 extra_odds 欄位 ← 規格 claim / decision topic 的對應（只做結構對應，值由決議給）
PARAM_MAP = {
    "free_game_num": ["free_spin.count_awarded", "free_spin.count"],
    "enter_free_game_gate": ["scatter.trigger_count", "free_spin.trigger_count"],
    "free_game_retrigger_spin_num": ["free_spin.retrigger_spins"],
    "free_game_retrigger_gate": ["free_spin.retrigger_count"],
    "max_win": ["win.max_multiplier", "max_win"],
    "extra_rate": ["bet.extra_rate", "extra_bet.rate"],
}
TEMPLATE_KEYS = ["odds", "extra_rate", "enter_free_game_gate", "free_game_retrigger_gate", "free_game_retrigger_spin_num", "free_game_num",
                 "is_item_card", "max_win", "jackpot_multiple", "jackpot_acc_rate", "main_game_reel_index_set", "main_game_reel_set_weight",
                 "free_game_type_weight", "free_game_reel_index_set", "free_game_reel_set_weight"]

# ISSUE-QT-001：符號 group → 線賠角色（play_role）。只有 payline（連線賠率）符號進 extra_odds.odds。
# WILD/SC/籌碼/JP 本質不是「連線賠率值」—— 它們的價值在代替/觸發/收集/彩金，不該被當 odds 要值。
# group 無宣告預設 normal（= payline），與舊行為相容（舊 gdd 多半只有 normal 符號）。
GROUP_PLAY_ROLE = {"normal": "payline", "special": "trigger", "fg": "collectible", "jp": "jackpot"}


def _play_role(group: str | None, code: str, has_odds: bool) -> str:
    """判定符號的線賠角色。group 最可信；group 缺時用 code 前綴 + 有無 odds 兜底。

    - 有 group：直接查表（special 內 code 以 W 開頭另標 wild）。
    - 無 group：**只在「看得出是 WILD/SC 且無 odds」時**才判非線賠 —— 真 WILD/SC 在 gdd
      通常無 odds。避免誤傷 code 剛好以 W 開頭、但有 odds 的 normal 符號（如 Watermelon）。
      與 qt_config 既有的 structure.wild_id/scatter_id 判法（靠 code 前綴）一致。
    """
    g = (group or "").lower()
    cu = code.upper()
    if g:  # 有明確 group
        if g in ("special", "wild") and cu.startswith("W"):
            return "wild"
        return GROUP_PLAY_ROLE.get(g, "payline")
    # 無 group：code 前綴兜底，但只對「無 odds」的符號生效（有 odds 一律當線賠）
    if not has_odds:
        if cu.startswith("W"):
            return "wild"
        if cu.startswith("SC"):
            return "trigger"
    return "payline"




def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--version", default="1.0.0")
    ap.add_argument("--config-spec")
    ap.add_argument("--gdd")
    ap.add_argument("--decisions")
    ap.add_argument("--reels", type=int)
    ap.add_argument("--rows", type=int)
    ap.add_argument("--game")
    ap.add_argument("--pay-mode", choices=["line", "ways"])
    ap.add_argument("--lines", type=int)
    ap.add_argument("--bet-cost", type=int)
    a = ap.parse_args()
    if not (a.config_spec or a.gdd):
        C.fail("BAD_INPUT", "至少要 --config-spec 或 --gdd")
    out = pathlib.Path(a.out)
    (out / "odds").mkdir(parents=True, exist_ok=True)
    prov: dict[str, str] = {}
    notes: list[str] = []

    cfg = C.yaml_load(pathlib.Path(a.config_spec)) if a.config_spec else {}
    params = {p["name"]: p for p in (cfg.get("parameters") or [])}
    dec = C.yaml_load(pathlib.Path(a.decisions)) if a.decisions else {}
    decided: dict[str, tuple] = {}
    for d in dec.get("decisions") or []:
        if d.get("decision") in ("accept", "modify") and d.get("value") is not None:
            decided[d["topic"]] = (d["value"], d.get("decision_id"))

    # 結構：盤面
    reels, rows = a.reels, a.rows
    for name, key in (("reels", "reel.columns"), ("rows", "reel.rows")):
        if locals()[name] is None:
            if key in decided:
                v, did = decided[key]
                if name == "reels": reels = int(v)
                else: rows = int(v)
                prov[f"structure.{name}"] = did
            elif key in params and (params[key].get("competitor_reference") or {}).get("value") is not None:
                v = int(params[key]["competitor_reference"]["value"])
                if name == "reels": reels = v
                else: rows = v
                prov[f"structure.{name}"] = f"competitor_reference({','.join(params[key]['competitor_reference'].get('evidence', []))})"
                notes.append(f"{name} 取自競品觀察（P-002 允許：結構可由 OBSERVED 定案）")
    gdd = C.yaml_load(pathlib.Path(a.gdd) / "gdd.yaml") if a.gdd else {}
    if (reels is None or rows is None) and gdd:
        for s in gdd.get("spec", []):
            m = re.search(r"(\d+)\s*[×xX]\s*(\d+)", str(s.get("v", "")))
            if s.get("k") == "盤面" and m:
                rows, reels = rows or int(m.group(1)), reels or int(m.group(2))
                prov.setdefault("structure.reels", "gdd.spec.盤面"); prov.setdefault("structure.rows", "gdd.spec.盤面")
    if reels is None or rows is None:
        notes.append("盤面（reels/rows）未定：用 --reels/--rows 或決議 reel.columns/reel.rows")

    # 結構：對獎方式 / 線數 / 收費（給 qt_lint QT-ENGINE 判斷範本能不能跑；gdd 沒寫就留 null）
    pay_mode, lines, bet_cost = a.pay_mode, a.lines, a.bet_cost
    for s in gdd.get("spec", []) if gdd else []:
        k, v = str(s.get("k", "")), str(s.get("v", ""))
        if "對獎" in k:
            if pay_mode is None:
                if re.search(r"ways|路", v, re.I):
                    pay_mode = "ways"
                elif re.search(r"lines?|線", v, re.I):
                    pay_mode = "line"
                if pay_mode:
                    prov.setdefault("structure.pay_mode", f"gdd.spec.{k}")
            m = re.search(r"(\d+)\s*(?:lines?|線)", v, re.I)
            if lines is None and m:
                lines = int(m.group(1)); prov.setdefault("structure.lines", f"gdd.spec.{k}")
        if bet_cost is None and any(t in k for t in ("收費", "成本")):
            m = re.search(r"(\d+)", v)
            if m:
                bet_cost = int(m.group(1)); prov.setdefault("structure.bet_cost", f"gdd.spec.{k}")
    for name, val in (("pay_mode", a.pay_mode), ("lines", a.lines), ("bet_cost", a.bet_cost)):
        if val is not None:
            prov[f"structure.{name}"] = "cli"
    if pay_mode is None or bet_cost is None:
        notes.append("對獎方式 / 收費未定：qt_lint 無法確認範本（3×3、5 線、收費 5）是否適用")

    # 符號表與賠率（gdd symbols）
    symbols = []
    if a.gdd:
        sy = C.yaml_load(pathlib.Path(a.gdd) / "symbols.yaml").get("symbols", [])
        auto_id = 100
        for s in sy:
            if s.get("role", "symbol") != "symbol":
                continue
            sid = s.get("sym_id")
            if sid is None:
                sid = auto_id; auto_id += 1
                notes.append(f"符號 {s['code']} 無 sym_id，暫配 {sid}（需對 Symbol_ID 分頁）")
            symbols.append({"code": s["code"], "sym_id": int(sid), "name": s.get("name"), "group": s.get("group"),
                            "role": _play_role(s.get("group"), s["code"], bool(s.get("odds"))), "odds": s.get("odds")})
    odds_tbl = None
    if symbols and reels:
        odds_tbl = {}
        for s in symbols:
            # ISSUE-QT-001：只有線賠（payline）符號進 odds 表；WILD/trigger/collectible/jackpot 不要值
            if s["role"] != "payline":
                continue
            arr = [0] * reels
            if s["odds"] and len(s["odds"]) == 3 and reels >= 5:
                arr[4], arr[3], arr[2] = int(s["odds"][0]), int(s["odds"][1]), int(s["odds"][2])
            elif s["odds"] and len(s["odds"]) == 3 and reels == 3:
                arr[2] = int(s["odds"][2])
            odds_tbl[str(s["sym_id"])] = arr if s["odds"] else None
            if s["odds"]:
                prov[f"extra_odds.odds.{s['sym_id']}"] = f"gdd.symbols[{s['code']}].odds"
        if any(v is None for v in odds_tbl.values()):
            notes.append("部分線賠符號無賠率（null）：等規格 Odds Table 或決議")
        non_payline = [s["sym_id"] for s in symbols if s["role"] != "payline"]
        if non_payline:
            notes.append(f"非線賠符號不進 odds 表（ISSUE-QT-001）：{non_payline}（role 見 structure.symbols；觸發/收集/彩金走各自結構）")

    # extra_odds 其餘欄位：決議有值才填
    extra = {k: None for k in TEMPLATE_KEYS}
    extra["odds"] = odds_tbl
    extra["is_item_card"] = 0
    prov["extra_odds.is_item_card"] = "default(0)"
    for field, topics in PARAM_MAP.items():
        for t in topics:
            if t in decided:
                v, did = decided[t]
                extra[field] = v
                prov[f"extra_odds.{field}"] = did
                break
    j = {"main_game_reel_data": None, "main_game_fake_reel_data": None, "free_game_reel_data": None, "free_game_fake_reel_data": [],
         "extra_odds": extra}
    C.atomic_write(out / "odds" / f"odds_{a.version}.json", json.dumps(j, ensure_ascii=False, indent=2))
    qc = {"contract": C.CONTRACT, "game": a.game or gdd.get("short_title") or (cfg.get("run_id") or "game"), "version": a.version,
          "structure": {"reels": reels, "rows": rows, "pay_mode": pay_mode, "lines": lines, "bet_cost": bet_cost, "symbols": symbols,
                        "wild_id": next((s["sym_id"] for s in symbols if s["code"].upper().startswith("W")), None),
                        "scatter_id": next((s["sym_id"] for s in symbols if s["code"].upper().startswith("SC")), None)},
          "sources": {"config_spec": a.config_spec, "gdd": a.gdd, "decisions": a.decisions},
          "provenance": prov, "notes": notes,
          "policy": "P-002：parameters 無決議一律 null；qt_lint 有 null 不准跑；非 null 欄位必須在 provenance 有來源"}
    C.atomic_write(out / "qt-config.yaml", C.yaml_dump(qc))
    nulls = [k for k, v in extra.items() if v is None] + [k for k in ("main_game_reel_data", "free_game_reel_data") if j[k] is None]
    C.emit({"odds": str(out / "odds" / f"odds_{a.version}.json"), "qt_config": str(out / "qt-config.yaml"), "reels": reels, "rows": rows,
            "symbols": len(symbols), "odds_filled": sum(1 for v in (odds_tbl or {}).values() if v), "null_fields": nulls, "notes": notes,
            "next": f"python qt_lint.py --dir {out}"}, {"stage": "qt_config"})


if __name__ == "__main__":
    main()
