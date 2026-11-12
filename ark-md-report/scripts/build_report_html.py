#!/usr/bin/env python3
"""報告 MD（Content 軌）→ 單檔 HTML（View 軌）：只裁剪不改寫，```mermaid 區塊建置時渲染成內嵌 SVG。

適用：ark-md-report 契約的審查／分析報告，要做成給人看的長文頁（左側目錄、hero、KPI、內文、頁尾），
特別是含 mermaid 圖的報告。純版面設計、圖卡、儀表板請用 ark-html-report。

用法：
  python build_report_html.py <src.md> <out.html> --asof "<資料截至說明>"
      [--kpi "值|標籤"]...（最多 5 個） [--kick "<專案> ・ 技術分析報告"]
      [--public --back "<回連網址>|<文字>"]
      [--playwright <含 node_modules/playwright-core 的資料夾>]   # 有 mermaid 才需要
      [--no-postprocess]

需要：python-markdown。mermaid 渲染另需 node、playwright-core 與本機 chromium（~/.cache/ms-playwright），
渲染時會連網載入 mermaid 10.9.1（jsDelivr）與 Noto Sans TC（Google Fonts）；產出的 HTML 內嵌 SVG，離線可看圖。

建置後自動做兩件事（--no-postprocess 可關）：
1. SVG 數字取小數 1 位、百分比取整數 —— 浮點長尾（25.040000000000003）會被公開版掃描誤判成 commit 編號或營運百分比。
2. mermaid 後處理：補標籤 CSS（渲染頁與報告頁的字型度量不同，框內文字會被截斷），
   刪掉沒被引用的 <symbol>（sequenceDiagram 內嵌的 database 等圖示路徑會被 IP 規則命中）。

公開版（--public）：hero 不顯示 verdict／confidence／findings，改顯示「公開版」徽章；頁尾只放回連與資料截至日。
產出後一定要跑 public_scan.py，0 命中才可對外。
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
e = html.escape

MERMAID_CSS = ("figure.mm svg foreignObject{overflow:visible}"
               "figure.mm .nodeLabel,figure.mm .edgeLabel,figure.mm .cluster-label"
               "{font-family:'Noto Sans TC',sans-serif!important;font-size:90%!important}")


def tidy_svg(svg: str) -> str:
    """SVG 數字取小數 1 位、百分比取整數。"""
    svg = re.sub(r"(\d+\.\d+)%", lambda m: f"{round(float(m.group(1)))}%", svg)
    return re.sub(r"(?<![\w#])(-?\d+\.\d{2,})", lambda m: f"{float(m.group(1)):.1f}", svg)


def postprocess(page: str) -> tuple[str, int]:
    """補 mermaid 標籤 CSS、刪未引用的 <symbol>；回傳（處理後 HTML、刪除數）。"""
    if 'class="fig mm"' in page and MERMAID_CSS not in page:
        page = page.replace("</style>", MERMAID_CSS + "</style>", 1)
    removed = 0

    def drop(m: re.Match) -> str:
        nonlocal removed
        sid = m.group(1)
        if f'href="#{sid}"' in page or f"url(#{sid})" in page:
            return m.group(0)
        removed += 1
        return ""

    page = re.sub(r'<symbol[^>]*\bid="([^"]+)"[^>]*>.*?</symbol>', drop, page, flags=re.S)
    return page.replace("<defs></defs>", ""), removed


def render_mermaid(blocks: list[str], playwright_dir: str) -> list[str]:
    """呼叫 render_mermaid.mjs 一次渲染所有 mermaid 區塊。"""
    if not playwright_dir:
        raise SystemExit("有 mermaid 圖，需要 --playwright <含 node_modules/playwright-core 的資料夾>（或環境變數 PW_DIR）")
    with tempfile.TemporaryDirectory() as td:
        inp, outp = Path(td, "in.json"), Path(td, "out.json")
        inp.write_text(json.dumps(blocks, ensure_ascii=False), encoding="utf-8")
        subprocess.run(["node", str(HERE / "render_mermaid.mjs"), str(inp), str(outp)], check=True,
                       env={**os.environ, "PW_DIR": str(Path(playwright_dir).resolve())})
        return json.loads(outp.read_text(encoding="utf-8"))


def build(text: str, *, src_label: str, asof: str, kpis: list[str], kick: str, public: bool, back: str,
          playwright_dir: str = "", do_postprocess: bool = True) -> tuple[str, int]:
    """組出整頁 HTML；回傳（HTML、mermaid 張數）。"""
    import markdown

    fm_m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    fm = fm_m.group(1) if fm_m else ""
    body = text[fm_m.end():] if fm_m else text
    tm = re.search(r'^title:\s*"?(.*?)"?\s*$', fm, re.M) or re.search(r"^#\s+(.*)$", body, re.M)
    title = tm.group(1) if tm else src_label
    dm = re.search(r"^date:\s*(\S+)", fm, re.M)
    date = dm.group(1) if dm else ""

    blocks = re.findall(r"```mermaid\n(.*?)```", body, re.S)
    svgs = render_mermaid(blocks, playwright_dir) if blocks else []
    for i, blk in enumerate(blocks):
        body = body.replace(f"```mermaid\n{blk}```", f"\n\nMERMAIDFIG{i}\n\n", 1)

    md = markdown.Markdown(extensions=["tables", "fenced_code", "toc"], extension_configs={"toc": {"toc_depth": "2-3"}})
    h = md.convert(body)
    for i, svg in enumerate(svgs):
        h = h.replace(f"<p>MERMAIDFIG{i}</p>", f'<figure class="fig mm">{tidy_svg(svg)}</figure>')
    h = h.replace("<table>", '<div class="tw"><table>').replace("</table>", "</table></div>")
    for sev in ("P0", "P1", "P2", "P3"):
        h = re.sub(rf"<td>({sev})</td>", rf'<td><span class="sev {sev.lower()}">\1</span></td>', h)

    kpi_html = "".join(f'<div class="kpi"><div class="v">{e(v)}</div><div class="l">{e(l)}</div></div>'
                       for v, l in (k.split("|", 1) if "|" in k else (k, "") for k in kpis[:5]))
    if public:
        badges = '<span class="bd">公開版：已拿掉內部系統資訊、版本編號與審查細節</span>'
        url, label = (back.split("|", 1) + [""])[:2] if back else ("", "")
        back_html = f'<a class="back" href="{e(url)}">{e(label or url)}</a>　・　' if url else ""
        footer = f"{back_html}{e(asof)}"
    else:
        def fmv(k: str) -> str:
            m = re.search(rf"^{k}:\s*(.+)$", fm, re.M)
            return m.group(1).strip() if m else ""
        fnd = re.search(r"findings:\s*\{\s*p0:\s*(\d+),\s*p1:\s*(\d+),\s*p2:\s*(\d+),\s*p3:\s*(\d+)", fm)
        badges = "".join([
            f'<span class="bd warn">verdict <b>{e(fmv("verdict"))}</b></span>' if fmv("verdict") else "",
            f'<span class="bd">confidence <b>{e(fmv("confidence"))}</b></span>' if fmv("confidence") else "",
            f'<span class="bd">P0 <b>{fnd[1]}</b>・P1 <b>{fnd[2]}</b>・P2 <b>{fnd[3]}</b>・P3 <b>{fnd[4]}</b></span>' if fnd else "",
        ])
        footer = (f'{e(asof)}　・　Content 軌（source of truth）：<code>{e(src_label)}</code>'
                  f'　・　本頁只做視圖裁剪；圖由同名 MD 的 mermaid 區塊渲染。')

    css = (HERE / "report_html.css").read_text(encoding="utf-8")
    kick_line = f"{e(kick)} ・ {e(date)}" if date else e(kick)
    page = f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700;900&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>{css}</style></head><body><div class="wrap">
<nav class="toc"><div class="kick" style="margin-bottom:10px">目錄</div>{getattr(md, "toc", "")}</nav>
<main>
<header class="hero"><div class="kick">{kick_line}</div><h1>{e(title)}</h1>
<div class="asof">{e(asof)}</div>
<div class="badges">{badges}</div>
{f'<div class="kpis">{kpi_html}</div>' if kpi_html else ''}
</header>
{h}
<footer>{footer}</footer>
</main></div></body></html>"""
    if do_postprocess:
        page, _ = postprocess(page)
    return page, len(svgs)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="報告 MD → 單檔 HTML（mermaid 預渲染）")
    ap.add_argument("src"); ap.add_argument("out")
    ap.add_argument("--asof", required=True, help="資料截至說明（標題下與頁尾）")
    ap.add_argument("--kpi", action="append", default=[], help="「值|標籤」，最多 5 個")
    ap.add_argument("--kick", default="技術分析報告", help="hero 上方小字，建議「<專案> ・ 技術分析報告」")
    ap.add_argument("--public", action="store_true", help="公開版：拿掉審查評等")
    ap.add_argument("--back", default="", help="公開版頁尾回連「網址|文字」")
    ap.add_argument("--playwright", default=os.environ.get("PW_DIR", ""))
    ap.add_argument("--no-postprocess", action="store_true")
    a = ap.parse_args(argv)
    src = Path(a.src)
    page, n = build(src.read_text(encoding="utf-8"), src_label=str(src), asof=a.asof, kpis=a.kpi, kick=a.kick,
                    public=a.public, back=a.back, playwright_dir=a.playwright, do_postprocess=not a.no_postprocess)
    Path(a.out).write_text(page, encoding="utf-8")
    print(f"ok {a.out}｜{len(page):,} 字元｜mermaid {n} 張")
    return 0


if __name__ == "__main__":
    sys.exit(main())
