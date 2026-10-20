#!/usr/bin/env python3
"""gr_probe — 盤點「現在拿得到哪些數據」，產出能力矩陣 capability.json。

報告格式固定，但每款遊戲、每個平台能撈到的欄位不同。probe 依資料集與設定判斷每一節：
ok（完整）、partial（部分，例如沒有歷史基準）、skip（缺資料，報告顯示尚無資料）。
gr_build 依這份矩陣決定算哪些區塊；拿到新欄位後重跑 probe 即可，不用改程式。

用法:
  python gr_probe.py --config report.yaml
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gr_common as C  # noqa: E402


def probe(cfg: dict) -> dict:
    dd = C.data_dir(cfg)
    ds = {}
    for name, spec in C.DATASETS.items():
        p = dd / f"{name}.csv"
        if not p.is_file():
            ds[name] = {"present": False, "columns": []}
            continue
        cols = C.header(p)
        miss = [c for c in spec["required"] if c not in cols]
        ds[name] = {"present": True, "columns": cols, "missing_required": miss}
    bench_dirs = sorted(x.name for x in (dd / "bench").glob("*") if (x / "game_user_daily.csv").is_file()) if (dd / "bench").is_dir() else []

    def has(name, col=None):
        d = ds.get(name) or {}
        if not d.get("present") or d.get("missing_required"):
            return False
        return col is None or col in d["columns"]

    gcols = ds["game_user_daily"]["columns"]
    has_bench = has("benchmark") or bool(bench_dirs)
    trig_cols = [c for c in gcols if c.startswith("trig_")]
    spec = cfg.get("spec") or {}
    sec = {}

    def put(key, status, why=""):
        sec[key] = {"status": status, "why": why}

    if not has("game_user_daily"):
        put("Q1", "skip", "缺 game_user_daily.csv（或必要欄位）")
    elif not has("slot_daily"):
        put("Q1", "partial", "缺 slot_daily.csv：只能算押量、人數，沒有佔比、排名、試玩率")
    else:
        put("Q1", "ok" if has_bench else "partial", "" if has_bench else "沒有歷史基準（benchmark.csv 或 bench/）")
    dims = cfg.get("composition") or []
    dim_ok = [d["title"] for d in dims if d.get("column") in gcols]
    dim_miss = [d["title"] for d in dims if d.get("column") not in gcols]
    if not dim_ok:
        put("Q2", "skip", "game_user_daily 沒有任何 composition 設定的分層欄位")
    elif not has("slot_users"):
        put("Q2", "partial", "缺 slot_users.csv：只有本機組成，沒有全虎機對照")
    else:
        put("Q2", "ok" if not dim_miss else "partial", ("缺欄位：" + "、".join(dim_miss)) if dim_miss else "")
    put("Q3", "skip" if not has("game_user_daily") else ("ok" if has_bench else "partial"),
        "" if has_bench else "沒有歷史基準，回訪率只能看絕對值")
    dseg = (cfg.get("depth") or {}).get("segment")
    put("Q4", "ok" if dseg in dim_ok else ("partial" if has("game_user_daily") else "skip"),
        "" if dseg in dim_ok else f"depth.segment「{dseg}」沒有對應欄位，只算整體")
    rtp_ok = has("game_user_daily", "win") and spec.get("target_rtp") and spec.get("sigma")
    trig_ok = bool(trig_cols) and bool(spec.get("triggers"))
    if rtp_ok and trig_ok:
        put("Q5", "ok")
    elif rtp_ok or trig_ok or has("game_user_daily", "win"):
        why = []
        if not has("game_user_daily", "win"):
            why.append("沒有 win 欄位")
        if not (spec.get("target_rtp") and spec.get("sigma")):
            why.append("spec.target_rtp／sigma 未填")
        if not trig_ok:
            why.append("沒有 trig_ 欄位或 spec.triggers")
        put("Q5", "partial", "；".join(why))
    else:
        put("Q5", "skip", "沒有 win 欄位，也沒有觸發次數")
    put("Q6", "ok" if has("erosion") else "skip", "" if has("erosion") else "缺 erosion.csv")
    put("H", "ok" if has("hours") else ("partial" if has("game_user_daily") else "skip"),
        "" if has("hours") else "缺 hours.csv：沒有時段分布，集中度與高強度照算")
    view_cols = [v.get("column") for v in cfg.get("views") or [] if v.get("column")]
    view_miss = [c for c in view_cols if c not in gcols]

    adapter_todo = []
    ap = C.adapter_path(cfg)
    if ap is not None:
        if ap.is_file():
            ad = C.yaml_load(ap)
            for grp in ("tables", "columns"):
                for k, v in (ad.get(grp) or {}).items():
                    if isinstance(v, str) and v.startswith("TODO"):
                        adapter_todo.append(f"{grp}.{k}：{v[5:].strip()}")
    return {"data_dir": str(dd), "datasets": ds, "bench_games": bench_dirs, "trigger_columns": trig_cols,
            "sections": sec, "view_columns_missing": view_miss, "adapter_todo": adapter_todo}


def main() -> None:
    ap = argparse.ArgumentParser(description="盤點可用數據 → capability.json")
    ap.add_argument("--config", required=True)
    a = ap.parse_args()
    cfg = C.load_config(a.config)
    res = probe(cfg)
    dd = C.data_dir(cfg)
    dd.mkdir(parents=True, exist_ok=True)
    (dd / "capability.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    if not res["datasets"]["game_user_daily"]["present"]:
        C.fail("GATE_BLOCKED", "沒有 game_user_daily.csv，無法產報告", "先跑 gr_run.py query，或把資料集放進 data_dir", res)
    summary = {k: v["status"] for k, v in res["sections"].items()}
    C.emit({"sections": summary, "detail": res["sections"], "adapter_todo": res["adapter_todo"],
            "view_columns_missing": res["view_columns_missing"], "capability": str(dd / "capability.json"),
            "next": f"gr_run.py build --config {a.config}"}, {"stage": "probe"})


if __name__ == "__main__":
    main()
