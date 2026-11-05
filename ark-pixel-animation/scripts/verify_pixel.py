#!/usr/bin/env python3
"""像素動畫驗收：逐秒截圖＋色盤／反鋸齒／決定性／靜止／放大／FPS 檢查。

用法::

    python3 verify_pixel.py anim.html [--out shots] [--step 1.0] [--scale 4]
    python3 verify_pixel.py http://127.0.0.1:28030/app --canvas "#office canvas" --scale 2   # 驗網頁（1.1）

頁面必須提供 ``window.__pixel = {W, H, FPS, DURATION, PAL, STATES, renderAt(t), pause(), pixels()}``
（範本見 ``assets/template-canvas.html``、``assets/template-pixi.html``）。

輸出 ``<out>/report.json``、``<out>/_contact_sheet.png``、逐張截圖，stdout 印摘要 JSON。
exit code：0 通過、1 有問題、2 環境缺件（playwright／Pillow／Chromium）。

Chromium 版本與 playwright 不合時，用 ``--chromium <執行檔>`` 或環境變數 ``ARK_PIXEL_CHROMIUM``
指定已安裝的 Chromium（例：``~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome``），不必重裝。

1.1 起（Pixel Office 實測回饋）：
- 目標可以是本機檔案或 ``http(s)://`` 網址（網址已有 query 時以 ``&`` 接上 ``t``／``scale``）
- viewport 預設依畫布大小自動放大到容得下（避免畫布超出視窗、被 sticky header 蓋住而誤判糊邊）；``--viewport WxH`` 可指定
- 畫布以 ``--canvas <CSS 選擇器>`` 指定（預設 ``canvas``）；頁面有多張 canvas 又沒指定時取第一張並在 ``warnings`` 提醒
- 注意：Playwright 截圖預設隱藏捲軸（``--hide-scrollbars``），本腳本只截畫布不受影響；自行截整頁驗捲軸時要關掉
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except ImportError as exc:  # pragma: no cover - 環境缺件
    print(
        f"缺少相依套件：{exc.name}。安裝：pip install playwright Pillow && "
        "python -m playwright install chromium（Chromium 已安裝則略過第二步）",
        file=sys.stderr,
    )
    sys.exit(2)

FPS_RANGE = (8, 12)


def hex2rgb(h: str) -> tuple[int, int, int]:
    """'#rrggbb' → (r, g, b)。"""
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def sample_times(duration: float, step: float, fps: int) -> list[float]:
    """取樣時間點：0, step, 2·step … 加上最後一格（檢查循環接縫）。"""
    times: list[float] = []
    t = 0.0
    while t < duration - 1e-6:
        times.append(round(t, 3))
        t += step
    last = round(duration - 1.0 / fps, 3)
    if last not in times:
        times.append(last)
    return times


def blurred_cells(img: Image.Image, scale: int) -> int:
    """回傳放大後「不是單色」的像素格數（偵測平滑放大）。"""
    sw, sh = img.size
    bad = 0
    for y in range(0, sh, scale):
        for x in range(0, sw, scale):
            c = img.getpixel((x, y))
            corners = ((dx, dy) for dx in (0, scale - 1) for dy in (0, scale - 1))
            if any(img.getpixel((x + dx, y + dy)) != c for dx, dy in corners):
                bad += 1
    return bad


def contact_sheet(frames: list[tuple[float, dict, Image.Image]], path: Path) -> None:
    """把各時間點截圖排成聯絡表（每列 4 張，標時間／格號／狀態）。"""
    cw, ch = frames[0][2].size
    cols_n = min(4, len(frames))
    rows_n = -(-len(frames) // cols_n)
    sheet = Image.new("RGB", (cols_n * (cw + 8) + 8, rows_n * (ch + 22) + 8), (20, 20, 28))
    d = ImageDraw.Draw(sheet)
    for i, (t, info, im) in enumerate(frames):
        x = 8 + (i % cols_n) * (cw + 8)
        y = 8 + (i // cols_n) * (ch + 22)
        sheet.paste(im, (x, y + 14))
        d.text((x, y), f"t={t}s f{info['frame']} {info['state']}", fill=(230, 230, 230))
    sheet.save(path)


def target_url(target: str | Path, scale: int) -> str:
    """本機檔案或網址 → 加上 t=0、scale 的網址。"""
    s = str(target)
    if s.startswith(("http://", "https://", "file://")):
        base = s
    else:
        base = Path(s).resolve().as_uri()
    return base + ("&" if "?" in base else "?") + f"t=0&scale={scale}"


def auto_viewport(w: int, h: int, scale: int) -> dict:
    """容得下放大後畫布的視窗（至少 1280×720，四周留邊給頁面標題列與側欄）。"""
    return {"width": max(1280, w * scale + 480), "height": max(720, h * scale + 360)}


def verify(html: str | Path, out: Path, step: float = 1.0, scale: int = 4, chromium: str | None = None,
           canvas: str = "canvas", viewport: tuple[int, int] | None = None) -> dict:
    """執行驗收並回傳摘要 dict（含 ok、problems、warnings、frames）。"""
    out.mkdir(parents=True, exist_ok=True)
    url = target_url(html, scale)
    problems: list[str] = []
    warnings: list[str] = []
    report: list[dict] = []
    frames: list[tuple[float, dict, Image.Image]] = []
    used: set[tuple[int, int, int]] = set()

    with sync_playwright() as p:
        exe = chromium or os.environ.get("ARK_PIXEL_CHROMIUM") or None
        browser = p.chromium.launch(executable_path=exe)
        pg = browser.new_page()
        errs: list[str] = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
        pg.goto(url)
        pg.wait_for_function("window.__pixel !== undefined", timeout=15000)
        meta = pg.evaluate("({W:__pixel.W,H:__pixel.H,FPS:__pixel.FPS,D:__pixel.DURATION,PAL:__pixel.PAL})")
        w, h, dur, fps = meta["W"], meta["H"], meta["D"], meta["FPS"]
        vp = {"width": viewport[0], "height": viewport[1]} if viewport else auto_viewport(w, h, scale)
        if vp != pg.viewport_size:
            pg.set_viewport_size(vp)
            pg.wait_for_timeout(200)                  # 讓頁面依新尺寸重新排版
        pal = {hex2rgb(c) for c in meta["PAL"]}
        pg.evaluate("__pixel.pause()")
        if not FPS_RANGE[0] <= fps <= FPS_RANGE[1]:
            problems.append(f"FPS={fps} 不在 {FPS_RANGE[0]}–{FPS_RANGE[1]}")

        times = sample_times(dur, step, fps)
        prev = None
        for t in times:
            info = pg.evaluate(f"__pixel.renderAt({t})")
            px = pg.evaluate("__pixel.pixels()")
            img = Image.frombytes("RGBA", (w, h), bytes(px)).convert("RGB")
            cols = {c for _, c in img.getcolors(w * h)}
            used |= cols
            bad = cols - pal
            if bad:
                problems.append(f"t={t}s 出現色盤外顏色 {len(bad)} 種（反鋸齒/漸層/半透明？）例 {sorted(bad)[:3]}")
            again = pg.evaluate(f"(__pixel.renderAt({t}), __pixel.pixels())")
            if again != px:
                problems.append(f"t={t}s 同一時間渲染兩次結果不同（用了 Math.random / Date？）")
            if prev is not None and px == prev:
                problems.append(f"t={t}s 與上一張截圖完全相同（動作停滯？）")
            prev = px
            big = img.resize((w * scale, h * scale), Image.NEAREST)
            f = out / f"t{t:05.2f}_{info['state']}.png"
            big.save(f)
            frames.append((t, info, big))
            report.append({"t": t, "frame": info["frame"], "state": info["state"], "colors": len(cols), "file": str(f)})

        # 放大一致性：截實際畫面，每個 scale×scale 區塊須為單色
        pg.evaluate(f"__pixel.renderAt({times[len(times) // 2]})")
        shot = out / "_screen.png"
        loc = pg.locator(canvas)
        n = loc.count()
        if n == 0:
            raise RuntimeError(f"找不到畫布：{canvas}")
        if n > 1:
            warnings.append(f"「{canvas}」對到 {n} 張 canvas，取第一張；請用 --canvas 指定")
            loc = loc.first
        loc.scroll_into_view_if_needed()
        loc.screenshot(path=str(shot))
        s = Image.open(shot).convert("RGB")
        if s.size != (w * scale, h * scale):
            problems.append(f"畫面尺寸 {s.size[0]}x{s.size[1]} ≠ {w * scale}x{h * scale}（非整數倍放大？）")
        else:
            blur = blurred_cells(s, scale)
            if blur:
                problems.append(f"放大後有 {blur} 個像素格不是單色（image-rendering / imageSmoothing 沒關？）")
        if errs:
            problems.append("Console 錯誤: " + " | ".join(errs[:5]))
        browser.close()

    if len(used) > len(pal):
        problems.append("使用顏色數超過色盤")
    contact_sheet(frames, out / "_contact_sheet.png")
    summary = {
        "ok": not problems, "canvas": f"{w}x{h}", "fps": fps, "duration": dur,
        "palette": len(pal), "colors_used": len(used), "problems": problems, "warnings": warnings, "frames": report,
    }
    (out / "report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    """CLI 入口。"""
    ap = argparse.ArgumentParser(description="像素動畫驗收（需頁面提供 window.__pixel）")
    ap.add_argument("html", help="本機 HTML 檔或 http(s):// 網址")
    ap.add_argument("--out", type=Path, default=Path("shots"))
    ap.add_argument("--step", type=float, default=1.0, help="取樣間隔秒數（測試版建議 0.5）")
    ap.add_argument("--scale", type=int, default=4, help="截圖放大倍率")
    ap.add_argument("--chromium", help="指定 Chromium 執行檔（預設用 playwright 自帶）")
    ap.add_argument("--canvas", default="canvas", help="畫布的 CSS 選擇器（頁面有多張 canvas 時指定）")
    ap.add_argument("--viewport", help="視窗大小 WxH，例 1600x1000（預設自動容得下放大後的畫布）")
    a = ap.parse_args(argv)
    vp = tuple(int(v) for v in a.viewport.lower().split("x")) if a.viewport else None
    try:
        summary = verify(a.html, a.out, a.step, a.scale, a.chromium, a.canvas, vp)
    except PlaywrightError as exc:
        if "Executable doesn't exist" in str(exc):
            print("找不到 Chromium：執行 python -m playwright install chromium，"
                  "或用 --chromium／ARK_PIXEL_CHROMIUM 指定已安裝的版本", file=sys.stderr)
            return 2
        raise
    print(json.dumps({k: v for k, v in summary.items() if k != "frames"}, ensure_ascii=False, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
