#!/usr/bin/env python3
"""gs_bundle — 競品分析 md ＋ gdd-pack（＋其他 md）→ 一份圖文自包含的單檔 HTML（零外部請求、檔案小）。

做法：gdd-pack 以 gdd_build 產出素材總覽頁當外殼（沒有 gdd 段時用內建簡版外殼），md 段渲染後插到外殼的
nav 與 main（gdd 段之前的 md 放前面、之後的放後面），最後交給 ark-html-report 的 html_images.embed：
圖片依用途縮圖 → WebP → 依內容去重 → 內嵌（map 模式，燈箱 gallery JSON 的 src 也改成 __img: 參照）。

bundle.yaml（路徑一律相對於 yaml 所在目錄）：
  bundle: "1"
  title: 賭博默示錄 競品分析與規格書        # <title> 與頁首導覽列標題
  out: 賭博默示錄_競品分析與規格書.html      # 預設 <title 清檔名>.html
  quality: standard                          # lite | standard | hi
  budget_mb: 6                               # 超過 → exit 3
  format: webp                               # webp | jpeg
  roles: {"symbols/*": icon}                 # 選填；依路徑指定用途（gdd 段預設已帶 symbols/*=icon）
  parts:
    - {kind: md,  id: analysis, label: 競品分析, path: ../../docs/reports/data/xxx.md}
    - {kind: gdd, id: spec, label: 遊戲規格書, pack: ../gdd/<slug>}

md 圖片 `![說明](路徑)`：先找 md 所在目錄，再找 gdd 素材根（可直接寫 symbols/xxx.png 與規格書共用同一份圖）。
mermaid 區塊保留為原始碼（單檔不載外部 JS）。md 內不得有 <script>/<iframe>/on*= → BAD_INPUT。

deterministic：同輸入 bit-identical；尾端戳記 <!-- gs-bundle: … --> 記各來源 sha16，--check 驗是否過期（STALE → exit 3）。

用法:
  python gs_bundle.py --bundle <bundle.yaml> [--out <html>] [--quality lite|standard|hi] [--budget-mb N]
  python gs_bundle.py --bundle <bundle.yaml> --check
"""
from __future__ import annotations

import argparse
import hashlib
import html as H
import json
import os
import pathlib
import re
import sys
import tempfile
from urllib.parse import quote, unquote

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "gdd"))
import gdd_common as C  # noqa: E402
import gdd_build  # noqa: E402

CONTRACT = "1"
STAMP_RE = re.compile(r"<!-- gs-bundle: (.+?) -->")
FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
MD_IMG_RE = re.compile(r'(<img\b[^>]*?\ssrc=")([^"]+)(")', re.I)
HEAD_RE = re.compile(r"<(/?)h([1-6])\b", re.I)
DEFAULT_ROLES = {"symbols/*": "icon"}
FM_SHOW = ("date", "author", "verdict", "confidence", "provenance", "source")


def html_images():
    """sibling skill ark-html-report 的放圖引擎；找不到 → MISSING_DEP。"""
    cands = [C.SKILL_DIR.parent / "ark-html-report" / "scripts"]
    if os.environ.get("ARK_HTML_REPORT_DIR"):
        cands.insert(0, pathlib.Path(os.environ["ARK_HTML_REPORT_DIR"]) / "scripts")
    for c in cands:
        if (c / "html_images.py").exists():
            sys.path.insert(0, str(c))
            import html_images  # type: ignore
            return html_images
    C.fail("MISSING_DEP", "找不到 ark-html-report/scripts/html_images.py（需 ark-html-report ≥ 1.2.0）",
           "安裝 ark-html-report 到 ark-game-spec 同層，或設 ARK_HTML_REPORT_DIR")


