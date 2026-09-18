#!/usr/bin/env python3
"""vu_sheets — keyframes → contact sheet（3×3、燒錄時間碼）→ frames/sheets/ + sheets.json。

用法:
  python vu_sheets.py --run artifacts/cva/<run_id> [--grid 3x3 --cell-width 480] [--core-only]
多模態模型看 sheet 而非單幀：token 降一個量級，時間順序內建。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vu_common as C  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="build contact sheets")
    ap.add_argument("--run", required=True)
    ap.add_argument("--grid")
    ap.add_argument("--cell-width", type=int)
    ap.add_argument("--max-sheets", type=int)
    ap.add_argument("--core-only", action="store_true")
    a = ap.parse_args()
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        C.fail("DRIVER_MISSING", "缺 Pillow", "pip install Pillow --break-system-packages")
    run = C.run_dir(a.run)
    sub = "detect" if a.core_only else "keyframes"
    kf_path = run / "frames" / f"{sub}.json"
    if not kf_path.exists():
        C.fail("BAD_INPUT", f"缺 frames/{sub}.json", "先跑 vu_keyframes.py")
    kfs = json.loads(kf_path.read_text(encoding="utf-8"))["keyframes"]
    if a.core_only:
        grid, cw, max_sheets, hard = "3x3", 480, 3, 3
    else:
        resolved = C.load_resolved(run)
        sc, b = resolved["extraction"].get("sheet", {}), resolved["extraction"]["budget"]
        grid = a.grid or sc.get("grid", "3x3")
        cw = a.cell_width or int(sc.get("cell_width", 480))
        max_sheets = a.max_sheets or int(b.get("max_sheets", 20))
        hard = int(b.get("hard_max", {}).get("max_sheets", 60))
        if max_sheets > hard:
            C.fail("BUDGET_EXCEEDED", f"--max-sheets {max_sheets} 超過 hard_max {hard}", "")
    cols, rows = (int(x) for x in grid.lower().split("x"))
    per = cols * rows
    out_dir = run / "frames" / ("detect_sheets" if a.core_only else "sheets")
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.jpg"):
        old.unlink()
    sheets, truncated = [], False
    with C.Timer() as t:
        chunks = [kfs[i:i + per] for i in range(0, len(kfs), per)]
        if len(chunks) > max_sheets:
            truncated = True
            step = len(chunks) / max_sheets
            chunks = [chunks[int(i * step)] for i in range(max_sheets)]
        for si, chunk in enumerate(chunks, 1):
            first = Image.open(run / chunk[0]["file"])
            ch = int(cw * first.height / first.width)
            first.close()
            sheet = Image.new("RGB", (cols * cw, rows * ch), (18, 18, 18))
            draw = ImageDraw.Draw(sheet)
            cells = []
            for ci, k in enumerate(chunk):
                with Image.open(run / k["file"]) as im:
                    im = im.convert("RGB").resize((cw, ch))
                    x, y = (ci % cols) * cw, (ci // cols) * ch
                    sheet.paste(im, (x, y))
                label = f"[{ci + 1}] {k['ts']}  {k['label']}"
                tw = max(8 * len(label), 60)
                draw.rectangle([x + 4, y + ch - 22, x + 4 + tw, y + ch - 4], fill=(0, 0, 0))
                draw.text((x + 8, y + ch - 20), label, fill=(255, 230, 0))
                cells.append({"cell": ci + 1, "keyframe_idx": k["idx"], "t": k["t"], "ts": k["ts"], "label": k["label"], "file": k["file"]})
            name = f"sheet-{si:03d}.jpg"
            sheet.save(out_dir / name, quality=88)
            sheets.append({"sheet": si, "file": f"frames/{out_dir.name}/{name}", "grid": grid, "cells": cells,
                           "t_start": chunk[0]["t"], "t_end": chunk[-1]["t"]})
    C.atomic_write(run / "frames" / ("detect_sheets.json" if a.core_only else "sheets.json"),
                   json.dumps({"sheets": sheets, "truncated": truncated, "max_sheets": max_sheets}, ensure_ascii=False))
    mm = C.load_manifest(run)
    mm.setdefault("budget_used", {})[f"{out_dir.name}_count"] = len(sheets)
    C.save_manifest(run, mm)
    C.stage_record(run, out_dir.name, t.elapsed_ms, count=len(sheets), truncated=truncated)
    C.emit({"count": len(sheets), "truncated": truncated, "dir": f"frames/{out_dir.name}"}, {"stage": out_dir.name, "elapsed_ms": t.elapsed_ms})


if __name__ == "__main__":
    main()
