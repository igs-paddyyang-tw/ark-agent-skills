"""book_build.py — ark-book View 軌渲染器：MD 章節 → 單檔 HTML 書。

只排版、不改寫：HTML 內容全部來自 book.yaml 與章節 MD；每章嵌 content-src + sha256 戳記，
與 ark-html-report 的 report_pair.py 同一套漂移偵測邏輯。

用法：
    python book_build.py books/first-personal-agent/                 # → books/.../site/index.html（library 風格）
    python book_build.py --list-styles                                # 列出 assets/styles/ 所有風格
    python book_build.py books/xxx/ --style neon                     # 覆蓋 book.yaml 的 style
    python book_build.py books/xxx/ --style editorial --styles-ref /path/ark-html-report/references/styles.md
    python book_build.py books/xxx/ --out dist/xxx.html              # 自訂輸出
    python book_build.py books/xxx/ --check                          # 驗戳記：OK / STALE / NO-SITE / NO-STAMP
    python book_build.py books/xxx/ --check --json

Exit code：build 成功 0；--check 為 STALE/NO-SITE/NO-STAMP 時 1。
依賴：PyYAML、markdown（pip install pyyaml markdown）。
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from book_lint import split_frontmatter, load_yaml_text, FILENAME_RE, h2_sections, norm_title  # noqa: E402

ASSETS = Path(__file__).resolve().parent.parent / "assets"
TEMPLATE = ASSETS / "book-template.html"

STYLES_DIR = ASSETS / "styles"
MANIFEST = STYLES_DIR / "_manifest.json"

SECTION_CLASS = {
    "這章要解決的問題": "problem", "路線圖": "roadmap", "內文": "body", "常見誤解": "myths",
    "動手做": "practice", "重點回顧": "recap", "下一章": "next",
    "為什麼有這本書": "problem", "這本書給誰": "body", "讀完你會": "recap", "全書路線圖": "roadmap", "這本書不講": "note",
}
CALLOUT_TITLE = {"ASK": "你可能會想說", "TIP": "白話", "MYTH": "大家通常會以為", "TRY": "動手做",
                 "NOTE": "補充", "WARNING": "注意"}
LEVEL_ZH = {"beginner": "入門", "intermediate": "進階", "advanced": "深入"}
TYPE_ZH = {"preface": "序", "chapter": "章", "appendix": "附錄", "exercise": "練習"}
SPINE_CYCLE = ["c-green", "c-wine", "c-navy"]
TZ = timezone(timedelta(hours=8))


def sha16(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


# ── Markdown → HTML ────────────────────────────────────────────────────────

def md_to_html(md: str) -> str:
    try:
        import markdown  # type: ignore
    except ImportError:
        sys.exit("需要 markdown 套件：pip install markdown")
    md, callouts = _extract_callouts(md)
    out = markdown.markdown(md, extensions=["tables", "fenced_code", "attr_list", "sane_lists"])
    for i, chtml in enumerate(callouts):
        out = out.replace(f"<p>CALLOUTPLACEHOLDER{i}</p>", chtml)
    out = re.sub(r"<table>", '<div class="table-wrap"><table>', out)
    out = re.sub(r"</table>", "</table></div>", out)
    out = re.sub(r'<pre><code class="language-([\w+-]+)">', r'<pre data-lang="\1"><code class="language-\1">', out)
    return out


ALERT_LINE = re.compile(r"^>\s*\[!(ASK|TIP|MYTH|TRY|NOTE|WARNING)\][ \t]*(.*)$")


def _extract_callouts(md: str) -> tuple[str, list[str]]:
    """把 `> [!TYPE] title` 起頭的連續 blockquote 抽出，內容去掉 `> ` 後獨立跑 markdown
    （這樣 blockquote 內的 fenced code 與清單才會被正確解析），換成佔位符。"""
    lines = md.split("\n")
    out_lines: list[str] = []
    callouts: list[str] = []
    i = 0
    while i < len(lines):
        m = ALERT_LINE.match(lines[i])
        if not m:
            out_lines.append(lines[i])
            i += 1
            continue
        typ, title = m.group(1), m.group(2).strip() or CALLOUT_TITLE.get(m.group(1), m.group(1))
        inner: list[str] = []
        i += 1
        while i < len(lines) and lines[i].startswith(">"):
            inner.append(re.sub(r"^>[ ]?", "", lines[i]))
            i += 1
        import markdown  # type: ignore
        inner_html = markdown.markdown("\n".join(inner), extensions=["tables", "fenced_code", "attr_list", "sane_lists"])
        inner_html = re.sub(r'<pre><code class="language-([\w+-]+)">', r'<pre data-lang="\1"><code class="language-\1">', inner_html)
        callouts.append(f'<blockquote class="callout {typ.lower()}"><div class="ct">{html.escape(title)}</div>{inner_html}</blockquote>')
        out_lines.append("")
        out_lines.append(f"CALLOUTPLACEHOLDER{len(callouts) - 1}")
        out_lines.append("")
    return "\n".join(out_lines), callouts


# ── 章節渲染 ───────────────────────────────────────────────────────────────

def render_sections(body: str, chapter_id: str) -> str:
    """把 body 依 ## 切段，包成 <section class="section {cls}">，h2 保留為錨點。"""
    # 去掉 body 開頭的 H1（章首已渲染 title）與 context 錨 blockquote
    body = re.sub(r"^\s*#\s+.+\n", "", body, count=1)
    body = re.sub(r"^\s*>\s*book:.*\n", "", body, count=1, flags=re.M)
    secs = h2_sections(body)
    if not secs:
        return md_to_html(body)
    pre = body.split("\n## ", 1)[0] if not body.lstrip().startswith("## ") else ""
    parts = [md_to_html(pre)] if pre.strip() else []
    for title, content in secs:
        cls = SECTION_CLASS.get(norm_title(title), "body")
        sid = f"{chapter_id}-{_slug(norm_title(title))}"
        parts.append(f'<section class="section {cls}" id="{sid}"><h2>{html.escape(title)}</h2>{md_to_html(content)}</section>')
    return "\n".join(parts)


