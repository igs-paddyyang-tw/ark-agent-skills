#!/usr/bin/env python3
"""atlas_build — atlas/<slug>/ → site/index.html（View 軌；只排版、不改寫）。

用法:
  python atlas_build.py --book atlas/<slug> [--assets auto|inline|linked] [--max-inline-mb 8] [--check]
- 左側章節目錄 + 章節切換（hash routing）+ 頂部閱讀進度 + 深色風格 token（來自 atlas.yaml.style，ark-html-report 契約變數）
- provenance 標記 **OBSERVED** 等渲染為彩色 badge；`![..](assets/figures/F001.jpg)` + `<!-- figure -->` 渲染為 <figure> 附時間碼與 evidence 連結
- mermaid fence 以 CDN 渲染（離線時保留原文）
- 頁尾雙軌戳記：每章 content-src + sha256、figures.json sha256；`--check` 比對現況 → STALE
- 頁尾固定「內部研究用途，不得外傳」
"""
from __future__ import annotations

import argparse
import base64
import datetime as _dt
import html
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import atlas_common as C  # noqa: E402

BADGE = {"OBSERVED": "ok", "INFERRED": "info", "DECIDED": "accent", "FROM_KB": "muted", "PROPOSED": "warn", "UNKNOWN": "danger"}
DEFAULT_TOKENS = C.yaml_load(pathlib.Path(__file__).resolve().parent.parent / "assets" / "default-style.yaml")["tokens"] if (pathlib.Path(__file__).resolve().parent.parent / "assets" / "default-style.yaml").exists() else {}


def esc(t: str) -> str:
    return html.escape(t, quote=False)