def sha16(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def safe_name(t: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s]+', "_", t).strip("_") or "bundle"


# ── 設定 ─────────────────────────────────────────────────────────────

def load_cfg(path: pathlib.Path) -> dict:
    cfg = C.yaml_load(path) or {}
    base = path.parent.resolve()
    parts = cfg.get("parts") or []
    if not parts:
        C.fail("BAD_INPUT", "bundle.yaml 需要 parts（至少一段 md 或 gdd）")
    seen, out = set(), []
    for i, pt in enumerate(parts):
        kind = pt.get("kind")
        if kind not in ("md", "gdd"):
            C.fail("BAD_INPUT", f"parts[{i}].kind 必須是 md 或 gdd：{kind}")
        pid = str(pt.get("id") or f"p{i + 1}")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", pid) or pid in seen:
            C.fail("BAD_INPUT", f"parts[{i}].id 需唯一且只含英數 _ -：{pid}")
        seen.add(pid)
        src = pt.get("path") if kind == "md" else pt.get("pack")
        if not src:
            C.fail("BAD_INPUT", f"parts[{i}] 缺 {'path' if kind == 'md' else 'pack'}")
        sp = (base / src).resolve()
        if kind == "md" and not sp.is_file():
            C.fail("BAD_INPUT", f"找不到 md：{sp}")
        if kind == "gdd":
            sp = C.pack_dir(str(sp))
        out.append({**pt, "id": pid, "kind": kind, "src": sp})
    if sum(p["kind"] == "gdd" for p in out) > 1:
        C.fail("BAD_INPUT", "一份 bundle 最多一段 gdd（素材總覽頁是外殼）")
    title = str(cfg.get("title") or "報告")
    o = cfg.get("out")
    return {"title": title, "subtitle": cfg.get("subtitle"), "base": base, "yaml": path.resolve(), "parts": out,
            "out": (base / o).resolve() if o else base / (safe_name(title) + ".html"),
            "quality": cfg.get("quality", "standard"), "budget_mb": float(cfg.get("budget_mb", 8)),
            "format": cfg.get("format", "webp"), "roles": {**DEFAULT_ROLES, **(cfg.get("roles") or {})},
            "style": (base / cfg["style"]).resolve() if cfg.get("style") else None}


# ── md 段 ────────────────────────────────────────────────────────────

def md_render(text: str) -> tuple[str, dict, str | None]:
    """回傳 (html, front_matter, 第一個 h1 文字)。h1 拿掉（當段名候選），其餘標題降一級（h2→h3…），mermaid 保留原始碼。"""
    fm = {}
    m = FM_RE.match(text)
    if m:
        try:
            import yaml  # type: ignore
            fm = yaml.safe_load(m.group(1)) or {}
        except Exception:
            fm = {}
        text = text[m.end():]
    h1 = None
    mh = re.search(r"^# (.+)$", text, re.M)
    if mh:
        h1 = mh.group(1).strip()
        text = text[:mh.start()] + text[mh.end():]
    text = re.sub(r"```mermaid\n(.*?)```", lambda x: "\n<pre class=\"bp-mermaid\" title=\"mermaid 原始碼\">"
                  + H.escape(x.group(1)) + "</pre>\n", text, flags=re.S)
    try:
        import markdown  # type: ignore
        body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"], output_format="html")
    except ImportError:
        body = C.md_to_html(text)
    body = HEAD_RE.sub(lambda x: f"<{x.group(1)}h{min(6, int(x.group(2)) + 1)}", body)
    body = re.sub(r"<table>", '<div class="tbl-wrap"><table>', body).replace("</table>", "</table></div>")
    return body, fm, h1


def md_part(pt: dict, img_roots: list[pathlib.Path], base: pathlib.Path) -> dict:
    text = pt["src"].read_text(encoding="utf-8")
    body, fm, h1 = md_render(text)
    if C.INJECT_RE.search(re.sub(r"<pre class=\"bp-mermaid\".*?</pre>", "", body, flags=re.S)):
        C.fail("BAD_INPUT", f"md 段 {pt['id']} 含 <script>/<iframe>/on*= 等可執行內容", "拿掉 md 內的原生 HTML")
    missing: list[str] = []

    def fix(m):
        u = H.unescape(m.group(2))
        if re.match(r"^(https?:|data:|#)", u):
            return m.group(0)
        rel = unquote(u)
        for root in [pt["src"].parent, *img_roots]:
            f = (root / rel).resolve()
            if f.is_file():
                try:
                    url = pathlib.PurePath(os.path.relpath(f, base)).as_posix()
                except ValueError:                       # Windows 跨磁碟
                    url = f.as_posix()
                return m.group(1) + quote(url, safe="/:._-") + m.group(3)
        missing.append(u)
        return m.group(0)

    body = MD_IMG_RE.sub(fix, body)
    if missing:
        C.fail("BAD_INPUT", f"md 段 {pt['id']} 有 {len(missing)} 張圖找不到", "路徑相對 md 所在目錄或 gdd 素材根", {"missing": missing[:20]})
    label = pt.get("label") or pt.get("title") or h1 or pt["id"]
    title = pt.get("title") or h1 or label
    meta = "".join(f"<span><i>{H.escape(k)}</i>{H.escape(str(fm[k]))}</span>" for k in FM_SHOW if fm.get(k))
    sec = (f'<section class="bp" id="part-{pt["id"]}" data-part="md">\n<h2 class="bp-title">{H.escape(str(title))}</h2>\n'
           + (f'<div class="bp-meta">{meta}</div>\n' if meta else "") + f'<div class="bp-body">\n{body}\n</div>\n</section>')
    return {"id": pt["id"], "label": str(label), "html": sec, "sha": sha16(pt["src"]), "src": str(pt["src"])}


BP_CSS = """<style id="gs-bundle-css">
.bp{margin:8px 0 40px}
.bp-title{scroll-margin-top:64px}
.bp-meta{display:flex;flex-wrap:wrap;gap:6px 14px;margin:-4px 0 14px;font-size:13px;color:var(--muted,#888)}
.bp-meta i{font-style:normal;opacity:.7;margin-right:6px}
.bp-body{line-height:1.75;max-width:1100px}
.bp-body h3{margin:26px 0 10px}.bp-body h4{margin:18px 0 8px}
.bp-body blockquote{margin:12px 0;padding:8px 14px;border-left:3px solid var(--gold,#c9a227);background:var(--panel2,rgba(127,127,127,.08));border-radius:0 6px 6px 0}
.bp-body blockquote p{margin:4px 0}
.bp-body code{font-family:var(--font-mono,ui-monospace,monospace);font-size:.9em;padding:1px 5px;border-radius:4px;background:var(--panel2,rgba(127,127,127,.12))}
.bp-body pre{overflow:auto;padding:12px 14px;border-radius:8px;background:var(--panel2,rgba(127,127,127,.1));border:1px solid var(--line,rgba(127,127,127,.25))}
.bp-body pre code{background:none;padding:0}
.bp-body img{max-width:100%}
.bp-mermaid{white-space:pre;font-size:12px;opacity:.85}
nav a.bp-nav{opacity:.95;font-weight:600}
.bp-cover{max-width:1400px;margin:0 auto;padding:10px 20px 0;font-size:13px;color:var(--muted,#888)}
.bp-cover b{color:inherit}
</style>"""

SHELL = """<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root{{--bg:#fafaf7;--fg:#1f2328;--muted:#6b7280;--line:#e5e2da;--panel:#fff;--panel2:#f3f1ea;--gold:#b7791f;--font-mono:ui-monospace,Menlo,Consolas,monospace}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16161a;--fg:#e6e3dc;--muted:#9a968c;--line:#2e2c29;--panel:#1d1c20;--panel2:#24232a;--gold:#e0b453}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.7 system-ui,-apple-system,"Noto Sans TC","Microsoft JhengHei",sans-serif}}
header{{max-width:1100px;margin:0 auto;padding:28px 20px 6px}}header h1{{margin:0;font-size:26px}}header .sub{{color:var(--muted)}}
nav{{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:8px 20px;display:flex;gap:16px;flex-wrap:wrap}}
nav a{{color:var(--gold);text-decoration:none}}main{{max-width:1100px;margin:0 auto;padding:10px 20px 40px}}
table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{border:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top}}th{{background:var(--panel2)}}
.tbl-wrap{{overflow-x:auto;margin:10px 0}}h2{{border-bottom:2px solid var(--line);padding-bottom:6px;margin-top:34px}}
footer{{max-width:1100px;margin:0 auto;padding:20px;color:var(--muted);font-size:12px;border-top:1px solid var(--line)}}
</style>
</head><body>
<header><h1>{title}</h1>{sub}</header>
<nav>
</nav>
<main>
</main>
<footer>{title}</footer>
</body></html>
"""


# ── 組裝 ─────────────────────────────────────────────────────────────

def gdd_shell(pt: dict, base: pathlib.Path, style) -> tuple[str, dict, pathlib.Path]:
    p = C.load_pack(pt["src"])
    root = p["assets"]["root"]
    try:
        rel = pathlib.PurePath(os.path.relpath(root, base)).as_posix()
    except ValueError:
        rel = root.as_posix()
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td) / "gdd.html"
        b = gdd_build.build(pt["src"], tmp, style, assets={"root_rel": rel}, write_todo=False)
        text = tmp.read_text(encoding="utf-8")
    # 燈箱讀 GALLERY.src：內嵌後是 __img:<key>，交給 __imgsrc 解析（沒內嵌時原樣）
    text = text.replace("lbImg.src = d.src;", "lbImg.src = (window.__imgsrc || (s => s))(d.src);")
    return text, {"stamp": b["stamp"], "pack": str(pt["src"])}, root