def _slug(s: str) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", s.strip()).strip("-").lower()
    return s or "s"


def render_chapter(fm: dict, body: str, path: Path, i: int, n: int, spine_cls: str) -> tuple[str, str]:
    cid = f"ch-{int(fm['chapter']):02d}"
    kicker = [f"第 {fm['chapter']} {TYPE_ZH.get(fm['type'], '章')}" if fm["type"] == "chapter" else TYPE_ZH.get(fm["type"], fm["type"]),
              f"約 {fm['est_minutes']} 分鐘", f'<span class="badge">{LEVEL_ZH.get(fm["level"], fm["level"])}</span>']
    head = f'<header class="ch-head"><div class="kicker">{" · ".join(kicker)}</div><h1>{html.escape(str(fm["title"]))}</h1></header>'
    punch = f'<div class="punchline"><small>這章的一句話</small>{html.escape(str(fm["punchline"]))}</div>' if fm["type"] != "preface" else ""
    lowc = ('<blockquote class="callout warning low-confidence"><div class="ct">注意</div><p>本章素材不足，結論待驗證（confidence: low）。</p></blockquote>'
            if fm.get("confidence") == "low" else "")
    sections = render_sections(body, cid)
    srcs = fm.get("sources") or []
    sources = ""
    if srcs:
        items = "".join(f"<li><code>{html.escape(str(s))}</code></li>" for s in srcs)
        sources = f'<details class="sources"><summary>本章依據（{len(srcs)}）</summary><ul>{items}</ul></details>'
    nav = (f'<nav class="nav"><button data-prev>‹ 上一章</button><span class="pos">{i + 1} / {n}</span>'
           f'<button data-next>下一章 ›</button></nav>')
    article = (f'<section class="chapter" id="{cid}" data-spine="{spine_cls}" data-level="{html.escape(str(fm["level"]))}">'
               f'{head}{punch}{lowc}{sections}{sources}{nav}</section>')
    stamp = f"<!-- content-src: {path.name} sha256:{sha16(path)} -->"
    return article, stamp


def render_cover(meta: dict, chapters: list[tuple[dict, Path]], total_min: int) -> str:
    outs = "".join(f"<li>{html.escape(str(o))}</li>" for o in meta.get("outcomes", []))
    toc = ""
    for fm, _ in chapters:
        cid = f"ch-{int(fm['chapter']):02d}"
        n = "序" if fm["type"] == "preface" else ("附錄" if fm["type"] == "appendix" else f"{fm['chapter']:02d}")
        toc += (f'<li><span class="n">{n}</span><a href="#{cid}" data-go="{cid}">{html.escape(str(fm["title"]))}</a>'
                f'<span class="m">{fm["est_minutes"]} 分</span></li>')
    scope = "".join(f"<li>{html.escape(str(s))}</li>" for s in meta.get("scope_out", []))
    scope_html = f'<div class="who">這本書不講</div><ul class="outs">{scope}</ul>' if scope else ""
    return (f'<section class="chapter cover" id="cover"><div class="cover">'
            f'<span class="plate">{html.escape(str(meta.get("shelf", "")).upper())} · v{meta.get("version", 1)}</span>'
            f'<h1>{html.escape(str(meta["title"]))}</h1>'
            + (f'<p class="sub">{html.escape(str(meta["subtitle"]))}</p>' if meta.get("subtitle") else "")
            + f'<p>{html.escape(str(meta.get("audience", "")))}</p>'
            f'<div class="who">讀完你會</div><ul class="outs">{outs}</ul>'
            f'{scope_html}'
            f'<div class="who">目錄</div><ul class="toc">{toc}</ul>'
            f'<div class="meta"><span>作者 {html.escape(str(meta.get("author", "")))}</span>'
            f'<span>{len(chapters)} 章 · 約 {total_min} 分鐘</span><span>更新 {meta.get("updated", "")}</span>'
            f'<span>{html.escape(str(meta.get("status", "")))}</span></div>'
            f'</div><nav class="nav"><span></span><span class="pos">封面</span><button data-next>開始閱讀 ›</button></nav></section>')


