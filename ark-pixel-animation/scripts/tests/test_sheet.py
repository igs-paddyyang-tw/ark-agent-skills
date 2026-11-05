"""sprite sheet 模式（1.1）：export_sheet 匯出 → verify_sheet 驗收；壞 sheet 反證。

需要 playwright＋Pillow＋可啟動的 Chromium（匯出用）；缺件時匯出相關測試 skip（不假綠）。
壞 sheet 由好 sheet 在測試中改壞（不放二進位樣本檔）。
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

SKILL = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILL / "scripts"))
import verify_sheet  # noqa: E402

NAMES = ["nana-agent", "cto-agent", "ceo-agent", "qa-agent", "coder-agent", "design-agent"]


def _chromium_ok() -> bool:
    try:
        from playwright.sync_api import Error, sync_playwright
    except ImportError:
        return False
    try:
        with sync_playwright() as p:
            p.chromium.launch(executable_path=os.environ.get("ARK_PIXEL_CHROMIUM") or None).close()
        return True
    except Error:
        return False


needs_browser = pytest.mark.skipif(not _chromium_ok(), reason="Chromium 無法啟動")


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    if not _chromium_ok():
        pytest.skip("Chromium 無法啟動")
    import export_sheet
    out = tmp_path_factory.mktemp("chars")
    res = export_sheet.export(NAMES, out)
    return out, res


@needs_browser
def test_export_writes_png_and_manifest(exported):
    out, res = exported
    assert len(res) == len(NAMES)
    m = json.loads((out / "cto-agent.json").read_text(encoding="utf-8"))
    assert m["schema"] == "ark.pixel_character.v1" and m["frame"] == {"w": 16, "h": 32}
    assert m["rows"] == ["down", "up", "right"] and m["frames"]["type"] == [3, 4]
    assert Image.open(out / "char_cto-agent.png").size == (112, 96)


@needs_browser
def test_exported_sheets_pass_all_checks(exported, tmp_path):
    out, _ = exported
    for png in sorted(out.glob("char_*.png")):
        r = verify_sheet.check(png, tmp_path)
        assert r["ok"], (png.name, r["problems"])
        assert Path(r["contact"]).exists()


@needs_browser
def test_looks_unique_within_group(exported):
    _, res = exported
    keys = {json.dumps(r["look"], sort_keys=True) for r in res}
    assert len(keys) == len(NAMES)


@needs_browser
def test_export_is_deterministic(exported, tmp_path):
    import export_sheet
    out, _ = exported
    export_sheet.export(NAMES, tmp_path)
    for n in ("cto-agent", "design-agent"):
        assert (tmp_path / f"char_{n}.png").read_bytes() == (out / f"char_{n}.png").read_bytes()


def test_template_has_single_source_placeholder():
    """產生器只有一份（chibi.js）：模板不得內嵌第二份 drawFrame。"""
    tpl = (SKILL / "assets" / "template-sheet.html").read_text(encoding="utf-8")
    assert "/*__ARK_CHIBI__*/" in tpl and "function drawFrame" not in tpl


def test_inline_injection_escapes_script_close():
    """chibi.js 內容含 </script 時，注入後不得提早關閉標籤（實測踩過）。"""
    import export_sheet
    page = export_sheet.assemble_page()
    start = page.index("<script>") + len("<script>")
    end = page.index("</script>", start)
    assert "ArkChibi" in page[start:end]                     # 第一個 </script> 之前就是完整的 chibi.js
    assert "g.ArkChibi = {" in page[start:end]


# ── 壞 sheet 反證：每一種都必須紅，且訊息指出格子與修法 ───────────────────────
@pytest.fixture
def good(exported, tmp_path):
    out, _ = exported
    shutil.copy(out / "char_cto-agent.png", tmp_path / "char_cto-agent.png")
    shutil.copy(out / "cto-agent.json", tmp_path / "cto-agent.json")
    return tmp_path / "char_cto-agent.png"


def _mutate(png: Path, fn) -> None:
    img = Image.open(png).convert("RGBA")
    fn(img)
    img.save(png)


@needs_browser
def test_bad_off_palette_color(good):
    _mutate(good, lambda im: im.putpixel((16 * 3 + 8, 32 + 20), (0, 255, 0, 255)))     # up 列、打字 3
    r = verify_sheet.check(good)
    assert not r["ok"] and any("⑤ 色盤外顏色 #00ff00" in p and "up" in p for p in r["problems"])


@needs_browser
def test_bad_semi_transparent_edge(good):
    _mutate(good, lambda im: im.putpixel((16 * 2 + 1, 10), (14, 15, 22, 128)))        # down 列、走路 2
    r = verify_sheet.check(good)
    assert not r["ok"] and any(p.startswith("② ") and "走路2" in p for p in r["problems"])


@needs_browser
def test_bad_bleed_across_cells(good):
    def shift(im):
        cell = im.crop((16, 0, 32, 32))                     # down 列、走路 1 往右移 4px → 壓到隔壁格
        im.paste((0, 0, 0, 0), (16, 0, 32, 32))
        im.alpha_composite(cell, (20, 0))
    _mutate(good, shift)
    r = verify_sheet.check(good)
    assert not r["ok"] and any(p.startswith("③ 圖案跨格") and "走路1" in p for p in r["problems"])


@needs_browser
def test_bad_floating_feet(good):
    def lift(im):
        cell = im.crop((0, 64, 16, 96))                     # right 列、走路 0 往上 3px
        im.paste((0, 0, 0, 0), (0, 64, 16, 96))
        im.alpha_composite(cell.crop((0, 3, 16, 32)), (0, 64))
    _mutate(good, lift)
    r = verify_sheet.check(good)
    assert not r["ok"] and any(p.startswith("④ ") and "right" in p and "第 28 列" in p for p in r["problems"])


def test_wrong_size(tmp_path):
    p = tmp_path / "char_x.png"
    Image.new("RGBA", (96, 96)).save(p)
    r = verify_sheet.check(p)
    assert not r["ok"] and r["problems"][0].startswith("① 尺寸 96×96")
