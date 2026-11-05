#!/usr/bin/env python3
"""角色 sprite sheet 驗收（112×96 = 3 方向 × 7 格 × 16×32）。只需 Pillow，不需瀏覽器。

用法::

    python3 verify_sheet.py characters/char_cto-agent.png [more.png …] [--out contact/]

manifest（同目錄 `<slug>.json`，`char_` 前綴去掉）存在時一併檢查色盤。

| # | 檢查 | 失敗代表 |
|---|---|---|
| 1 | 尺寸 112×96 | 版型錯 |
| 2 | alpha 只有 0／255 | 半透明邊（反鋸齒、縮放糊邊） |
| 3 | 不跨格：相鄰兩格的交界兩側不能同時有不透明像素 | 圖案溢出到隔壁格 |
| 4 | 每格非空，且最低的不透明列在第 31 列（腳底對齊） | 角色浮空或被切腳 |
| 5 | 顏色都在 manifest 色盤內 | 色盤外顏色 |
| 6 | 走路第 0 格與第 2 格的腳部水平位移 ≤ 2px | 循環接縫跳動 |
| 7 | 打字 3≠4、閱讀 5≠6 | 動作沒有變化 |
| 8 | 輸出 contact sheet（6 倍、標方向與格號） | — |

exit code：0 通過、1 有問題、2 檔案讀不到／缺 Pillow。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    print("缺少 Pillow：pip install Pillow", file=sys.stderr)
    sys.exit(2)

FW, FH, COLS, ROWS = 16, 32, 7, ("down", "up", "right")
W, H = FW * COLS, FH * len(ROWS)
FRAME_NAME = {0: "走路0", 1: "走路1", 2: "走路2", 3: "打字3", 4: "打字4", 5: "閱讀5", 6: "閱讀6"}


def where(r: int, c: int) -> str:
    return f"（{ROWS[r]}，{FRAME_NAME[c]}）"


def hex2rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def find_manifest(png: Path) -> Path | None:
    stem = png.stem[5:] if png.stem.startswith("char_") else png.stem
    m = png.with_name(stem + ".json")
    return m if m.exists() else None


def check(png: Path, out: Path | None = None) -> dict:
    """回傳 {ok, problems, file, contact}。"""
    problems: list[str] = []
    img = Image.open(png).convert("RGBA")
    if img.size != (W, H):
        return {"ok": False, "file": str(png), "problems": [f"① 尺寸 {img.size[0]}×{img.size[1]} ≠ {W}×{H}（版型：3 方向 × 7 格 × 16×32）"], "contact": None}
    px = img.load()
    opaque = lambda x, y: px[x, y][3] > 0  # noqa: E731

    # ② alpha 只能 0／255
    semi = [(x, y) for y in range(H) for x in range(W) if 0 < px[x, y][3] < 255]
    if semi:
        x, y = semi[0]
        problems.append(f"② 有 {len(semi)} 個半透明像素，例如 {where(y // FH, x // FW)} 格內 ({x % FW},{y % FH}) alpha={px[x, y][3]}"
                        " → 關閉平滑／不要縮放，背景只用完全透明")

    # ③ 不跨格
    bleed = []
    for c in range(1, COLS):                       # 直的交界
        x = c * FW
        for y in range(H):
            if opaque(x - 1, y) and opaque(x, y):
                bleed.append((y // FH, c - 1, c))
                break
    for r in range(1, len(ROWS)):                  # 橫的交界
        y = r * FH
        for x in range(W):
            if opaque(x, y - 1) and opaque(x, y):
                bleed.append((r - 1, x // FW, None))
                break
    for r, c, c2 in bleed:
        problems.append(f"③ 圖案跨格：{where(r, c)} 與{'右邊一格' if c2 is not None else '下一列同格'}在交界處相連 → 角色要完整畫在 16×32 格內")

    # ④ 每格非空、腳底在第 31 列
    for r in range(len(ROWS)):
        for c in range(COLS):
            ox, oy = c * FW, r * FH
            rows_with = [y for y in range(FH) if any(opaque(ox + x, oy + y) for x in range(FW))]
            if not rows_with:
                problems.append(f"④ {where(r, c)} 是空的 → 每格都要有角色")
            elif rows_with[-1] != FH - 1:
                problems.append(f"④ {where(r, c)} 最低的不透明列是第 {rows_with[-1]} 列，不是第 31 列 → 腳底要貼齊格子底部")

    # ⑤ 色盤
    man = find_manifest(png)
    if man:
        pal = {hex2rgb(h) for h in json.loads(man.read_text(encoding="utf-8")).get("palette", [])}
        off: dict[tuple, tuple] = {}
        for y in range(H):
            for x in range(W):
                p = px[x, y]
                if p[3] == 255 and p[:3] not in pal:
                    off.setdefault(p[:3], (y // FH, x // FW))
        for rgb, (r, c) in list(off.items())[:3]:
            problems.append(f"⑤ 色盤外顏色 #{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}，出現在 {where(r, c)} → 只用 manifest 的 palette")
        if len(off) > 3:
            problems.append(f"⑤ 另有 {len(off) - 3} 種色盤外顏色")

    # ⑥ 走路循環接縫：第 0、2 格腳部（第 28–31 列）的左右邊界位移
    for r in range(len(ROWS)):
        def feet_span(c: int):
            xs = [x for y in range(28, 32) for x in range(FW) if opaque(c * FW + x, r * FH + y)]
            return (min(xs), max(xs)) if xs else None
        a, b = feet_span(0), feet_span(2)
        if a and b and max(abs(a[0] - b[0]), abs(a[1] - b[1])) > 2:
            problems.append(f"⑥ {ROWS[r]} 走路第 0 格與第 2 格腳部位移 {max(abs(a[0] - b[0]), abs(a[1] - b[1]))}px（> 2）→ 循環會跳，縮小步幅")

    # ⑦ 動作要有變化
    def cell_bytes(r: int, c: int) -> bytes:
        return img.crop((c * FW, r * FH, c * FW + FW, r * FH + FH)).tobytes()
    for r in range(len(ROWS)):
        if cell_bytes(r, 3) == cell_bytes(r, 4):
            problems.append(f"⑦ {ROWS[r]} 打字 3、4 兩格完全相同 → 手要上下交替")
        if r != 1 and cell_bytes(r, 5) == cell_bytes(r, 6):       # 背面看不到文件，閱讀兩格可相同
            problems.append(f"⑦ {ROWS[r]} 閱讀 5、6 兩格完全相同 → 文件要有起伏")

    # ⑧ contact sheet
    contact = None
    if out is not None:
        out.mkdir(parents=True, exist_ok=True)
        s, pad, lab = 6, 6, 14
        cw, ch = FW * s, FH * s
        sheet = Image.new("RGB", (COLS * (cw + pad) + pad, len(ROWS) * (ch + pad + lab) + pad), (11, 11, 16))
        d = ImageDraw.Draw(sheet)
        for r in range(len(ROWS)):
            for c in range(COLS):
                x0, y0 = pad + c * (cw + pad), pad + r * (ch + pad + lab)
                for ty in range(0, ch, 12):                     # 棋盤底：看得出透明
                    for tx in range(0, cw, 12):
                        d.rectangle([x0 + tx, y0 + lab + ty, x0 + tx + 11, y0 + lab + ty + 11],
                                    fill=(32, 35, 47) if (tx // 12 + ty // 12) % 2 else (23, 26, 36))
                cell = img.crop((c * FW, r * FH, c * FW + FW, r * FH + FH)).resize((cw, ch), Image.NEAREST)
                sheet.paste(cell, (x0, y0 + lab), cell)
                d.text((x0, y0), f"{ROWS[r]} {c}", fill=(201, 204, 214))
        contact = out / f"{png.stem}_contact.png"
        sheet.save(contact)

    return {"ok": not problems, "file": str(png), "manifest": str(man) if man else None, "problems": problems,
            "contact": str(contact) if contact else None}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="角色 sprite sheet 驗收（112×96）")
    ap.add_argument("png", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, help="contact sheet 輸出目錄")
    a = ap.parse_args(argv)
    results = []
    for p in a.png:
        if not p.is_file():
            print(f"找不到檔案：{p}", file=sys.stderr)
            return 2
        results.append(check(p, a.out))
    ok = all(r["ok"] for r in results)
    print(json.dumps({"ok": ok, "results": results}, ensure_ascii=False, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
