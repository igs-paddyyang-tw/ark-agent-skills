#!/usr/bin/env python3
"""oob_layout — 讀 cpp_trace 編出來的 trial.bin（g++ -m32 -O2 版面），取某個靜態陣列「越界後」的值，給 quirk_oob_odds 之類的鍵用。

GHY 系 C++ 常讓特殊符號（FF、SP、JP、RB）用超出賠率表的列號查 odds，g++ 下讀到的是緊接在後面的靜態陣列（多半是線表）。
不要手抄：用符號位址＋objdump 程式化取得。

用法：python3 oob_layout.py <trial.bin> --sym <符號名的正規式，例 'uwconCheckGTOddsInfo$'> --rows 12,13,14 --cols 5 --width 4
  --width：元素位元組數（Type.h 的 UWORD 可能是 2 或 4；看 Type.h 的 typedef）
  --cols ：每列元素數（賠率表的欄數）
輸出：JSON [[…cols], …]（每個 --rows 一列），另印出緊接在後的符號名稱到 stderr，方便確認讀到的是哪個陣列。
（蒸餾自 W2 shu-lai-bao／crazy-wheel／diamond-billionaire）
"""
import argparse, json, re, subprocess, sys

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("exe"); ap.add_argument("--sym", required=True)
ap.add_argument("--rows", required=True); ap.add_argument("--cols", type=int, default=5); ap.add_argument("--width", type=int, default=2, choices=(1, 2, 4))
a = ap.parse_args()
nm = subprocess.run(["nm", "-C", "-n", a.exe], capture_output=True, text=True).stdout.splitlines()
hits = [(i, l) for i, l in enumerate(nm) if re.search(a.sym, l)]
if len(hits) != 1:
    sys.exit(f"--sym 要剛好對到 1 個符號，實際 {len(hits)} 個：{[l for _, l in hits][:5]}")
idx, line = hits[0]
base = int(line.split()[0], 16)
if idx + 1 < len(nm):
    print("下一個符號：", nm[idx + 1], file=sys.stderr)
mem = {}
for sec in (".rodata", ".data"):
    for l in subprocess.run(["objdump", "-s", "-j", sec, a.exe], capture_output=True, text=True).stdout.splitlines():
        m = re.match(r"\s*([0-9a-f]{4,8}) ((?:[0-9a-f]{2,8} ){1,4})", l)
        if m:
            addr, hx = int(m.group(1), 16), m.group(2).replace(" ", "")
            for i in range(0, len(hx), 2):
                mem[addr + i // 2] = int(hx[i:i + 2], 16)
w = lambda i: int.from_bytes(bytes(mem.get(base + a.width * i + j, 0) for j in range(a.width)), "little")
print(json.dumps([[w(r * a.cols + k) for k in range(a.cols)] for r in map(int, a.rows.split(","))]))
