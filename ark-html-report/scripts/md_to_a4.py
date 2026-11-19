#!/usr/bin/env python3
"""Markdown → 多頁 A4 文件（單檔 HTML，可列印、可存 PDF）。

適用：專案計畫書、規格書、分析報告等「多頁文件」。單頁圖卡請看 references/a4-infocard.md；
要捲動閱讀、含目錄與 KPI 的報告頁請用 ark-md-report 的 build_report_html.py。

用法：
  python md_to_a4.py <src.md> <out.html> [--style paperprint] [--kick "<專案> ・ 專案計畫書"]
      [--playwright <含 node_modules/playwright-core 的資料夾>]   # 有 mermaid 圖才需要
      [--no-webfont] [--no-stamp]
  python md_to_a4.py --list-styles

- 配色：讀 references/styles.md 的五種風格 token（預設 paperprint，列印最穩）
- 報頭：frontmatter 的 title；version／date／created／updated／status／verdict 放報頭小字
- 分頁：@page A4、頁尾頁碼；表格列、程式碼、引言、圖不跨頁切斷；h2／h3 不孤立在頁尾
- 輸出是 deterministic：同一份原稿重產內容相同（不寫產生日期）
- 原稿是 ark-md-report 報告（frontmatter 有 source_skill: ark-md-report）時自動寫入雙軌戳記，
  可用 ark-md-report 的 report_pair.py check 驗證；--no-stamp 可關
- mermaid：同一棵 skills 樹裡有 ark-md-report 時沿用它的渲染（需 node＋playwright-core）；
  沒有時保留原始碼區塊並在 stderr 提示
"""
from __future__ import annotations

import argparse
import hashlib
import html
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STYLES_MD = HERE.parent / "references" / "styles.md"
MD_REPORT_SCRIPTS = HERE.parents[1] / "ark-md-report" / "scripts"
DEFAULT_STYLE = "paperprint"
META_KEYS = (("version", "版本"), ("date", "日期"), ("created", "建立"), ("updated", "更新"),
             ("status", "狀態"), ("verdict", "結論"))
e = html.escape

LAYOUT_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#e9e9e9;color:var(--text);font-family:var(--font-body);font-size:10.5pt;line-height:1.6}
.a4{width:210mm;min-height:297mm;margin:16px auto;background:var(--surface);padding:16mm 15mm 14mm;
  box-shadow:0 2px 20px rgba(24,34,51,.12);-webkit-print-color-adjust:exact;print-color-adjust:exact}
header.doc{border-bottom:2px solid var(--accent);padding-bottom:5mm;margin-bottom:6mm}
header.doc .kick{font-size:9pt;color:var(--text-3);letter-spacing:.05em}
header.doc h1{font-family:var(--font-display);font-size:19pt;line-height:1.35;margin:2mm 0;font-weight:700}
header.doc .meta{font-size:9pt;color:var(--text-2)}
header.doc .meta span{margin-right:5mm}
h1,h2,h3{font-family:var(--font-display);line-height:1.35}
h1{font-size:16pt;margin:7mm 0 3mm}
h2{font-size:13pt;margin:7mm 0 3mm;padding-bottom:1.5mm;border-bottom:1px solid var(--border)}
h2::before{content:"";display:inline-block;width:3px;height:12pt;background:var(--accent);margin-right:2.5mm;vertical-align:-2px}
h3{font-size:11pt;margin:5mm 0 2mm;color:var(--text-2)}
p{margin:2mm 0}
ul,ol{margin:2mm 0 2mm 6mm}
li{margin:.8mm 0}
a{color:var(--accent)}
code{font-family:var(--font-mono);font-size:9pt;background:var(--surface-2);padding:0 1.2mm}
pre{background:var(--surface-2);border:1px solid var(--border);padding:3mm;margin:3mm 0;overflow-x:auto;
  font-size:8.5pt;line-height:1.45;white-space:pre-wrap;word-break:break-word}
