#!/usr/bin/env python3
"""gen_config — 依 config-map.yaml 從來源產生快測 config json，並逐鍵寫來源標記（ark-game-quicktest 路線 C）。

來源（src）：
  live            線上 Server 機率（ref/live/*.json；path 用點號，數字鍵照字串）
  xlsx            ⓪ 主版機率表（值寫在 map 的 value，ref 寫表名／儲存格）
  engine          原快測引擎（C++ 以 dump 程式輸出的 cpp-original.json；Go 引擎原設定）
  ruled           兩邊衝突經人裁定（value＋ruling: {id, by, date, winner}）
  filled:inferred AI 推定｜filled:designed AI 重設計｜filled:default 範本預設（都必須有 reason 與 check）
轉換（transform）：
  reels_map  各軸符號依 symbol_map 轉碼     odds_map  {線上符號碼: 賠率列} → 引擎符號順序的列表（缺的補 0 列；rows: N 可放大列數給線上新增碼）
  expr       Python 運算式，變數 v = 來源值、e = 引擎原值、smap／sym(x) = 符號對照（例 "100 - v[0]"）
另外：check: engine_equal → 產生值必須與引擎原值相同，不同就記為差異（diff），讓人知道線上改過。
輸出：config json、provenance.json（鍵 → {src, ref, note, semantic, diff}）、摘要（各 src 計數）。
用法：python gen_config.py --map _tuning/config-map.yaml --root data/slot/<slug> --engine config/cpp-original.json --out config/live.json
"""
from __future__ import annotations
import argparse, json, pathlib, sys
import yaml

SRC = {"live", "xlsx", "engine", "ruled", "filled:inferred", "filled:designed", "filled:default"}


def dig(d, path: str):
    for k in path.split("."):
        if isinstance(d, list):
            d = d[int(k)]
        else:
            d = d[k] if k in d else d[str(k)]
    return d


def reels(v, smap):
    """各軸符號轉碼；v 可為 list 或 {"0": …} dict，可多層（組 → 軸 → 格）。"""
    if isinstance(v, dict):
        v = [v[str(i)] for i in range(len(v))]
    if v and isinstance(v[0], (list, dict)) and v[0] and isinstance((v[0] if isinstance(v[0], list) else list(v[0].values()))[0], (list, dict)):
        return [reels(x, smap) for x in v]
    return [[smap.get(str(x), smap.get(x, x)) for x in (reel.values() if isinstance(reel, dict) else reel)] for reel in v]


def odds(v, smap, n, width):
    rows = [[0] * width for _ in range(n)]
    seen = set()
    for k, row in v.items():
        code = smap.get(str(k), smap.get(k))
        if code is None or not (0 <= int(code) < n):  # 對照到賠率表範圍外的碼（例 4→100 的表演碼）略過
            continue
        if int(code) in seen:  # 多個線上碼對到同一引擎碼（例 FG 大 SS 25→12）：保留第一個，不讓後面的覆蓋
            continue
        seen.add(int(code)); rows[int(code)] = list(row)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--map", required=True); ap.add_argument("--root", required=True); ap.add_argument("--engine", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--provenance")
    a = ap.parse_args()
    root = pathlib.Path(a.root)
    m = yaml.safe_load(pathlib.Path(a.map).read_text(encoding="utf-8"))
    eng = json.loads(pathlib.Path(a.engine).read_text(encoding="utf-8"))
    smap = {str(k): v for k, v in (m.get("symbol_map") or {}).items()}
    lives = {k: json.loads((root / p).read_text(encoding="utf-8")) for k, p in (m.get("live") or {}).items()}
    out, prov, errs = {}, {}, []
    for key, rule in m["keys"].items():
        src = rule.get("src")
        if src not in SRC:
            errs.append(f"{key}: src {src!r} 不合法"); continue
        if src.startswith("filled") and not (rule.get("reason") and rule.get("check")):
            errs.append(f"{key}: AI 補齊必須寫 reason 與 check"); continue
        e = eng.get(key)
        if src == "live":
            lv = lives[rule.get("from", "prob")]
            v = dig(lv, rule["path"])
        elif src == "engine":
            v = e
        else:
            v = rule.get("value")
        t = rule.get("transform")
        if t == "reels_map":
            v = reels(v, smap)
        elif t == "odds_map":
            v = odds(v, smap, int(rule.get("rows") or len(e)), len(e[0]))  # rows：線上新增符號碼（引擎原表沒有的列）時可加大
        elif t == "expr":
            v = eval(rule["expr"], {"v": v, "e": e, "smap": smap, "sym": lambda x: smap.get(str(x), x), "__builtins__": __builtins__})  # noqa: S307（map 檔由移植者撰寫、受版控）
        out[key] = v
        p = {"src": src, "ref": rule.get("ref") or rule.get("path") or ((m.get("engine_label") or "engine-original") + ":" + key if src == "engine" else None)}
        for f in ("note", "semantic", "reason", "check", "ruling"):
            if rule.get(f):
                p[f] = rule[f]
        if src != "engine" and e is not None and v != e:
            p["diff"] = "與原快測引擎不同"
        prov[key] = p
    for key in eng:
        if key not in out:
            errs.append(f"{key}: 引擎有、map 沒列（每個鍵都要標來源）")
    if errs:
        print(json.dumps({"success": False, "errors": errs}, ensure_ascii=False, indent=1)); sys.exit(3)
    pathlib.Path(a.out).write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    pp = pathlib.Path(a.provenance or pathlib.Path(a.out).with_suffix(".provenance.json"))
    summary = {}
    for p in prov.values():
        summary[p["src"]] = summary.get(p["src"], 0) + 1
    pp.write_text(json.dumps({"summary": summary, "keys": prov}, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"success": True, "summary": summary, "diff": [k for k, p in prov.items() if p.get("diff")]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