def render_sidebar(meta: dict, chapters: list[tuple[dict, Path]], spine_of: dict) -> str:
    items = [f'<button class="spine c-brown" type="button"><span class="n">封</span><span class="t">封面</span></button>']
    for fm, _ in chapters:
        n = "序" if fm["type"] == "preface" else ("附" if fm["type"] == "appendix" else f"{fm['chapter']:02d}")
        items.append(f'<button class="spine {spine_of[int(fm["chapter"])]}" type="button">'
                     f'<span class="n">{n}</span><span class="t">{html.escape(str(fm["title"]))}</span>'
                     f'<span class="m">{fm["est_minutes"]}′</span></button>')
    return "\n    ".join(items)


# ── 風格（manifest 驅動，可擴充）────────────────────────────────────────

def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"default": "library", "styles": [{"name": p.stem} for p in STYLES_DIR.glob("*.css")]}


def style_names() -> list[str]:
    return [s["name"] for s in load_manifest().get("styles", [])]


def load_style(style: str, styles_ref: Path | None) -> tuple[str, str]:
    """回傳 (css, body_attr)。優先讀 assets/styles/{style}.css；找不到時嘗試從 ark-html-report 的 styles.md 借 token。"""
    css_path = STYLES_DIR / f"{style}.css"
    if css_path.exists():
        dark = next((s.get("dark") for s in load_manifest().get("styles", []) if s["name"] == style), False)
        return css_path.read_text(encoding="utf-8"), (' data-theme="dark"' if dark else "")
    if styles_ref and styles_ref.exists():
        text = styles_ref.read_text(encoding="utf-8")
        m = re.search(rf"^##\s+\d+\.\s+{re.escape(style)}\b.*?```css\n(.*?)```", text, re.S | re.M)
        if m:
            tokens = m.group(1) + "\n:root{--oak:#2b2f36;--oak-dark:#1c1f24;--brass:var(--warn);--brass-2:var(--warn);}"
            return tokens, ' data-theme="dark"' if style == "midnight" else ""
    sys.exit(f"找不到風格 `{style}`。可用：{', '.join(style_names())}（或 --styles-ref 指向 ark-html-report/references/styles.md）")


# ── build / check ──────────────────────────────────────────────────────────

def load_book(book_dir: Path) -> tuple[dict, list[tuple[dict, Path, str]]]:
    meta = load_yaml_text((book_dir / "book.yaml").read_text(encoding="utf-8"))
    order = [str(c) for c in meta.get("chapters", [])]
    files = {p.stem: p for p in book_dir.glob("*.md") if FILENAME_RE.match(p.name)}
    chapters = []
    for stem in order:
        p = files.get(stem)
        if not p:
            sys.exit(f"book.yaml chapters 有 `{stem}` 但檔案不存在（先跑 book_lint.py）")
        fm, body = split_frontmatter(p.read_text(encoding="utf-8"))
        chapters.append((fm, p, body))
    return meta, chapters