def assemble(cfg: dict) -> tuple[str, dict]:
    base = cfg["out"].parent
    base.mkdir(parents=True, exist_ok=True)              # 相對路徑含 ..，基準目錄須存在才解得開
    gi = next((i for i, p in enumerate(cfg["parts"]) if p["kind"] == "gdd"), None)
    img_roots: list[pathlib.Path] = []
    gdd_info = None
    if gi is not None:
        shell, gdd_info, root = gdd_shell(cfg["parts"][gi], base, cfg["style"])
        img_roots.append(root)
        gdd_label = cfg["parts"][gi].get("label")
    else:
        sub = f'<div class="sub">{H.escape(str(cfg["subtitle"]))}</div>' if cfg.get("subtitle") else ""
        shell, gdd_label = SHELL.format(title=H.escape(cfg["title"]), sub=sub), None
    mds = [(i, md_part(p, img_roots, base)) for i, p in enumerate(cfg["parts"]) if p["kind"] == "md"]
    before = [m for i, m in mds if gi is None or i < gi]
    after = [m for i, m in mds if gi is not None and i > gi]
    nav_b = "".join(f'<a class="bp-nav" href="#part-{m["id"]}">{H.escape(m["label"])}</a>' for m in before)
    nav_a = "".join(f'<a class="bp-nav" href="#part-{m["id"]}">{H.escape(m["label"])}</a>' for m in after)
    t = shell
    t = re.sub(r"<title>.*?</title>", f"<title>{H.escape(cfg['title'])}</title>", t, count=1, flags=re.S)
    t = t.replace("</head>", BP_CSS + "\n</head>", 1)
    if gi is not None:
        if '<a href="#rule">' not in t or '<input id="q"' not in t:
            C.fail("GATE_BLOCKED", "素材總覽模板缺 nav 錨點（#rule / #q），無法插入 md 段", "確認 assets/gdd-template.html.j2 版本")
        t = t.replace('<a href="#rule">', nav_b + '<a class="bp-nav" href="#rule">', 1)
        if gdd_label:
            t = t.replace('<a class="bp-nav" href="#rule">遊戲規格</a>', f'<a class="bp-nav" href="#rule">{H.escape(gdd_label)}</a>', 1)
        t = t.replace('<input id="q"', nav_a + '<input id="q"', 1)
        parts_line = "｜".join([m["label"] for m in before] + [gdd_label or "遊戲規格書"] + [m["label"] for m in after])
        t = t.replace("</header>", f"</header>\n<div class=\"bp-cover\">本檔收錄：<b>{H.escape(parts_line)}</b></div>", 1)
    else:
        t = t.replace("<nav>\n", "<nav>\n" + nav_b + "\n", 1)
    t = t.replace("<main>", "<main>\n" + "\n".join(m["html"] for m in before), 1)
    t = t.replace("</main>", "\n".join(m["html"] for m in after) + "\n</main>", 1)
    stamp_parts = [f"yaml:{sha16(cfg['yaml'])}"] + [f"md-{m['id']}:{m['sha']}" for _, m in mds]
    if gdd_info:
        stamp_parts.append("gdd[" + gdd_info["stamp"] + "]")
    stamp_parts.append(f"q:{cfg['quality']}/{cfg['format']}")
    stamp = "<!-- gs-bundle: " + " ".join(stamp_parts) + " -->"
    return t, {"stamp": stamp, "md_parts": [m["id"] for _, m in mds], "gdd": gdd_info}