def inline_md(t: str) -> str:
    t = esc(t)
    t = re.sub(r"\*\*(OBSERVED|INFERRED|DECIDED|FROM_KB|PROPOSED|UNKNOWN)\*\*", lambda m: f'<span class="badge {BADGE[m.group(1)]}">{m.group(1)}</span>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\b(E\d{3,})\b", r'<a class="ev" href="#fig-ev-\1">\1</a>', t)
    return t


def render_md(body: str, book: pathlib.Path, assets_mode: str, figs: dict) -> str:
    out, lines, i = [], body.splitlines(), 0
    list_open = table_open = False

    def close():
        nonlocal list_open, table_open
        if list_open:
            out.append("</ul>"); list_open = False
        if table_open:
            out.append("</tbody></table></div>"); table_open = False

    while i < len(lines):
        l = lines[i]
        if l.startswith("```"):
            close()
            lang = l[3:].strip()
            j = i + 1
            buf = []
            while j < len(lines) and not lines[j].startswith("```"):
                buf.append(lines[j]); j += 1
            code = "\n".join(buf)
            out.append(f'<pre class="mermaid">{esc(code)}</pre>' if lang == "mermaid" else f'<pre><code class="lang-{esc(lang)}">{esc(code)}</code></pre>')
            i = j + 1
            continue
        m = re.match(r"^(#{1,3}) (.+)$", l)
        if m:
            close()
            lvl = len(m.group(1))
            if lvl == 1:
                i += 1; continue  # 章標題由 ch-head 渲染
            sid = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", m.group(2)).strip("-")
            out.append(f'<h{lvl} id="{esc(sid)}">{inline_md(m.group(2))}</h{lvl}>')
            i += 1; continue
        mi = C.IMG_RE.match(l.strip())
        if mi:
            close()
            alt, src = mi.group(1), mi.group(2)
            fig_c = C.FIG_RE.match(lines[i + 1].strip()) if i + 1 < len(lines) else None
            fid = fig_c.group(1) if fig_c else None
            f = figs.get(fid, {})
            p = book / src
            if assets_mode == "inline" and p.exists():
                src_attr = "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode()
            else:
                src_attr = src
            evs = " ".join(f'<a class="ev" id="fig-ev-{e}" href="#fig-ev-{e}">{e}</a>' for e in f.get("evidence", []))
            meta = f"{f.get('type', 'figure')} · {' → '.join(f.get('ts', []))}" if f else ""
            out.append(f'<figure id="{esc(fid or "")}"><img src="{src_attr}" alt="{esc(alt)}" loading="lazy">'
                       f'<figcaption><b>{esc(fid or "")}</b> {esc(meta)} {evs}<span class="cap">{esc(alt)}</span></figcaption></figure>')
            i += 2 if fig_c else 1
            continue
        if l.startswith("<!--"):
            i += 1; continue
        if l.startswith("|"):
            cells = [c.strip() for c in l.strip().strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                i += 1; continue
            if not table_open:
                close()
                out.append('<div class="table-wrap"><table><thead><tr>' + "".join(f"<th>{inline_md(c)}</th>" for c in cells) + "</tr></thead><tbody>")
                table_open = True
            else:
                out.append("<tr>" + "".join(f"<td>{inline_md(c)}</td>" for c in cells) + "</tr>")
            i += 1; continue
        if l.startswith("- "):
            if table_open:
                close()
            if not list_open:
                out.append("<ul>"); list_open = True
            out.append(f"<li>{inline_md(l[2:])}</li>")
            i += 1; continue
        if l.strip() == "":
            close(); i += 1; continue
        close()
        out.append(f"<p>{inline_md(l)}</p>")
        i += 1
    close()
    return "\n".join(out)


CSS = """
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--font-body);line-height:1.7}
a{color:var(--accent)}code{font-family:var(--font-mono);background:var(--surface-2);padding:1px 6px;border-radius:var(--radius-sm);font-size:.9em}
pre{background:var(--surface-2);padding:14px;border-radius:var(--radius);overflow:auto;border:1px solid var(--border)}
#progress{position:fixed;top:0;left:0;height:3px;background:var(--accent);width:0;z-index:9}
.layout{display:flex;align-items:flex-start;min-height:100vh}
aside{flex:0 0 280px;background:var(--surface-2);border-right:1px solid var(--border);padding:24px 18px;position:sticky;top:0;height:100vh;overflow:auto}
aside .brand{font-family:var(--font-display);font-size:1.05rem;color:var(--accent);margin-bottom:4px}
aside .sub{color:var(--text-3);font-size:.8rem;margin-bottom:18px}
aside nav a{display:block;padding:8px 10px;margin:2px 0;border-left:3px solid transparent;color:var(--text-2);text-decoration:none;font-size:.92rem;border-radius:0 var(--radius-sm) var(--radius-sm) 0}
aside nav a.active{border-left-color:var(--accent);background:var(--accent-soft);color:var(--text)}
aside nav a .n{color:var(--text-3);font-family:var(--font-mono);font-size:.75rem;margin-right:8px}
main{flex:1 1 auto;min-width:0;padding:36px 48px 80px;max-width:var(--maxw);margin:0 auto}
.cover{padding:40px 0 20px;border-bottom:1px solid var(--border);margin-bottom:24px}
.cover h1{font-family:var(--font-display);font-size:2rem;margin:0 0 6px}
.cover .meta{color:var(--text-3);font-size:.85rem}.cover img{width:100%;border-radius:var(--radius);margin-top:18px;box-shadow:var(--shadow)}
.chapter{display:none}.chapter.active{display:block}
.ch-head{margin:0 0 18px}.ch-head .n{font-family:var(--font-mono);color:var(--accent);font-size:.85rem}.ch-head h1{font-family:var(--font-display);margin:2px 0 0;font-size:1.7rem}
h2{font-family:var(--font-display);margin-top:34px;padding-bottom:6px;border-bottom:1px solid var(--border);font-size:1.25rem}
h3{color:var(--text-2);margin-top:22px;font-size:1.02rem}
ul{padding-left:1.2em}li{margin:5px 0}
.badge{display:inline-block;font-family:var(--font-mono);font-size:.7rem;letter-spacing:.04em;padding:2px 7px;border-radius:999px;margin-right:6px;vertical-align:middle;border:1px solid var(--border)}
.badge.ok{color:var(--ok)}.badge.info{color:var(--info)}.badge.accent{color:var(--accent);border-color:var(--accent)}.badge.warn{color:var(--warn)}.badge.danger{color:var(--danger)}.badge.muted{color:var(--text-3)}
figure{margin:18px 0;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:10px;box-shadow:var(--shadow)}
figure img{width:100%;display:block;border-radius:var(--radius-sm)}
figcaption{font-size:.8rem;color:var(--text-2);margin-top:8px;font-family:var(--font-mono)}figcaption .cap{display:block;color:var(--text-3);margin-top:3px}
.ev{font-family:var(--font-mono);font-size:.8em;text-decoration:none;border-bottom:1px dotted var(--accent)}
.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:.9rem}th,td{border:1px solid var(--border);padding:6px 10px;text-align:left}th{background:var(--surface-2)}
.pager{display:flex;justify-content:space-between;margin-top:40px;padding-top:16px;border-top:1px solid var(--border)}.pager a{text-decoration:none}
footer{color:var(--text-3);font-size:.78rem;margin-top:40px;border-top:1px solid var(--border);padding-top:14px}
.watermark{position:fixed;right:16px;bottom:12px;color:var(--danger);opacity:.75;font-family:var(--font-mono);font-size:.75rem;pointer-events:none}
@media(max-width:900px){.layout{flex-direction:column}aside{position:static;height:auto;flex:none;width:100%}main{padding:20px}}
@media print{aside,#progress,.watermark{display:none}.chapter{display:block;page-break-before:always}}
"""

JS = """
(function(){const chs=[...document.querySelectorAll('.chapter')];const links=[...document.querySelectorAll('aside nav a')];
function show(id){chs.forEach(c=>c.classList.toggle('active',c.id===id));links.forEach(a=>a.classList.toggle('active',a.getAttribute('href')==='#'+id));
const i=chs.findIndex(c=>c.id===id);document.getElementById('progress').style.width=((i+1)/chs.length*100)+'%';window.scrollTo(0,0);}
function route(){let h=location.hash.replace('#','');if(h.startsWith('fig-ev-')){const el=document.getElementById(h);if(el){const ch=el.closest('.chapter');if(ch){show(ch.id);el.scrollIntoView();}}return;}
show(chs.some(c=>c.id===h)?h:chs[0].id);}
window.addEventListener('hashchange',route);route();
if(window.mermaid){try{mermaid.initialize({startOnLoad:true,theme:'dark'});}catch(e){}}})();
"""


def build(book: pathlib.Path, assets_mode: str, max_inline_mb: float) -> dict:
    cy = C.yaml_load(book / "atlas.yaml")
    figs_doc = json.loads((book / "figures.json").read_text(encoding="utf-8")) if (book / "figures.json").exists() else {"figures": []}
    figs = {f["figure_id"]: f for f in figs_doc["figures"]}
    total_mb = sum((book / f["file"]).stat().st_size for f in figs.values() if (book / f["file"]).exists()) / 1e6
    if assets_mode == "auto":
        assets_mode = "inline" if total_mb <= max_inline_mb else "linked"
    style = cy.get("style") or {}
    tokens = {**DEFAULT_TOKENS, **(style.get("tokens") or {})}
    root_css = ":root{" + ";".join(f"{k}:{v}" for k, v in tokens.items()) + "}"
    chapters, stamps = [], []
    for c in cy["chapters"]:
        p = book / c["file"]
        md = p.read_text(encoding="utf-8")
        stamps.append(f"<!-- content-src: {c['file']} sha256:{C.sha_text(md)[:16]} -->")
        ch = C.parse_chapter(md)
        chapters.append({"id": f"ch-{c['n']:02d}", "n": c["n"], "title": c["title"], "type": c["type"],
                         "html": render_md(ch["body"], book, assets_mode, figs)})
    nav = "".join(f'<a href="#{c["id"]}"><span class="n">{c["n"]:02d}</span>{esc(c["title"])}</a>' for c in chapters)
    cover_img = ""
    if cy.get("cover", {}).get("image") and (book / cy["cover"]["image"]).exists():
        p = book / cy["cover"]["image"]
        src = "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode() if assets_mode == "inline" else cy["cover"]["image"]
        cover_img = f'<img src="{src}" alt="cover">'
    g = cy.get("game", {})
    cover = (f'<div class="cover"><h1>{esc(cy["title"])}</h1><div class="meta">{esc(cy.get("subtitle", ""))} · v{cy.get("version", 1)} · {esc(cy.get("status", ""))} · '
             f'{esc(g.get("display_name", ""))} / {esc(g.get("domain", ""))} · run {esc(g.get("run_id", ""))}</div>{cover_img}</div>')
    body_chapters = []
    for i, c in enumerate(chapters):
        prev_ = f'<a href="#{chapters[i-1]["id"]}">‹ {esc(chapters[i-1]["title"])}</a>' if i else "<span></span>"
        next_ = f'<a href="#{chapters[i+1]["id"]}">{esc(chapters[i+1]["title"])} ›</a>' if i + 1 < len(chapters) else "<span></span>"
        body_chapters.append(f'<section class="chapter" id="{c["id"]}">{cover if i == 0 else ""}<div class="ch-head"><div class="n">第 {c["n"]:02d} 章</div><h1>{esc(c["title"])}</h1></div>'
                             f'{c["html"]}<div class="pager">{prev_}<span>{i+1} / {len(chapters)}</span>{next_}</div></section>')
    built = _dt.datetime.now().isoformat(timespec="seconds")
    watermark = '<div class="watermark">草稿版 · 含未決議項</div>' if cy.get("status") == "draft" else '<div class="watermark">內部研究用途 · 不得外傳</div>'
    page = f"""<!doctype html><html lang="zh-Hant" data-theme="{esc(style.get('theme', 'dark'))}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(cy['title'])}</title><style>{root_css}{CSS}</style></head><body>
<div id="progress"></div><div class="layout"><aside><div class="brand">{esc(cy['title'])}</div><div class="sub">{esc(g.get('display_name', ''))} · {len(chapters)} 章 · {len(figs)} 圖</div><nav>{nav}</nav></aside>
<main>{''.join(body_chapters)}
<footer>{esc(cy['title'])} · v{cy.get('version', 1)} · 由 ark-game-atlas 由 run {esc(g.get('run_id', ''))} 編成 · built {built} · assets: {assets_mode}<br>
本書每個數字都能回溯到規格書的一條主張；圖上時間碼可回到原始影片核對。<b>內部競品研究用途，不得外傳。</b></footer>
{watermark}</main></div>
{''.join(stamps)}
<!-- atlas-src: atlas.yaml sha256:{C.sha_text((book / 'atlas.yaml').read_text(encoding='utf-8'))[:16]} figures:{C.sha_file(book / 'figures.json')[:16] if (book / 'figures.json').exists() else 'none'} chapters:{len(chapters)} built:{built} -->
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script><script>{JS}</script></body></html>"""
    (book / "site").mkdir(exist_ok=True)
    C.atomic_write(book / "site" / "index.html", page)
    if assets_mode == "linked":
        # linked：site/ 需能找到 ../assets → 複製一份到 site/assets
        import shutil
        shutil.copytree(book / "assets", book / "site" / "assets", dirs_exist_ok=True)
    size_mb = round((book / "site" / "index.html").stat().st_size / 1e6, 2)
    return {"site": str(book / "site" / "index.html"), "assets_mode": assets_mode, "size_mb": size_mb, "chapters": len(chapters), "figures": len(figs)}


def check(book: pathlib.Path) -> dict:
    site = book / "site" / "index.html"
    if not site.exists():
        return {"status": "NO-SITE", "stale": []}
    html_ = site.read_text(encoding="utf-8")
    stamps = dict(re.findall(r"<!-- content-src: (\S+) sha256:([0-9a-f]{16}) -->", html_))
    if not stamps:
        return {"status": "NO-STAMP", "stale": []}
    stale = [f for f, h in stamps.items() if not (book / f).exists() or C.sha_text((book / f).read_text(encoding="utf-8"))[:16] != h]
    m = re.search(r"figures:([0-9a-f]{16}|none)", html_)
    if m and (book / "figures.json").exists() and m.group(1) != C.sha_file(book / "figures.json")[:16]:
        stale.append("figures.json")
    return {"status": "STALE" if stale else "OK", "stale": stale}


def main() -> None:
    ap = argparse.ArgumentParser(description="build atlas html")
    ap.add_argument("--book", required=True)
    ap.add_argument("--assets", default="auto", choices=["auto", "inline", "linked"])
    ap.add_argument("--max-inline-mb", type=float, default=8.0)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    book = C.atlas_dir(a.book)
    if a.check:
        r = check(book)
        if r["status"] != "OK":
            C.fail("GATE_BLOCKED", f"雙軌 {r['status']}: {r['stale']}", "重跑 atlas_build.py", data=r)
        C.emit(r, {"stage": "check"})
    with C.Timer() as t:
        r = build(book, a.assets, a.max_inline_mb)
    C.emit(r, {"stage": "build", "elapsed_ms": t.elapsed_ms})


if __name__ == "__main__":
    main()
