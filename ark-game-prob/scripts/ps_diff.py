#!/usr/bin/env python3
"""ps_diff — 規格 ⇄ 設定檔對照：`prob-data.json`（xlsx 參數）vs 快測設定檔 JSON（ProbSetting 外部化 / odds_<ver>.json）。

目的：抓「規格書寫 300、設定檔是 200」這種不一致（彌勒佛 ReviveThreshold 實例），在跑快測前就擋下來。
對照規則寫在 YAML map（預設 references/config-map.fasttest.yaml），每條 = {xlsx: <選擇器>, config: <鍵路徑>, transform?: <名稱>}。
選擇器（對 prob-data.known）：
  board.<項目>                      基本資訊鍵值            reelsets.weight / reelsets.flags
  weights[<表>].weight              權重表的權重序列          weights[<表>].label
  dual[<表>].<i>.values / .weights  SC/SS 雙欄第 i 欄         yesno[<表>]      → [[是,否],…]
  scalars[<表>]                     單值                      series[<表>].<列標籤>
  matrix[<表>].<小標前綴>            組別×欄矩陣 → 每組 values  paytable.<符號>  → [x3,x4,x5]
  strips.<key>.<組>.lens            輪帶長度
transform：star_to_neg（*2 → -2）、pct（×100）、int、first、drop_last、drop_lead2、lens（子陣列長度）、drop_zero_tail（去尾端 0）、ways_to_lines。
用法: python ps_diff.py --data data/prob/<slug>/prob-data.json --config <config.json> [--map <map.yaml>] [--out <dir>]
交付格式：ps_diff <N> 條規則｜一致 a｜不一致 b｜缺 c → <out>/config-diff.md / .json；不一致 exit 3（--warn-only 降為 0）
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ps_common as C  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_MAP = HERE.parent / "references" / "config-map.fasttest.yaml"


def by_block(items, block):
    for x in items or []:
        if x.get("block") == block or x.get("block", "").upper() == block.upper():
            return x
    return None


def select(K: dict, data: dict, sel: str):
    m = re.match(r"^(\w+)(?:\[([^\]]+)\])?(?:\.(.+))?$", sel.strip())
    if not m:
        raise ValueError(f"bad selector {sel}")
    kind, key, rest = m.group(1), m.group(2), m.group(3)
    if kind == "board":
        return (K.get("board") or {}).get(rest)
    if kind == "paytable":
        for p in K.get("paytable") or []:
            if str(p["sym"]) == rest:
                return [p["odds"][k] for k in sorted(p["odds"], key=lambda s: int(s))]
        return None
    if kind == "reelsets":
        rs = K.get("reelsets")
        if not rs:
            return None
        if rest == "weight":
            return [s["weight"] for s in rs["sets"]]
        if rest == "flags":
            return [s["flags"] for s in rs["sets"]]
        return None
    if kind == "weights":
        w = by_block(K.get("weights"), key)
        if not w:
            return None
        return [i["weight"] for i in w["items"]] if rest == "weight" else [i["label"] for i in w["items"]]
    if kind == "dual":
        d = by_block(K.get("dual"), key)
        if not d:
            return None
        idx, what = rest.split(".", 1)
        col = d["columns"][int(idx)]
        return [p[0] for p in col["pairs"]] if what == "values" else [p[1] for p in col["pairs"]]
    if kind == "yesno":
        y = by_block(K.get("yesno"), key)
        return [[r["yes"], r["no"]] for r in y["rows"]] if y else None
    if kind == "scalars":
        s = by_block(K.get("scalars"), key)
        return s["value"] if s else None
    if kind == "series":
        for s in K.get("series") or []:
            if s["block"] == key:
                for r in s["rows"]:
                    if r["label"] == rest:
                        return r["values"]
                # 以第一列標籤辨識整張（如 保留金龍 → 第二列權重）
        for s in K.get("series") or []:
            if s["block"] == key and s["rows"] and s["rows"][0]["label"] == rest.split(".")[0]:
                lab2 = rest.split(".")[1] if "." in rest else "權重"
                for r in s["rows"]:
                    if r["label"] == lab2:
                        return r["values"]
        return None
    if kind == "matrix":
        for x in K.get("matrix") or []:
            if x["block"] == key and (x.get("caption") or "").startswith(rest):
                nums = [i for i, h in enumerate(x["head"]) if re.fullmatch(r"\d+(\.\d+)?", str(h))]
                return [[(g["values"][i] if i < len(g["values"]) else None) or 0 for i in nums] for g in x["groups"]]
        return None
    if kind == "matrix_head":
        for x in K.get("matrix") or []:
            if x["block"] == key and (x.get("caption") or "").startswith(rest):
                return [float(h) if "." in str(h) else int(h) for h in x["head"] if re.fullmatch(r"\d+(\.\d+)?", str(h))]
        return None
    if kind == "strips":
        parts = rest.split(".")
        g = (data.get("strips") or {}).get(key, {}).get(parts[0])
        if g and parts[-1] == "lens":
            return [len(r) for r in g["reels"]]
        return None
    raise ValueError(f"unknown selector kind {kind}")


def get_path(cfg: dict, path: str):
    cur = cfg
    for part in path.split("."):
        if isinstance(cur, list):
            cur = cur[int(part)]
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
        if cur is None:
            return None
    return cur


def transform(v, name: str | None):
    if v is None or not name:
        return v
    for t in [t.strip() for t in name.split("|")]:
        if t == "star_to_neg":
            v = [(-int(str(x)[1:]) if isinstance(x, str) and x.startswith("*") else x) for x in v]
        elif t == "pct":
            v = [x * 100 for x in v] if isinstance(v, list) else v * 100
        elif t == "int":
            v = [int(x) for x in v] if isinstance(v, list) else int(v)
        elif t == "first":
            v = v[0] if isinstance(v, list) and v else v
        elif t == "drop_zero_tail":
            if isinstance(v, list):
                if v and isinstance(v[0], list):
                    v = [drop_tail(r) for r in v]
                else:
                    v = drop_tail(v)
        elif t == "drop_last":
            v = v[:-1] if isinstance(v, list) else v
        elif t == "drop_lead2":
            v = v[2:] if isinstance(v, list) else v
        elif t == "lens":
            v = [len(x) for x in v] if isinstance(v, list) else v
        elif t == "ways_to_lines":
            v = 243 if str(v).lower().replace(" ", "") == "allways" else v
    return v


def drop_tail(seq):
    seq = list(seq)
    while seq and not seq[-1]:
        seq.pop()
    return seq


def norm(v):
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, list):
        return [norm(x) for x in v]
    return v


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--config", required=True, help="快測設定檔 JSON（ProbSetting 外部化或 odds_<ver>.json）")
    ap.add_argument("--map", default=str(DEFAULT_MAP))
    ap.add_argument("--out", help="輸出目錄（預設 prob-data.json 所在目錄）")
    ap.add_argument("--warn-only", action="store_true")
    a = ap.parse_args()
    dp, cp, mp = pathlib.Path(a.data), pathlib.Path(a.config), pathlib.Path(a.map)
    for p in (dp, cp, mp):
        if not p.exists():
            C.fail("BAD_INPUT", f"找不到 {p}")
    data = json.loads(dp.read_text(encoding="utf-8"))
    cfg = json.loads(cp.read_text(encoding="utf-8"))
    rules = C.yaml_load(mp).get("rules") or []
    K = data.get("known") or {}
    rows, n_ok = [], 0
    for r in rules:
        try:
            xv = transform(select(K, data, r["xlsx"]), r.get("transform"))
        except Exception as e:  # noqa: BLE001
            xv, err = None, str(e)
        cv = get_path(cfg, r["config"])
        if r.get("config_transform"):
            cv = transform(cv, r["config_transform"])
        if xv is None and cv is None:
            status = "missing-both"
        elif xv is None:
            status = "missing-xlsx"
        elif cv is None:
            status = "missing-config"
        else:
            status = "match" if norm(xv) == norm(cv) else "mismatch"
        if status == "match":
            n_ok += 1
        rows.append({"rule": r.get("id") or r["config"], "xlsx": r["xlsx"], "config": r["config"], "status": status,
                     "xlsx_value": xv, "config_value": cv, "note": r.get("note", "")})
    mism = [r for r in rows if r["status"] == "mismatch"]
    miss = [r for r in rows if r["status"].startswith("missing")]
    out = pathlib.Path(a.out) if a.out else dp.parent
    rep = {"contract": "1", "kind": "config-diff", "data": {"path": str(dp), "sha256_16": C.sha16(dp)}, "config": {"path": str(cp), "sha256_16": C.sha16(cp)},
           "map": str(mp), "summary": {"rules": len(rows), "match": n_ok, "mismatch": len(mism), "missing": len(miss)}, "rows": rows}
    C.atomic_write(out / "config-diff.json", json.dumps(rep, ensure_ascii=False, indent=1, default=str))

    def short(v):
        s = json.dumps(v, ensure_ascii=False, default=str)
        return s if len(s) <= 60 else s[:57] + "…"
    md = [f"# 規格 ⇄ 設定檔 對照（{data.get('game')}）", "", f"- xlsx：`{data['source']['name']}`（{data['source']['sha256_16']}）", f"- config：`{cp.name}`（{C.sha16(cp)}）", f"- map：`{mp.name}`",
          f"- 結果：{len(rows)} 條規則｜一致 {n_ok}｜**不一致 {len(mism)}**｜缺 {len(miss)}", "",
          "| 規則 | xlsx 選擇器 | config 鍵 | 狀態 | xlsx 值 | config 值 | 備註 |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        flag = {"match": "✅", "mismatch": "🔴", "missing-xlsx": "⚪ 缺 xlsx", "missing-config": "⚪ 缺 config", "missing-both": "⚪"}[r["status"]]
        md.append(f"| {r['rule']} | `{r['xlsx']}` | `{r['config']}` | {flag} | {short(r['xlsx_value'])} | {short(r['config_value'])} | {r['note']} |")
    md += ["", "> 不一致項請回規格或設定檔改，不要只改本報告；改完重跑 ps_extract（xlsx 變了）或直接重跑 ps_diff（config 變了）。"]
    C.atomic_write(out / "config-diff.md", "\n".join(md) + "\n")
    deliver = f"ps_diff {len(rows)} 條規則｜一致 {n_ok}｜不一致 {len(mism)}｜缺 {len(miss)} → {out / 'config-diff.md'}"
    if mism and not a.warn_only:
        C.fail("GATE_BLOCKED", f"{len(mism)} 條規格 ⇄ 設定檔不一致", deliver, {"mismatch": mism})
    C.emit({**rep["summary"], "mismatch_rules": [r["rule"] for r in mism], "delivery": deliver}, {"stage": "ps_diff"})


if __name__ == "__main__":
    main()