def build(cfg: dict) -> dict:
    HI = html_images()
    text, info = assemble(cfg)
    base = cfg["out"].parent
    try:
        out_html, rep = HI.embed(text, base, quality=cfg["quality"], fmt=cfg["format"], mode="map",
                                 budget_mb=cfg["budget_mb"], do_layout=True, lightbox=True, json_src=True,
                                 role_rules=cfg["roles"])
    except HI.EmbedError as e:
        C.fail(e.code, f"放圖失敗：{e}", "調 quality: lite、roles 指定用途，或拿掉不必要的圖" if e.code == "GATE_BLOCKED" else "", e.data)
    # 守門：不得殘留本機圖片連結
    left = [u for u in re.findall(r'(?:src|href)="([^"]+)"', out_html) if HI.is_image_ref(u) and not u.startswith(("data:", "http"))]
    if left:
        C.fail("GATE_BLOCKED", f"內嵌後仍有 {len(left)} 個本機圖片連結", "", {"left": left[:10]})
    out_html = out_html.replace("</body>", info["stamp"] + "\n</body>", 1) if "</body>" in out_html else out_html + info["stamp"]
    cfg["out"].parent.mkdir(parents=True, exist_ok=True)
    C.atomic_write(cfg["out"], out_html)
    rep.pop("all", None)
    manifest = {"contract": CONTRACT, "out": str(cfg["out"]), "title": cfg["title"], "parts": [
        {"id": p["id"], "kind": p["kind"], "src": str(p["src"])} for p in cfg["parts"]], "stamp": info["stamp"][15:-4],
        "images": rep}
    mp = cfg["out"].with_suffix(".bundle.json")
    C.atomic_write(mp, json.dumps(manifest, ensure_ascii=False, indent=1))
    return {"out": str(cfg["out"]), "manifest": str(mp), "html_mb": rep["html_mb"], "images": rep["images"],
            "references": rep["references"], "src_mb": rep["src_mb"], "embedded_mb": rep["embedded_mb"],
            "duplicates_saved": rep["duplicates_saved"], "mode": rep["mode"], "quality": cfg["quality"],
            "parts": [p["id"] for p in cfg["parts"]], "budget_mb": cfg["budget_mb"],
            "delivery": f"{cfg['out'].name}｜{len(cfg['parts'])} 段｜{rep['images']} 張圖（{rep['references']} 處引用）"
                        f"｜原圖 {rep['src_mb']} MB → 內嵌 {rep['embedded_mb']} MB｜HTML {rep['html_mb']} MB（預算 {cfg['budget_mb']}）"}


