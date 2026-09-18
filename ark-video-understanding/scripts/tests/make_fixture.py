#!/usr/bin/env python3
"""合成測試影片：已知事件時間點（停輪 / 轉場 / 閃光），供偵測器召回與 determinism 測試。

python make_fixture.py --out /tmp/fx_slot.mp4 --kind slot
kind=slot: 5 次 spin（各 1.5 s 快速變化 + 3.5 s 靜止），t=26 轉場，t=28 閃光。
kind=fast: 6 個回合（下注靜止 3 s → 進行 2 s → 結果靜止 2 s）。
"""
import argparse
import json
import subprocess

import numpy as np

W, H, FPS = 640, 360, 10


def slot_frames(rng):
    events = {"settle": [], "scene": [], "flash": []}
    frames = []
    dur = 30
    tiles = rng.integers(0, 255, size=(3, 3, 3))
    bg = np.array([20, 30, 60], dtype=np.uint8)
    spin_starts = [2, 7, 12, 17, 22]
    hud = 0
    for i in range(dur * FPS):
        t = i / FPS
        if t >= 26:
            bg = np.array([90, 20, 20], dtype=np.uint8)
        f = np.zeros((H, W, 3), dtype=np.uint8) + bg
        spinning = any(s <= t < s + 1.5 for s in spin_starts)
        for s in spin_starts:
            if abs(t - (s + 1.5)) < 1e-6:
                events["settle"].append(round(s + 1.5, 2)); hud += 1
        if spinning:
            tiles = rng.integers(0, 255, size=(3, 3, 3))
        for r in range(3):
            for c in range(3):
                x0, y0 = 120 + c * 140, 30 + r * 90
                f[y0:y0 + 80, x0:x0 + 120] = tiles[r, c]
        # HUD 數字區（底部）
        f[320:350, 200:200 + 30 * (hud + 1)] = 240
        if 28.0 <= t < 28.4:
            f[:] = 255
            if abs(t - 28.0) < 1e-6:
                events["flash"].append(28.0)
        frames.append(f)
    events["scene"].append(26.0)
    return frames, events


def fast_frames(rng):
    events = {"hold_start": [], "settle": []}
    frames = []
    t = 0.0
    bg = np.array([15, 15, 15], dtype=np.uint8)
    while t < 42:
        # betting hold 3 s
        events["hold_start"].append(round(t, 2))
        for _ in range(3 * FPS):
            f = np.zeros((H, W, 3), dtype=np.uint8) + bg; f[100:260, 220:420] = 80; frames.append(f)
        t += 3
        # play 2 s (curve moving)
        for k in range(2 * FPS):
            f = np.zeros((H, W, 3), dtype=np.uint8) + bg
            f[100:260, 220:420] = 80
            x = 40 + int(k * 25)
            f[max(0, 300 - k * 12):300, 40:min(W, x)] = 200
            f[:, :] = np.where(rng.random((H, W, 1)) < 0.02, 255, f)  # noise to raise motion
            frames.append(f)
        t += 2
        events["settle"].append(round(t, 2))
        for _ in range(2 * FPS):
            f = np.zeros((H, W, 3), dtype=np.uint8) + bg; f[100:260, 220:420] = 160; frames.append(f)
        t += 2
    return frames, events


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--kind", default="slot")
    a = ap.parse_args()
    rng = np.random.default_rng(7)
    frames, events = slot_frames(rng) if a.kind == "slot" else fast_frames(rng)
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                          "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", a.out], stdin=subprocess.PIPE)
    for f in frames:
        p.stdin.write(f.tobytes())
    p.stdin.close(); p.wait()
    with open(a.out + ".events.json", "w") as fh:
        json.dump(events, fh)
    print(json.dumps({"out": a.out, "events": events}))


if __name__ == "__main__":
    main()
