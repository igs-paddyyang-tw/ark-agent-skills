#!/usr/bin/env python3
"""vu_timeline — 低解析灰階抽幀 → motion energy / brightness / 直方圖距離 / ROI 序列 → motion_timeline.json。

用法:
  python vu_timeline.py --run artifacts/cva/<run_id> [--fps 4 --width 160 --crop x,y,w,h]
deterministic：同影片同參數輸出 bit-identical。
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

AUTO_ROI = {  # 以畫面比例表示 (x, y, w, h)
    "numeric_hud_bottom": (0.0, 0.85, 1.0, 0.15),
    "numeric_hud_top": (0.0, 0.0, 1.0, 0.12),
    "numeric_hud_center": (0.3, 0.3, 0.4, 0.4),
}


def read_frames(video: pathlib.Path, fps: int, width: int, crop: tuple | None):
    import numpy as np
    C.which("ffmpeg")
    meta = C.ffprobe(video)
    vf = []
    if crop:
        x, y, w, h = crop
        vf.append(f"crop=iw*{w}:ih*{h}:iw*{x}:ih*{y}")
    vf += [f"fps={fps}", f"scale={width}:-2", "format=gray"]
    cmd = ["ffmpeg", "-v", "error", "-i", str(video), "-vf", ",".join(vf), "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        C.fail("QUERY_FAILED", f"ffmpeg 抽幀失敗: {r.stderr.decode(errors='replace')[:200]}", "")
    # 高度由 scale=-2 決定：用 ffprobe 比例推算（取偶數）
    src_w, src_h = meta["width"], meta["height"]
    if crop:
        src_w, src_h = src_w * crop[2], src_h * crop[3]
    height = int(round(width * src_h / src_w / 2)) * 2
    n = len(r.stdout) // (width * height)
    if n == 0:
        C.fail("QUERY_FAILED", "抽不到任何幀", "影片可能損壞或時長為 0")
    arr = np.frombuffer(r.stdout[: n * width * height], dtype=np.uint8).reshape(n, height, width)
    return arr, meta


def compute(arr, fps: int, rois: dict) -> dict:
    import numpy as np
    f = arr.astype(np.float32) / 255.0
    n = f.shape[0]
    motion = np.zeros(n, dtype=np.float32)
    motion[1:] = np.abs(f[1:] - f[:-1]).mean(axis=(1, 2))
    brightness = f.mean(axis=(1, 2))
    hist = np.stack([np.histogram(x, bins=16, range=(0, 1))[0] for x in f]).astype(np.float32)
    hist /= hist.sum(axis=1, keepdims=True)
    hist_dist = np.zeros(n, dtype=np.float32)
    hist_dist[1:] = 0.5 * np.abs(hist[1:] - hist[:-1]).sum(axis=1)  # L1/2 ∈ [0,1]
    H, W = f.shape[1], f.shape[2]
    roi_series = {}
    for name, (x, y, w, h) in rois.items():
        sl = f[:, int(y * H): max(int(y * H) + 1, int((y + h) * H)), int(x * W): max(int(x * W) + 1, int((x + w) * W))]
        d = np.zeros(n, dtype=np.float32)
        d[1:] = np.abs(sl[1:] - sl[:-1]).mean(axis=(1, 2))
        roi_series[name] = {"rect": [x, y, w, h], "diff": [round(float(v), 5) for v in d]}
    return {"fps": fps, "n": int(n), "t": [round(i / fps, 3) for i in range(n)],
            "motion": [round(float(v), 5) for v in motion], "brightness": [round(float(v), 5) for v in brightness],
            "hist_dist": [round(float(v), 5) for v in hist_dist], "roi": roi_series}


def rois_from_pack(resolved: dict | None) -> dict:
    out = {}
    for d in (resolved or {}).get("extraction", {}).get("detectors", []):
        if d.get("use") == "roi_change":
            roi = d.get("roi", {})
            if "rect" in roi:
                out[roi.get("name", "roi")] = tuple(roi["rect"])
            elif roi.get("auto") in AUTO_ROI:
                out[roi.get("name", roi["auto"])] = AUTO_ROI[roi["auto"]]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="motion timeline")
    ap.add_argument("--run", required=True)
    ap.add_argument("--fps", type=int)
    ap.add_argument("--width", type=int)
    ap.add_argument("--crop", help="x,y,w,h（0-1 比例），裁掉實況主疊層")
    ap.add_argument("--roi", action="append", default=[], help="name=x,y,w,h 額外 ROI（可多個）")
    a = ap.parse_args()
    run = C.run_dir(a.run)
    m = C.load_manifest(run)
    resolved = json.loads((run / "pack" / "resolved.json").read_text(encoding="utf-8")) if (run / "pack" / "resolved.json").exists() else None
    tl_cfg = (resolved or {}).get("extraction", {}).get("timeline", {})
    fps = a.fps or int(tl_cfg.get("fps", 4))
    width = a.width or int(tl_cfg.get("width", 160))
    crop = tuple(float(x) for x in a.crop.split(",")) if a.crop else None
    rois = rois_from_pack(resolved)
    for spec in a.roi:
        name, rect = spec.split("=")
        rois[name] = tuple(float(x) for x in rect.split(","))
    try:
        import numpy  # noqa: F401
    except ImportError:
        C.fail("DRIVER_MISSING", "缺 numpy", "pip install numpy --break-system-packages")
    with C.Timer() as t:
        arr, _meta = read_frames(run / m["video"]["file"], fps, width, crop)
        tl = compute(arr, fps, rois)
        tl["crop"] = list(crop) if crop else None
        tl["width"] = width
    C.atomic_write(run / "frames" / "motion_timeline.json", json.dumps(tl, separators=(",", ":")))
    m = C.load_manifest(run)
    m["timeline"] = {"fps": fps, "width": width, "crop": tl["crop"], "rois": list(rois), "n": tl["n"]}
    C.save_manifest(run, m)
    C.stage_record(run, "timeline", t.elapsed_ms, n=tl["n"])
    C.emit({"n": tl["n"], "duration_s": round(tl["n"] / fps, 2), "rois": list(rois),
            "motion_mean": round(sum(tl["motion"]) / tl["n"], 5)}, {"stage": "timeline", "elapsed_ms": t.elapsed_ms})


if __name__ == "__main__":
    main()
