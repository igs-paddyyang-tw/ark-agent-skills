#!/usr/bin/env python3
"""html_images — 報告「放圖」引擎：把 HTML 裡引用的本機圖片依用途縮圖、轉檔、去重後內嵌，產出零外部請求的單檔 HTML。

為什麼：一張遊戲截圖原檔 1080×1920 PNG 動輒 2～3 MB；直接 base64 內嵌，十幾張就幾十 MB。
依用途縮到「頁面上實際顯示的尺寸 ×2 以內」並轉 WebP，通常只剩原本的 2～5%（實測 KAIJI 示意圖 36 張 95 MB → 2.1 MB）。

會處理的引用（路徑相對 --base，或絕對路徑；http(s)/data:/// 一律不動並列為外部）：
  <img src="…">、<a href="…圖檔">、<source srcset="單一路徑">、JSON 字串 "src":"…"（燈箱 / gallery 資料，--no-json-src 關閉）

用途（data-role 屬性；沒寫就依原圖尺寸自動判斷）：
  icon         長邊 ≤ 400 的小圖（圖騰、圖示）            → 寬 ≤ 240
  portrait     直式截圖（高 ≥ 1.3 × 寬）                    → 寬 ≤ 560
  landscape    其他截圖 / 照片                              → 寬 ≤ 800
  diagram      圖表、流程圖（色少、要銳利）                 → 寬 ≤ 1200，WebP 無損或 PNG
  full         不縮
品質檔：lite（寬 ×0.65、q55）／standard（q65）／hi（寬 ×1.5、q80）。

內嵌方式：
  uri   每個引用直接換成 data URI（零 JS；同一張圖被引用多次就重複多份）
  map   圖只存一份於 window.__IMG，<img data-img="k"> 由頁尾一小段 script 回填；JSON src 改成 "__img:k"，
        頁面 JS 用 window.__imgsrc(s) 解析（ark-game-spec 的燈箱已支援）
  auto  （預設）沒有重複引用且沒有 JSON 引用 → uri；否則 → map

放圖輔助（--layout）：獨立成段的 <img> 包成 <figure class="ar-fig ar-{role}">（alt 當圖說），
連續兩張以上自動排成 .ar-gallery 格狀；--lightbox 加一個點圖放大的極簡燈箱。CSS 只用 token 變數（有 fallback）。

守門：缺檔 → exit 2；內嵌後超過 --budget-mb → exit 3（列出前 10 大張圖）。同輸入同參數 → 輸出逐位元相同。

用法:
  python html_images.py embed report.html [--base <dir>] [--out report.inline.html] [--quality lite|standard|hi]
         [--format webp|jpeg] [--mode auto|uri|map] [--budget-mb 8] [--layout] [--lightbox] [--manifest images.json]
  python html_images.py inspect report.html [--base <dir>]      # 只列出引用與預估大小，不寫檔
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html as _html
import io
import json
import pathlib
import re
import sys
from urllib.parse import unquote

VERSION = "1.1.0"
EXIT = {"BAD_INPUT": 2, "GATE_BLOCKED": 3, "MISSING_DEP": 8}
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".bmp")
ROLES = ("icon", "portrait", "landscape", "diagram", "full")
WIDTH = {"icon": 240, "portrait": 560, "landscape": 800, "diagram": 1200, "full": None}
TIERS = {"lite": (0.65, 55), "standard": (1.0, 65), "hi": (1.5, 80)}

ATTR_RE = re.compile(r'(<(?:img|source|a)\b[^>]*?\s)(src|href|srcset)=("([^"]*)"|\'([^\']*)\')', re.I | re.S)
TAG_ROLE_RE = re.compile(r'\sdata-role=["\'](\w+)["\']', re.I)
JSON_SRC_RE = re.compile(r'("src"\s*:\s*")([^"]+)(")')
EXTERNAL = ("http://", "https://", "data:", "//", "#", "mailto:", "javascript:", "__img:")


# ── envelope ──────────────────────────────────────────────────────────────

def _utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass


def emit(data):
    _utf8()
    print(json.dumps({"success": True, "contract": "1", "data": data, "meta": {"skill": "ark-html-report", "skill_version": VERSION}}, ensure_ascii=False))


def fail(code, message, hint="", data=None):
    _utf8()
    print(json.dumps({"success": False, "contract": "1", "error": {"code": code, "message": message, "hint": hint}, "data": data}, ensure_ascii=False))
    sys.exit(EXIT.get(code, 1))


class EmbedError(Exception):
    def __init__(self, code: str, message: str, data=None):
        super().__init__(message)
        self.code, self.data = code, data


# ── 影像處理 ──────────────────────────────────────────────────────────────

def _pil():
    try:
        from PIL import Image  # type: ignore
        return Image
    except ImportError as e:
        raise EmbedError("MISSING_DEP", "需要 Pillow（pip install Pillow）") from e


def is_image_ref(u: str) -> bool:
    return unquote(u.split("?")[0].split("#")[0]).lower().endswith(IMG_EXT)


def resolve(u: str, base: pathlib.Path) -> pathlib.Path:
    p = pathlib.Path(unquote(u.split("?")[0].split("#")[0]))
    return p if p.is_absolute() else (base / p)


def auto_role(w: int, h: int) -> str:
    if max(w, h) <= 400:
        return "icon"
    if h >= 1.3 * w:
        return "portrait"
    return "landscape"


def encode(path: pathlib.Path, role: str | None, quality: str, fmt: str) -> dict:
    """回傳 {mime, data, w, h, role, src_bytes, out_bytes}；deterministic（無 metadata、固定參數）。"""
    raw = path.read_bytes()
    ext = path.suffix.lower()
    if ext == ".svg":
        return {"mime": "image/svg+xml", "data": raw, "w": None, "h": None, "role": role or "diagram", "src_bytes": len(raw), "out_bytes": len(raw)}
    Image = _pil()
    im = Image.open(io.BytesIO(raw))
    if ext == ".gif" and getattr(im, "is_animated", False):
        return {"mime": "image/gif", "data": raw, "w": im.width, "h": im.height, "role": role or "full", "src_bytes": len(raw), "out_bytes": len(raw)}
    w0, h0 = im.size
    role = role if role in ROLES else auto_role(w0, h0)
    scale, q = TIERS[quality]
    maxw = WIDTH[role]
    if maxw:
        maxw = int(maxw * scale) if role != "icon" or scale < 1 else maxw
        if w0 > maxw:
            im = im.resize((maxw, max(1, round(h0 * maxw / w0))), Image.LANCZOS)
    alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
    im = im.convert("RGBA" if alpha else "RGB")
    buf = io.BytesIO()
    if fmt == "webp":
        if role == "diagram":
            im.save(buf, "WEBP", lossless=True, quality=100, method=6)
        else:
            im.save(buf, "WEBP", quality=q, method=6)
        mime = "image/webp"
    else:
        if alpha or role == "diagram":
            im.save(buf, "PNG", optimize=True)
            mime = "image/png"
        else:
            im.save(buf, "JPEG", quality=q + 10, optimize=True, progressive=False)
            mime = "image/jpeg"
    data = buf.getvalue()
    if len(data) >= len(raw) and ext in (".png", ".jpg", ".jpeg", ".webp") and (not maxw or w0 <= maxw):
        mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}[ext]
        data = raw                                     # 原圖已經比較小就用原圖
    return {"mime": mime, "data": data, "w": im.width, "h": im.height, "role": role, "src_bytes": len(raw), "out_bytes": len(data)}


def data_uri(e: dict) -> str:
    return f"data:{e['mime']};base64," + base64.b64encode(e["data"]).decode("ascii")


# ── 放圖輔助 ──────────────────────────────────────────────────────────────

LAYOUT_CSS = """
<style id="ar-fig-css">
.ar-fig{margin:16px auto;text-align:center}
.ar-fig img{max-width:100%;height:auto;border-radius:var(--radius,10px);border:1px solid var(--border,var(--line,#e3e1dc));background:var(--surface,var(--card,#fff))}
.ar-fig.ar-portrait img{max-width:min(100%,360px)}
.ar-fig.ar-icon img{max-width:min(100%,160px);border:none;background:none}
.ar-fig.ar-landscape img,.ar-fig.ar-diagram img{width:100%}
.ar-fig figcaption{font-size:13px;color:var(--text-muted,var(--muted,#5d5d63));margin-top:6px}
.ar-gallery{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));margin:16px 0}
.ar-gallery .ar-fig{margin:0}
.ar-gallery .ar-fig.ar-portrait img{max-width:100%}
.ar-gallery.ar-icons{grid-template-columns:repeat(auto-fill,minmax(110px,1fr))}
</style>"""

LIGHTBOX = """
<div id="ar-lb" hidden style="position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,.85);display:flex;align-items:center;justify-content:center;cursor:zoom-out">
<img alt="" style="max-width:94vw;max-height:94vh;border-radius:8px"></div>
<script>(function(){var lb=document.getElementById('ar-lb'),im=lb.querySelector('img');
document.addEventListener('click',function(e){var t=e.target;if(t.tagName==='IMG'&&t.closest('.ar-fig')){im.src=t.currentSrc||t.src;lb.hidden=false;lb.style.display='flex';}});
lb.addEventListener('click',function(){lb.hidden=true;lb.style.display='none';});
document.addEventListener('keydown',function(e){if(e.key==='Escape'){lb.hidden=true;lb.style.display='none';}});lb.style.display='none';})();</script>"""

_P_IMG_RE = re.compile(r'<p>\s*(<img\b[^>]*>)\s*</p>|^\s*(<img\b[^>]*>)\s*$', re.I | re.M)


def layout(html_text: str, roles: dict[str, str]) -> tuple[str, int]:
    """獨立成段的 <img> → <figure>；連續 figure → .ar-gallery。roles: src → role。"""
    n = 0

    def fig(m):
        nonlocal n
        tag = m.group(1) or m.group(2)
        src = re.search(r'src=["\']([^"\']+)["\']', tag)
        alt = re.search(r'alt=["\']([^"\']*)["\']', tag)
        role = roles.get(src.group(1), "landscape") if src else "landscape"
        n += 1
        cap = f"<figcaption>{alt.group(1)}</figcaption>" if alt and alt.group(1).strip() else ""
        return f'<figure class="ar-fig ar-{role}">{tag}{cap}</figure>'

    out = _P_IMG_RE.sub(fig, html_text)

    def gal(m):
        block = m.group(0)
        cls = "ar-gallery ar-icons" if block.count("ar-icon") == block.count("<figure") else "ar-gallery"
        return f'<div class="{cls}">{block}</div>'

    out = re.sub(r'(?:<figure class="ar-fig[^"]*">.*?</figure>\s*){2,}', gal, out, flags=re.S)
    return out, n


# ── 主流程 ────────────────────────────────────────────────────────────────

def collect(html_text: str, base: pathlib.Path, json_src: bool) -> tuple[list[tuple], list[str]]:
    """回傳 refs：[(kind, start, end, url, role_hint)]、external：[url]"""
    refs, external = [], []
    for m in ATTR_RE.finditer(html_text):
        u = m.group(4) if m.group(4) is not None else m.group(5)
        attr = m.group(2).lower()
        if attr == "href" and not is_image_ref(u):
            continue
        if attr == "srcset" and ("," in u or " " in u.strip()):
            continue
        if u.startswith(EXTERNAL):
            if u.startswith(("http://", "https://", "//")) and is_image_ref(u):
                external.append(u)
            continue
        if not is_image_ref(u):
            continue
        tag_start = m.start(1)
        tag_end = html_text.find(">", m.end())
        role = TAG_ROLE_RE.search(html_text[tag_start:tag_end + 1])
        vstart = m.start(3) + 1
        refs.append(("attr", vstart, vstart + len(u), u, role.group(1).lower() if role else None, attr))
    if json_src:
        for m in JSON_SRC_RE.finditer(html_text):
            u = m.group(2)
            if u.startswith(EXTERNAL) or not is_image_ref(u):
                continue
            refs.append(("json", m.start(2), m.end(2), u, None, "json"))
    refs.sort(key=lambda r: r[1])
    return refs, external


def _rule_role(u: str, rules: dict[str, str] | None) -> str | None:
    if not rules:
        return None
    from fnmatch import fnmatchcase
    from urllib.parse import unquote
    for pat, role in rules.items():
        if fnmatchcase(unquote(u), pat):
            return role
    return None


def parse_roles(items: list[str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for it in items or []:
        pat, _, role = it.rpartition("=")
        if not pat or role not in ROLES:
            raise EmbedError("BAD_INPUT", f"--role 格式為 <glob>=<{'|'.join(ROLES)}>：{it}")
        out[pat] = role
    return out


def embed(html_text: str, base: pathlib.Path, quality: str = "standard", fmt: str = "webp", mode: str = "auto",
          budget_mb: float | None = 8.0, do_layout: bool = False, lightbox: bool = False, json_src: bool = True,
          role_rules: dict[str, str] | None = None) -> tuple[str, dict]:
    """role_rules：{glob: role}，給沒寫 data-role 的引用（含 JSON src）依路徑指定用途，例 {"symbols/*": "icon"}。"""
    if quality not in TIERS:
        raise EmbedError("BAD_INPUT", f"quality 必須是 {list(TIERS)}")
    refs, external = collect(html_text, base, json_src)
    missing = sorted({r[3] for r in refs if not resolve(r[3], base).exists()})
    if missing:
        raise EmbedError("BAD_INPUT", f"{len(missing)} 張圖找不到", {"missing": missing[:20]})
    # 先依路徑編碼（同路徑同角色只編一次），再依輸出 bytes 去重
    enc_cache: dict[tuple, dict] = {}
    key_of: dict[int, str] = {}
    blobs: dict[str, dict] = {}
    for i, r in enumerate(refs):
        path = resolve(r[3], base).resolve()
        hint = r[4] or _rule_role(r[3], role_rules)
        ck = (str(path), hint)
        if ck not in enc_cache:
            enc_cache[ck] = encode(path, hint, quality, fmt)
        e = enc_cache[ck]
        k = hashlib.sha256(e["data"]).hexdigest()[:12]
        blobs.setdefault(k, {**e, "paths": set(), "refs": 0})
        blobs[k]["paths"].add(r[3]); blobs[k]["refs"] += 1
        key_of[i] = k
    dup = any(b["refs"] > 1 for b in blobs.values())
    has_json = any(r[0] == "json" for r in refs)
    use = mode if mode in ("uri", "map") else ("map" if (dup or has_json) else "uri")
    roles = {r[3]: blobs[key_of[i]]["role"] for i, r in enumerate(refs)}

    # 由後往前替換，位置才不會跑掉
    out = html_text
    for i in range(len(refs) - 1, -1, -1):
        kind, s, e_, u, _, attr = refs[i]
        k = key_of[i]
        if use == "uri":
            out = out[:s] + data_uri(blobs[k]) + out[e_:]
        elif kind == "json":
            out = out[:s] + f"__img:{k}" + out[e_:]
        else:
            # src="…" → data-img="k"（img/source）；a href → data-img-href
            a_start = s - 2 - len(attr)                    # value 前面固定是 attr="（或 '）
            q = out[s - 1]
            new_attr = ("data-img-href" if attr == "href" else "data-img-srcset" if attr == "srcset" else "data-img")
            out = out[:a_start] + f'{new_attr}={q}{k}{q}' + out[e_ + 1:]
    if do_layout:
        if use == "map":
            key_roles = {k: b["role"] for k, b in blobs.items()}
            out, n_fig = _layout_map(out, key_roles)
        else:
            uri_roles = {data_uri(b): b["role"] for b in blobs.values()}
            out, n_fig = layout(out, uri_roles)
    else:
        n_fig = 0
    head_add = LAYOUT_CSS if do_layout else ""
    if head_add:
        out = out.replace("</head>", head_add + "\n</head>", 1) if "</head>" in out else head_add + out
    if use == "map":
        table = ",".join(f'"{k}":"{data_uri(blobs[k])}"' for k in sorted(blobs))
        boot = ("<script id=\"ar-img-map\">window.__IMG={" + table + "};"
                "window.__imgsrc=function(s){return s&&s.indexOf('__img:')===0?window.__IMG[s.slice(6)]:s};</script>")
        hydrate = ("<script id=\"ar-img-hydrate\">(function(){var I=window.__IMG;"
                   "document.querySelectorAll('[data-img]').forEach(function(e){e.setAttribute('src',I[e.getAttribute('data-img')]);});"
                   "document.querySelectorAll('[data-img-srcset]').forEach(function(e){e.setAttribute('srcset',I[e.getAttribute('data-img-srcset')]);});"
                   "document.querySelectorAll('[data-img-href]').forEach(function(e){e.setAttribute('href',I[e.getAttribute('data-img-href')]);});})();</script>")
        m = re.search(r"<body\b[^>]*>", out, re.I)
        out = (out[:m.end()] + "\n" + boot + out[m.end():]) if m else boot + out
        out = out.replace("</body>", hydrate + "\n</body>", 1) if "</body>" in out else out + hydrate
    if lightbox:
        out = out.replace("</body>", LIGHTBOX + "\n</body>", 1) if "</body>" in out else out + LIGHTBOX
    size = len(out.encode("utf-8"))
    imgs = sorted(({"key": k, "role": b["role"], "w": b["w"], "h": b["h"], "src_kb": round(b["src_bytes"] / 1024, 1),
                    "out_kb": round(b["out_bytes"] / 1024, 1), "refs": b["refs"], "paths": sorted(b["paths"])} for k, b in blobs.items()),
                  key=lambda x: -x["out_kb"])
    report = {"mode": use, "quality": quality, "format": fmt, "images": len(blobs), "references": len(refs),
              "duplicates_saved": sum(b["refs"] - 1 for b in blobs.values()) if use == "map" else 0,
              "src_mb": round(sum(b["src_bytes"] for b in blobs.values()) / 1e6, 2),
              "embedded_mb": round(sum(b["out_bytes"] for b in blobs.values()) / 1e6, 2),
              "html_mb": round(size / 1e6, 2), "budget_mb": budget_mb, "figures": n_fig,
              "external_images": sorted(set(external)), "top": imgs[:10], "all": imgs}
    if budget_mb and size > budget_mb * 1e6:
        raise EmbedError("GATE_BLOCKED", f"內嵌後 {size / 1e6:.2f} MB 超過預算 {budget_mb} MB", {k: v for k, v in report.items() if k != "all"})
    return out, report


def _layout_map(html_text: str, key_roles: dict[str, str]) -> tuple[str, int]:
    roles = {}
    for m in re.finditer(r'data-img="([0-9a-f]{12})"', html_text):
        roles[m.group(1)] = key_roles.get(m.group(1), "landscape")
    # layout() 依 src 判斷角色；map 模式改看 data-img
    n = 0

    def fig(m):
        nonlocal n
        tag = m.group(1) or m.group(2)
        k = re.search(r'data-img=["\']([0-9a-f]{12})["\']', tag)
        alt = re.search(r'alt=["\']([^"\']*)["\']', tag)
        role = roles.get(k.group(1), "landscape") if k else "landscape"
        n += 1
        cap = f"<figcaption>{alt.group(1)}</figcaption>" if alt and alt.group(1).strip() else ""
        return f'<figure class="ar-fig ar-{role}">{tag}{cap}</figure>'

    out = _P_IMG_RE.sub(fig, html_text)

    def gal(m):
        block = m.group(0)
        cls = "ar-gallery ar-icons" if block.count("ar-icon") == block.count("<figure") else "ar-gallery"
        return f'<div class="{cls}">{block}</div>'

    out = re.sub(r'(?:<figure class="ar-fig[^"]*">.*?</figure>\s*){2,}', gal, out, flags=re.S)
    return out, n


def main() -> None:
    ap = argparse.ArgumentParser(description="ark-html-report 放圖引擎：本機圖片 → 縮圖 / 轉檔 / 去重 → 內嵌單檔 HTML")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("embed", "inspect"):
        s = sub.add_parser(name)
        s.add_argument("html")
        s.add_argument("--base", help="相對路徑的基準目錄（預設 HTML 所在目錄）")
        s.add_argument("--quality", default="standard", choices=list(TIERS))
        s.add_argument("--format", default="webp", choices=["webp", "jpeg"])
        s.add_argument("--mode", default="auto", choices=["auto", "uri", "map"])
        s.add_argument("--budget-mb", type=float, default=8.0)
        s.add_argument("--no-json-src", action="store_true")
        s.add_argument("--role", action="append", metavar="GLOB=ROLE", help="依路徑指定用途，可重複，例 --role 'symbols/*=icon'")
        if name == "embed":
            s.add_argument("--out", help="輸出（預設 <name>.inline.html）")
            s.add_argument("--layout", action="store_true", help="獨立 <img> 包成 figure、連續圖排成 gallery")
            s.add_argument("--lightbox", action="store_true", help="加點圖放大燈箱")
            s.add_argument("--manifest", help="另寫內嵌清單 json")
    a = ap.parse_args()
    src = pathlib.Path(a.html)
    if not src.exists():
        fail("BAD_INPUT", f"找不到 {src}")
    base = pathlib.Path(a.base) if a.base else src.parent
    text = src.read_text(encoding="utf-8")
    try:
        if a.cmd == "inspect":
            _, rep = embed(text, base, a.quality, a.format, a.mode, None, False, False, not a.no_json_src, parse_roles(a.role))
            rep.pop("all", None)
            emit(rep)
            return
        out_html, rep = embed(text, base, a.quality, a.format, a.mode, a.budget_mb, a.layout, a.lightbox, not a.no_json_src,
                              parse_roles(a.role))
    except EmbedError as e:
        fail(e.code, str(e), "調 --quality lite、給大圖加 data-role，或拿掉不必要的圖" if e.code == "GATE_BLOCKED" else "", e.data)
    out = pathlib.Path(a.out) if a.out else src.with_name(src.stem + ".inline.html")
    out.write_text(out_html, encoding="utf-8", newline="\n")
    if a.manifest:
        pathlib.Path(a.manifest).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    rep.pop("all", None)
    emit({"out": str(out), **rep,
          "delivery": f"{out.name}｜{rep['images']} 張圖（{rep['references']} 處引用，模式 {rep['mode']}）｜原圖 {rep['src_mb']} MB → 內嵌 {rep['embedded_mb']} MB｜HTML {rep['html_mb']} MB"})


if __name__ == "__main__":
    main()
