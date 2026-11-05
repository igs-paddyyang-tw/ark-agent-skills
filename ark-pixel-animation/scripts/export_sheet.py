#!/usr/bin/env python3
"""Q 版角色 sprite sheet 匯出：名字 → `char_<slug>.png`（112×96 RGBA）＋ `<slug>.json`（ark.pixel_character.v1）。

用法::

    python3 export_sheet.py --name cto-agent --name qa-agent --out characters/
    python3 export_sheet.py --names-file names.txt --out characters/          # 一行一個名字
    python3 export_sheet.py --preview sheet.html                              # 只產預覽頁（?name= 指定角色）

- 產生器只有一份：`assets/chibi.js`，注入 `assets/template-sheet.html` 後由 Chromium 畫出（與網頁即時畫的完全相同）。
- 同一次匯出的多個名字，外觀保證不重複（chibi.js `uniqueLooks`）；同樣的名字組合每次輸出相同。
- 產出後請跑 `verify_sheet.py` 驗收。

exit code：0 成功、2 環境缺件（playwright／Pillow／Chromium）或參數錯誤。
Chromium 版本與 playwright 不合時，用 ``--chromium`` 或環境變數 ``ARK_PIXEL_CHROMIUM`` 指定。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlencode

try:
    from PIL import Image
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except ImportError as exc:  # pragma: no cover - 環境缺件
    print(f"缺少相依套件：{exc.name}。安裝：pip install playwright Pillow", file=sys.stderr)
    sys.exit(2)

SKILL = Path(__file__).resolve().parents[1]
CHIBI = SKILL / "assets" / "chibi.js"
TEMPLATE = SKILL / "assets" / "template-sheet.html"
PLACEHOLDER = "/*__ARK_CHIBI__*/"
SCHEMA = "ark.pixel_character.v1"


def skill_version() -> str:
    m = re.search(r'^\s*version:\s*"([^"]+)"', (SKILL / "SKILL.md").read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else "?"


def assemble_page() -> str:
    """模板＋chibi.js → 自足的單檔 HTML 字串。"""
    tpl = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in tpl:
        raise SystemExit(f"模板缺少 {PLACEHOLDER}")
    # 🔴 內嵌進 <script> 時，JS 原始碼裡任何 "</script" 都會提早關閉標籤（實測：chibi.js 註解曾含一個 → 頁面空白）
    js = CHIBI.read_text(encoding="utf-8").replace("</script", "<\\/script")
    return tpl.replace(PLACEHOLDER, js)


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "character"


def manifest(sheet: dict) -> dict:
    return {
        "schema": SCHEMA, "name": sheet["name"], "frame": {"w": 16, "h": 32},
        "rows": ["down", "up", "right"], "frames": {"walk": [0, 1, 2], "type": [3, 4], "read": [5, 6]},
        "palette": sheet["palette"], "look": sheet["look"], "hash": sheet["hash"],
        "generator": "ark-pixel-animation/assets/chibi.js", "skill_version": skill_version(),
    }


def export(names: list[str], out: Path, chromium: str | None = None) -> list[dict]:
    out.mkdir(parents=True, exist_ok=True)
    results = []
    with tempfile.TemporaryDirectory() as td:
        page_path = Path(td) / "sheet.html"
        page_path.write_text(assemble_page(), encoding="utf-8")
        base = page_path.resolve().as_uri()
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=chromium or os.environ.get("ARK_PIXEL_CHROMIUM") or None)
            pg = browser.new_page()
            errs: list[str] = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            for name in names:
                pg.goto(base + "?" + urlencode({"name": name, "names": ",".join(names), "t": 0}))
                pg.wait_for_function("window.__pixel && window.__pixel.sheet", timeout=15000)
                sheet = pg.evaluate("__pixel.sheet()")
                img = Image.frombytes("RGBA", (sheet["w"], sheet["h"]), bytes(sheet["rgba"]))
                slug = slugify(name)
                png, js = out / f"char_{slug}.png", out / f"{slug}.json"
                img.save(png, optimize=True)
                js.write_text(json.dumps(manifest(sheet), ensure_ascii=False, indent=1), encoding="utf-8")
                results.append({"name": name, "png": str(png), "manifest": str(js), "look": sheet["look"]})
            browser.close()
            if errs:
                raise RuntimeError("頁面錯誤：" + " | ".join(errs[:3]))
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Q 版角色 sprite sheet 匯出（ark.pixel_character.v1）")
    ap.add_argument("--name", action="append", default=[], help="角色名（可重複）；決定外觀")
    ap.add_argument("--names-file", type=Path, help="一行一個名字")
    ap.add_argument("--out", type=Path, default=Path("characters"))
    ap.add_argument("--preview", type=Path, help="只寫出預覽頁（開啟時加 ?name=…）")
    ap.add_argument("--chromium", help="指定 Chromium 執行檔")
    a = ap.parse_args(argv)
    if a.preview:
        a.preview.write_text(assemble_page(), encoding="utf-8")
        print(json.dumps({"ok": True, "preview": str(a.preview)}, ensure_ascii=False))
        return 0
    names = list(a.name)
    if a.names_file:
        names += [ln.strip() for ln in a.names_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
    names = list(dict.fromkeys(names))
    if not names:
        print("至少給一個 --name 或 --names-file", file=sys.stderr)
        return 2
    try:
        res = export(names, a.out, a.chromium)
    except PlaywrightError as exc:
        if "Executable doesn't exist" in str(exc):
            print("找不到 Chromium：python -m playwright install chromium，或用 --chromium／ARK_PIXEL_CHROMIUM 指定", file=sys.stderr)
            return 2
        raise
    print(json.dumps({"ok": True, "count": len(res), "items": res}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