def build(book_dir: Path, out: Path | None, style: str, styles_ref: Path | None) -> Path:
    meta, chapters = load_book(book_dir)
    style_css, body_attr = load_style(style, styles_ref)
    tpl = TEMPLATE.read_text(encoding="utf-8")

    spine_of: dict[int, str] = {}
    k = 0
    for fm, _, _ in chapters:
        n = int(fm["chapter"])
        if fm["type"] == "preface":
            spine_of[n] = "c-brown"
        elif fm["type"] == "appendix":
            spine_of[n] = "c-brass"
        else:
            spine_of[n] = SPINE_CYCLE[k % len(SPINE_CYCLE)]
            k += 1
    cover_color = (meta.get("cover") or {}).get("spine_color") if isinstance(meta.get("cover"), dict) else None
    if cover_color:
        for n, fm in [(int(f["chapter"]), f) for f, _, _ in chapters]:
            if fm["type"] == "chapter":
                spine_of[n] = f"c-{cover_color}"

    total_min = sum(int(fm["est_minutes"]) for fm, _, _ in chapters)
    pairs = [(fm, p) for fm, p, _ in chapters]
    n = len(chapters) + 1
    articles = [render_cover(meta, pairs, total_min)]
    stamps = []
    for i, (fm, p, body) in enumerate(chapters, start=1):
        a, s = render_chapter(fm, body, p, i, n, spine_of[int(fm["chapter"])])
        articles.append(a)
        stamps.append(s)
    built = datetime.now(TZ).isoformat(timespec="seconds")
    stamps.append(f"<!-- book-src: book.yaml sha256:{sha16(book_dir / 'book.yaml')} chapters:{len(chapters)} built:{built} -->")

    desc = f"{meta.get('audience', '')}".strip()
    page = (tpl.replace("{{LANG}}", str(meta.get("language", "zh-Hant")))
            .replace("{{TITLE}}", html.escape(str(meta["title"])))
            .replace("{{DESCRIPTION}}", html.escape(desc))
            .replace("{{STYLE_CSS}}", style_css)
            .replace("{{STYLE}}", html.escape(style))
            .replace("{{BODY_ATTR}}", body_attr)
            .replace("{{SHELF_META}}", f"{len(chapters)} 章 · 約 {total_min} 分鐘 · v{meta.get('version', 1)}")
            .replace("{{SIDEBAR}}", render_sidebar(meta, pairs, spine_of))
            .replace("{{CHAPTERS}}", "\n".join(articles))
            .replace("{{FOOT_LEFT}}", f"{html.escape(str(meta['title']))} · v{meta.get('version', 1)} · {meta.get('updated', '')}")
            .replace("{{FOOT_RIGHT}}", f"Content 軌：books/{meta['slug']}/ · 由 ark-book 產生，請勿手改此檔")
            .replace("{{SLUG}}", str(meta["slug"]))
            .replace("{{VERSION}}", str(meta.get("version", 1)))
            .replace("{{STAMPS}}", "\n".join(stamps)))
    out = out or (book_dir / "site" / "index.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out


STAMP_RE = re.compile(r"<!--\s*content-src:\s*(\S+)\s+sha256:([0-9a-f]{16})\s*-->")
BOOK_STAMP_RE = re.compile(r"<!--\s*book-src:\s*book\.yaml\s+sha256:([0-9a-f]{16})\s+chapters:(\d+)\s+built:(\S+)\s*-->")


def check(book_dir: Path, site: Path | None) -> dict:
    site = site or (book_dir / "site" / "index.html")
    if not site.exists():
        return {"status": "NO-SITE", "site": str(site), "stale": []}
    text = site.read_text(encoding="utf-8")
    stamps = dict(STAMP_RE.findall(text))
    bm = BOOK_STAMP_RE.search(text)
    if not stamps or not bm:
        return {"status": "NO-STAMP", "site": str(site), "stale": []}
    stale = []
    for p in sorted(book_dir.glob("*.md")):
        if not FILENAME_RE.match(p.name):
            continue
        if stamps.get(p.name) != sha16(p):
            stale.append(p.name)
    if bm.group(1) != sha16(book_dir / "book.yaml"):
        stale.append("book.yaml")
    return {"status": "OK" if not stale else "STALE", "site": str(site), "stale": stale, "built": bm.group(3)}


def main(argv: list[str]) -> int:
    if "-h" in argv or "--help" in argv:
        print(__doc__)
        return 0
    if "--list-styles" in argv:
        mf = load_manifest()
        for st in mf.get("styles", []):
            mark = "*" if st["name"] == mf.get("default") else " "
            print(f"{mark} {st['name']:<9} {st.get('label', ''):<4} {'dark ' if st.get('dark') else 'light'}  {st.get('use_for', '')}")
        return 0
    if not argv or argv[0].startswith("--"):
        print(__doc__)
        return 2
    book_dir = Path(argv[0])
    if not (book_dir / "book.yaml").exists():
        sys.exit(f"找不到 {book_dir / 'book.yaml'}")

    def opt(name: str) -> str | None:
        return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else None

    out = Path(opt("--out")) if opt("--out") else None
    if "--check" in argv:
        res = check(book_dir, out)
        if "--json" in argv:
            print(json.dumps(res, ensure_ascii=False))
        else:
            print(f"{res['status']}  {res['site']}" + (f"  stale: {', '.join(res['stale'])}" if res.get("stale") else ""))
        return 0 if res["status"] == "OK" else 1

    meta_style = load_yaml_text((book_dir / "book.yaml").read_text(encoding="utf-8")).get("style")
    style = opt("--style") or meta_style or load_manifest().get("default", "library")
    styles_ref = Path(opt("--styles-ref")) if opt("--styles-ref") else None
    path = build(book_dir, out, style, styles_ref)
    res = check(book_dir, out)
    print(f"built  {path}  ({path.stat().st_size // 1024} KB)  style: {style}  pair: {res['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