def check(cfg: dict) -> tuple[str, str]:
    out = cfg["out"]
    if not out.exists():
        return "NO-HTML", str(out)
    tail = out.read_bytes()[-4096:].decode("utf-8", "replace")
    m = STAMP_RE.search(tail)
    if not m:
        return "NO-STAMP", str(out)
    _, info = assemble(cfg)
    return ("OK" if m.group(0) == info["stamp"] else "STALE"), str(out)


def main() -> None:
    ap = argparse.ArgumentParser(description="ark-game-spec bundle：md + gdd-pack → 圖文自包含單檔 HTML", allow_abbrev=False)
    ap.add_argument("--bundle", required=True, help="bundle.yaml")
    ap.add_argument("--out")
    ap.add_argument("--quality", choices=["lite", "standard", "hi"])
    ap.add_argument("--budget-mb", type=float)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    y = pathlib.Path(a.bundle)
    if not y.is_file():
        C.fail("BAD_INPUT", f"找不到 {y}")
    cfg = load_cfg(y)
    if a.out:
        cfg["out"] = pathlib.Path(a.out).resolve()
    if a.quality:
        cfg["quality"] = a.quality
    if a.budget_mb:
        cfg["budget_mb"] = a.budget_mb
    if a.check:
        st, path = check(cfg)
        if st != "OK":
            C.fail("GATE_BLOCKED", f"{st}：{path}", "重跑 gs_bundle", {"status": st})
        C.emit({"status": st, "html": path}, {"stage": "bundle_check"})
        return
    C.emit(build(cfg), {"stage": "bundle"})


if __name__ == "__main__":
    main()
