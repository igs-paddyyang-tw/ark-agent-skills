#!/usr/bin/env python3
"""vu_keyframes — events → 原解析度幀（ffmpeg 精準 seek）→ dHash 去重 → 預算 → frames/keyframes/ + keyframes.json。

用法:
  python vu_keyframes.py --run artifacts/cva/<run_id> [--max-keyframes N] [--t-range 60,300]
預算：pack budget.max_keyframes 為預設；CLI 可覆寫但不可超過 core hard_max（→ BUDGET_EXCEEDED）。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vu_common as C  # noqa: E402

PRIORITY_LOW = {"fallback", "scene", "periodic"}


def dhash(img, size: int = 12) -> int:
    """色彩感知 dHash：R/G/B 三通道各 size×size 差分 → 3·size² bits（灰階 dHash 會把換色轉場當重複）。"""
    bits = 0
    for ch in img.convert("RGB").split():
        g = ch.resize((size + 1, size))
        px = list(g.getdata())
        for r in range(size):
            for c in range(size):
                bits = (bits << 1) | (1 if px[r * (size + 1) + c] > px[r * (size + 1) + c + 1] else 0)
    return bits


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def extract(video: pathlib.Path, t: float, dst: pathlib.Path) -> bool:
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", "-q:v", "2", str(dst)],
                       capture_output=True)
    return r.returncode == 0 and dst.exists()


def main() -> None:
    ap = argparse.ArgumentParser(description="extract keyframes")
    ap.add_argument("--run", required=True)
    ap.add_argument("--max-keyframes", type=int)
    ap.add_argument("--hamming", type=int, default=16, help="色彩 dHash(3×12×12=432bit) 距離 ≤ 此值視為重複")
    ap.add_argument("--t-range", help="start,end 秒，只處理此區間")
    ap.add_argument("--core-only", action="store_true", help="detect 模式：最多 27 幀（3 張 sheet）寫到 frames/detect/")
    a = ap.parse_args()
    try:
        from PIL import Image
    except ImportError:
        C.fail("DRIVER_MISSING", "缺 Pillow", "pip install Pillow --break-system-packages")
    run = C.run_dir(a.run)
    m = C.load_manifest(run)
    ev_path = run / "frames" / "events.json"
    if not ev_path.exists():
        C.fail("BAD_INPUT", "缺 events.json", "先跑 vu_events.py")
    ev = json.loads(ev_path.read_text(encoding="utf-8"))
    if a.core_only:
        budget, hard_max, sub = 27, 27, "detect"
    else:
        resolved = C.load_resolved(run)
        b = resolved["extraction"]["budget"]
        budget = a.max_keyframes or int(b.get("max_keyframes", 150))
        hard_max = int(b.get("hard_max", {}).get("max_keyframes", 400))
        sub = "keyframes"
        if budget > hard_max:
            C.fail("BUDGET_EXCEEDED", f"--max-keyframes {budget} 超過 pack hard_max {hard_max}", "縮小 --t-range 或分段跑")
    events = ev["events"]
    if a.t_range:
        lo, hi = (float(x) for x in a.t_range.split(","))
        events = [e for e in events if lo <= e["t"] <= hi]
    # 同一時間點多個事件合併（保留最高優先 label）
    merged: dict[float, dict] = {}
    for e in events:
        key = round(e["t"] * 2) / 2  # 0.5 s 桶
        cur = merged.get(key)
        if cur is None or (cur["label"] in PRIORITY_LOW and e["label"] not in PRIORITY_LOW):
            merged[key] = e
    cands = sorted(merged.values(), key=lambda e: e["t"])
    video = run / m["video"]["file"]
    out_dir = run / "frames" / sub
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.jpg"):
        old.unlink()
    kept, dropped_dup, failed = [], 0, 0
    with C.Timer() as t:
        for e in cands:
            tmp = out_dir / ".tmp.jpg"
            if not extract(video, e["t"], tmp):
                failed += 1
                continue
            with Image.open(tmp) as im:
                h = dhash(im)
            dup = next((k for k in kept if hamming(h, int(k["hash"], 16)) <= a.hamming), None)
            if dup is not None:
                if e["label"] not in PRIORITY_LOW and dup["label"] in PRIORITY_LOW:
                    pathlib.Path(dup["_tmp"]).unlink()  # 主事件取代兜底幀
                    kept.remove(dup)
                else:
                    dropped_dup += 1
                    tmp.unlink()
                    continue
            kept.append({**e, "hash": f"{h:0108x}", "_tmp": str(tmp.rename(out_dir / f".k{e['t']:09.3f}.jpg"))})
        budget_applied = False
        if len(kept) > budget:
            budget_applied = True
            prim = [k for k in kept if k["label"] not in PRIORITY_LOW]
            low = [k for k in kept if k["label"] in PRIORITY_LOW]
            if len(prim) >= budget:
                step = len(prim) / budget
                prim = [prim[int(i * step)] for i in range(budget)]
                low = []
            else:
                room = budget - len(prim)
                step = len(low) / room if room else 1
                low = [low[int(i * step)] for i in range(room)] if room else []
            keep_ids = {id(k) for k in prim + low}
            for k in kept:
                if id(k) not in keep_ids:
                    pathlib.Path(k["_tmp"]).unlink()
            kept = sorted(prim + low, key=lambda k: k["t"])
        final = []
        for i, k in enumerate(kept):
            name = f"{i:04d}_{C.ts_slug(k['t'])}_{k['label']}.jpg"
            pathlib.Path(k["_tmp"]).rename(out_dir / name)
            final.append({"idx": i, "t": k["t"], "ts": C.fmt_ts(k["t"]), "label": k["label"], "detector": k["detector"],
                          "score": k["score"], "hash": k["hash"], "file": f"frames/{sub}/{name}", "extra": k.get("extra", {})})
    C.atomic_write(run / "frames" / f"{sub}.json", json.dumps({"keyframes": final, "budget": budget, "budget_applied": budget_applied,
                                                                 "dropped_duplicates": dropped_dup, "extract_failed": failed}, ensure_ascii=False))
    mm = C.load_manifest(run)
    mm.setdefault("budget_used", {})[f"{sub}_count"] = len(final)
    C.save_manifest(run, mm)
    C.stage_record(run, sub, t.elapsed_ms, count=len(final), budget_applied=budget_applied)
    by = {}
    for k in final:
        by[k["label"]] = by.get(k["label"], 0) + 1
    C.emit({"count": len(final), "by_label": by, "dropped_duplicates": dropped_dup, "budget": budget,
            "budget_applied": budget_applied, "dir": f"frames/{sub}"}, {"stage": sub, "elapsed_ms": t.elapsed_ms})


if __name__ == "__main__":
    main()
