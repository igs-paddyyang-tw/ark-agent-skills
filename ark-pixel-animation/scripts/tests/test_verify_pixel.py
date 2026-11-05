"""verify_pixel.py 的正例與反證。

需要 playwright＋Pillow＋可啟動的 Chromium；缺件時整檔 skip（不假綠：skip 會顯示在報告）。
Chromium 版本與 playwright 不合時設 ``ARK_PIXEL_CHROMIUM`` 指向已安裝的執行檔。
PixiJS 範本需要連 jsDelivr，離線時設 ``ARK_PIXEL_OFFLINE=1`` 跳過該案例。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
pytest.importorskip("PIL")

SKILL = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILL / "scripts"))
import verify_pixel  # noqa: E402

CANVAS = SKILL / "assets" / "template-canvas.html"
PIXI = SKILL / "assets" / "template-pixi.html"


def _chromium_ok() -> bool:
    """確認 Chromium 能啟動，否則整檔 skip。"""
    from playwright.sync_api import Error, sync_playwright

    try:
        with sync_playwright() as p:
            p.chromium.launch(executable_path=os.environ.get("ARK_PIXEL_CHROMIUM") or None).close()
        return True
    except Error:
        return False


pytestmark = pytest.mark.skipif(not _chromium_ok(), reason="Chromium 無法啟動")


def _mutate(tmp_path: Path, old: str, new: str) -> Path:
    """複製 Canvas 範本並做一處替換，產生壞樣本。"""
    src = CANVAS.read_text(encoding="utf-8")
    assert src.count(old) == 1, old
    out = tmp_path / "bad.html"
    out.write_text(src.replace(old, new), encoding="utf-8")
    return out


def test_canvas_template_passes(tmp_path: Path) -> None:
    r = verify_pixel.verify(CANVAS, tmp_path / "shots", step=0.5)
    assert r["ok"], r["problems"]
    assert (tmp_path / "shots" / "_contact_sheet.png").exists()


@pytest.mark.skipif(os.environ.get("ARK_PIXEL_OFFLINE") == "1", reason="離線：PixiJS 需 CDN")
def test_pixi_template_passes(tmp_path: Path) -> None:
    r = verify_pixel.verify(PIXI, tmp_path / "shots", step=0.5)
    assert r["ok"], r["problems"]


def test_global_alpha_is_rejected(tmp_path: Path) -> None:
    bad = _mutate(tmp_path, "function drawBG(f){\n", "function drawBG(f){\n  ctx.globalAlpha = 0.6;\n")
    r = verify_pixel.verify(bad, tmp_path / "shots", step=0.5)
    assert not r["ok"]
    assert any("色盤外顏色" in p for p in r["problems"])


def test_math_random_is_rejected(tmp_path: Path) -> None:
    bad = _mutate(tmp_path, "const tip = drawWizard(40, 54, st, f);",
                  "const tip = drawWizard(40 + Math.floor(Math.random() * 4), 54, st, f);")
    r = verify_pixel.verify(bad, tmp_path / "shots", step=0.5)
    assert not r["ok"]
    assert any("渲染兩次結果不同" in p for p in r["problems"])


def test_smooth_scaling_is_rejected(tmp_path: Path) -> None:
    bad = _mutate(tmp_path, "canvas{image-rendering:pixelated;image-rendering:crisp-edges;display:block}",
                  "canvas{display:block}")
    r = verify_pixel.verify(bad, tmp_path / "shots", step=0.5)
    assert not r["ok"]
    assert any("不是單色" in p for p in r["problems"])


def test_fps_out_of_range_is_rejected(tmp_path: Path) -> None:
    bad = _mutate(tmp_path, "const FPS = 10; ", "const FPS = 24; ")
    r = verify_pixel.verify(bad, tmp_path / "shots", step=0.5)
    assert not r["ok"]
    assert any("FPS=24" in p for p in r["problems"])


def test_sample_times_includes_loop_seam() -> None:
    assert verify_pixel.sample_times(2, 0.5, 10) == [0.0, 0.5, 1.0, 1.5, 1.9]


# ── 1.1：網址、viewport、canvas 選擇器（Pixel Office 實測回饋）──────────────────
def test_target_url_file_and_http():
    assert verify_pixel.target_url("http://h/app", 2) == "http://h/app?t=0&scale=2"
    assert verify_pixel.target_url("http://h/app?demo=1", 3) == "http://h/app?demo=1&t=0&scale=3"
    assert verify_pixel.target_url(CANVAS, 4).startswith("file://") and verify_pixel.target_url(CANVAS, 4).endswith("?t=0&scale=4")


def test_auto_viewport_fits_scaled_canvas():
    vp = verify_pixel.auto_viewport(384, 224, 3)
    assert vp["width"] >= 384 * 3 and vp["height"] >= 224 * 3 + 200


def test_http_url_target(tmp_path: Path) -> None:
    """以 http:// 網址驗收（本機起一個靜態伺服器）。"""
    import functools
    import http.server
    import threading
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(CANVAS.parent))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{srv.server_address[1]}/{CANVAS.name}"
        r = verify_pixel.verify(url, tmp_path / "shots", step=0.5, scale=6)    # 6 倍＝960×540，靠自動 viewport 容下
        assert r["ok"], r["problems"]
    finally:
        srv.shutdown()


def test_multiple_canvases_warn_and_selector(tmp_path: Path) -> None:
    src = CANVAS.read_text(encoding="utf-8")
    page = tmp_path / "two.html"
    page.write_text(src.replace('<body><canvas id="c"></canvas>', '<body><canvas id="other" width="4" height="4"></canvas><canvas id="c"></canvas>'), encoding="utf-8")
    r = verify_pixel.verify(page, tmp_path / "a", step=0.5, canvas="#c")
    assert r["ok"] and not r["warnings"], (r["problems"], r["warnings"])
    r2 = verify_pixel.verify(page, tmp_path / "b", step=0.5)
    assert r2["warnings"] and "2 張 canvas" in r2["warnings"][0]