pre code{background:none;padding:0}
blockquote{border-left:3px solid var(--accent);background:var(--accent-soft);padding:2mm 4mm;margin:3mm 0;color:var(--text-2)}
table{width:100%;border-collapse:collapse;margin:3mm 0;font-size:9pt;line-height:1.45}
th,td{border:1px solid var(--border);padding:1.6mm 2.2mm;vertical-align:top;text-align:left}
th{background:var(--surface-2);font-weight:700}
thead{display:table-header-group}
figure.mm{margin:3mm 0;text-align:center}figure.mm svg{max-width:100%;height:auto}
footer.doc{margin-top:8mm;padding-top:3mm;border-top:1px solid var(--border);font-size:8.5pt;color:var(--text-3)}
@page{size:A4;margin:14mm 13mm 16mm;
  @bottom-right{content:counter(page) " / " counter(pages);font-size:8pt;color:#888}}
@media print{
  body{background:#fff}
  .a4{margin:0;box-shadow:none;width:auto;min-height:auto;padding:0}
  tr,pre,blockquote,figure,img{break-inside:avoid}
  h1,h2,h3{break-after:avoid}
  a{text-decoration:none}
}
@media (max-width:820px){.a4{width:auto;min-height:auto;margin:0;padding:16px}}
"""


def load_styles(path: Path = STYLES_MD) -> dict[str, dict[str, str]]:
    """從 styles.md 讀出各風格的 font import 與 :root 區塊：{名稱: {"import": ..., "root": ...}}。"""
    text = path.read_text(encoding="utf-8")
    styles: dict[str, dict[str, str]] = {}
    for m in re.finditer(r"^## \d+\. (\w+)[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S):
        css = re.search(r"```css\n(.*?)```", m.group(2), re.S)
        if not css:
            continue
        imp = re.search(r"^@import url\('([^']+)'\);", css.group(1), re.M)
        root = re.search(r":root\s*\{.*?\}", css.group(1), re.S)
        if root:
            styles[m.group(1)] = {"import": imp.group(1) if imp else "", "root": root.group(0)}
    return styles


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """拆出 frontmatter（容許 BOM、CRLF；只取單行 key: value，不需 PyYAML）。"""
    text = text.lstrip("\ufeff").replace("\r\n", "\n")
    m = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}, text
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        km = re.match(r"^([A-Za-z_][\w-]*):\s*(.+?)\s*$", line)
        if km and not km.group(2).startswith(("|", ">")):
            v = km.group(2)
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            fm[km.group(1)] = v
    return fm, text[m.end():]


def _norm(s: str) -> str:
    return re.sub(r"[\s*`_]", "", s)


def drop_dup_h1(body: str, title: str) -> str:
    """內文開頭的 H1 與報頭標題相同才拿掉（不同就保留）。"""
    m = re.match(r"\A\s*# (.+)\n", body)
    if m and _norm(m.group(1)) == _norm(title):
        return body[m.end():]
    return body


def _md_report_mermaid():
    """沿用 ark-md-report 的 mermaid 渲染（同一棵 skills 樹裡有才用）；沒有回 None。"""
    if not (MD_REPORT_SCRIPTS / "build_report_html.py").exists():
        return None
    sys.path.insert(0, str(MD_REPORT_SCRIPTS))
    try:
        import build_report_html as b  # type: ignore
    except Exception:  # noqa: BLE001
        return None
    finally:
        sys.path.pop(0)
    return b


def render_mermaid_blocks(body: str, playwright_dir: str) -> tuple[str, list[str]]:
    """把 ```mermaid 區塊換成佔位符並渲染；不能渲染時原樣保留。回傳（body、svg 清單）。"""
    blocks = re.findall(r"```mermaid\n(.*?)```", body, re.S)
    if not blocks:
        return body, []
    b = _md_report_mermaid()
    if b is None or not playwright_dir:
        why = "找不到 ark-md-report" if b is None else "沒給 --playwright（或 PW_DIR）"
        print(f"⚠ 有 {len(blocks)} 張 mermaid 圖但{why}，保留原始碼區塊", file=sys.stderr)
        return body, []
    svgs = [b.tidy_svg(s) for s in b.render_mermaid(blocks, playwright_dir)]
    for i, blk in enumerate(blocks):
        body = body.replace(f"```mermaid\n{blk}```", f"\n\nMERMAIDFIG{i}\n\n", 1)
    return body, svgs


def src_label(src: Path) -> str:
    """頁尾與戳記用的原稿路徑：在目前目錄底下就用相對路徑，否則只用檔名（不洩漏 home 路徑）。"""
    try:
        return src.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return src.name


def stamp_line(src: Path, label: str) -> str:
    """與 ark-md-report report_pair.py 相同格式的雙軌戳記。"""
    return f"<!-- content-src: {label} sha256:{hashlib.sha256(src.read_bytes()).hexdigest()[:16]} -->"


def build(src: Path, *, style: str = DEFAULT_STYLE, kick: str = "", playwright_dir: str = "",
          webfont: bool = True, stamp: bool | None = None) -> str:
    """組出整份 A4 HTML。stamp=None 表示依 frontmatter 自動判斷。"""
    import markdown

    styles = load_styles()
    if style not in styles:
        raise SystemExit(f"沒有風格 {style!r}；可用：{', '.join(styles)}（預設 {DEFAULT_STYLE}）")
    fm, body = split_frontmatter(src.read_text(encoding="utf-8"))
    title = fm.get("title") or src.stem
    body = drop_dup_h1(body, title)
    body, svgs = render_mermaid_blocks(body, playwright_dir)

    h = markdown.markdown(body, extensions=["tables", "fenced_code", "sane_lists"])
    for i, svg in enumerate(svgs):
        h = h.replace(f"<p>MERMAIDFIG{i}</p>", f'<figure class="mm">{svg}</figure>')

    meta = "".join(f"<span>{label}：{e(fm[k])}</span>" for k, label in META_KEYS if fm.get(k))
    label = src_label(src)
    font = (f'<link href="{e(styles[style]["import"])}" rel="stylesheet">'
            if webfont and styles[style]["import"] else "")
    page = f"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>{font}
<style>{styles[style]["root"]}{LAYOUT_CSS}</style></head>
<body><main class="a4">
<header class="doc">{f'<div class="kick">{e(kick)}</div>' if kick else ''}<h1>{e(title)}</h1><div class="meta">{meta}</div></header>
{h}
<footer class="doc">原稿（Content 軌）：<code>{e(label)}</code> ・ 本頁只做排版，內容以原稿為準</footer>
</main>
</body></html>
"""
    if svgs:
        b = _md_report_mermaid()
        if b is not None:
            page, _ = b.postprocess(page.replace('class="mm"', 'class="fig mm"'))
    if stamp is None:
        stamp = fm.get("source_skill") == "ark-md-report"
    if stamp:
        page = page.replace("</body>", stamp_line(src, label) + "\n</body>", 1)
    return page


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Markdown → 多頁 A4 文件（單檔 HTML）")
    ap.add_argument("src", nargs="?")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--style", default=DEFAULT_STYLE, help=f"配色風格（預設 {DEFAULT_STYLE}；--list-styles 看全部）")
    ap.add_argument("--kick", default="", help="報頭小字，建議「<專案> ・ <文件類型>」")
    ap.add_argument("--playwright", default=os.environ.get("PW_DIR", ""), help="有 mermaid 圖才需要")
    ap.add_argument("--no-webfont", action="store_true", help="不載入 Google Fonts（離線環境用系統字型）")
    ap.add_argument("--stamp", dest="stamp", action="store_true", default=None, help="強制寫雙軌戳記")
    ap.add_argument("--no-stamp", dest="stamp", action="store_false", help="不寫雙軌戳記")
    ap.add_argument("--list-styles", action="store_true")
    a = ap.parse_args(argv)
    if a.list_styles:
        print("\n".join(load_styles()))
        return 0
    if not (a.src and a.out):
        ap.error("需要 <src.md> <out.html>")
    src = Path(a.src)
    page = build(src, style=a.style, kick=a.kick, playwright_dir=a.playwright,
                 webfont=not a.no_webfont, stamp=a.stamp)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"✅ {out}｜風格 {a.style}｜{'含' if 'content-src:' in page else '無'}雙軌戳記")
    return 0


if __name__ == "__main__":
    sys.exit(main())
