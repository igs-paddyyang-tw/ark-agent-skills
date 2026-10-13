#!/usr/bin/env python3
"""ps_html — View 軌（1.4.0，md-first）：`prob-spec.md`（Content 軌）→ 單檔 `prob-spec.html`。

- **唯一輸入是 prob-spec.md**：數字與表格都從 md 的表格契約（references/prob-spec-contract.md §表格契約）讀出，
  不再讀 prob-data.json；所以 xlsx 模式、qt 模式、人手照範本寫的 md 三者產出同一套 View（沒有 xlsx 也能出高品質報告）。
  prob-data.json 若在同目錄，只拿 raw_log 放「原始快測輸出」摺疊區（選配）。
- 表格依表頭分類後選元件：KPI / RTP 組成 SVG / 驗收守門（快測摘要）、熱度表（符號命中、矩陣）、長條（權重、輪帶組、贏分分布）、
  旗標（輪帶換帶）、符號 chip（Pay table / Odds / strip）、規格格（kv）、通用表（其餘；超長格摺疊）。
- 頁首戳記 `<!-- content-src: prob-spec.md sha256:<16> -->`，ps_lint PS-STALE 據此驗 md ↔ html 一致。
- 版面：左側章節導覽（窄螢幕變橫向膠囊）、雙主題、手機不橫向捲動；CSS token 遵 ark-html-report 契約。不呼叫 LLM。

用法: python ps_html.py --dir <prob 目錄>            （讀 <dir>/prob-spec.md [+ prob-spec.meta.json] [+ prob-data.json]）
      python ps_html.py --md <prob-spec.md> [--out x.html] [--css assets/view.css] [--body-only]
交付格式：View 軌已落盤 <out>｜章節 N｜戳記 sha256:<16>
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ps_common as C  # noqa: E402
import ps_mdview as M  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_CSS = HERE.parent / "assets" / "view.css"
GROUP_COLORS = ["var(--g1)", "var(--g2)", "var(--g3)", "var(--g4)"]
SERIES = ["var(--c1)", "var(--c2)", "var(--c3)", "var(--c4)", "var(--c5)", "var(--c6)"]
PENDING = M.PENDING
LONG_CELL = 40   # 超過此長度的字串格摺疊（如 xlsx 旁註的 Go 陣列字面量），避免撐爆欄寬


# ------------------------------------------------------------------ primitives

def esc(s) -> str:
    return html.escape("" if s is None else str(s))


def isnum(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def num(v, d=None) -> str:
    if v is None or v == "" or v == "-":
        return "—"
    if isinstance(v, str):
        return esc(v)
    if d is None:
        d = 0 if float(v).is_integer() else (4 if abs(v) < 10 else 2)
    return f"{v:,.{d}f}"


def _col_letter(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def cell(v) -> str:
    """通用表儲存格：空 → 空白；超長字串 → <details> 摺疊（`{a, b, …}` 陣列標項數）；其餘同 num()。"""
    if v is None or v == "":
        return ""
    if isinstance(v, str) and len(v.strip()) > LONG_CELL:
        s = v.strip()
        label = f"陣列 {len(s.strip('{},; ').split(','))} 項" if s.startswith("{") else esc(s[:16]) + "…"
        return f'<details class="cell-fold"><summary>{label}</summary><code>{esc(s)}</code></details>'
    return num(v)


def split_generic(rows: list[dict], c0: int = 1) -> list[dict]:
    """（相容 1.2 的 xlsx 通用表切分；md-first 已不走此路，保留給舊測試與 ps_xlsx）把通用表切成並排子表。"""
    def strs(r):
        return sum(isinstance(v, str) for v in r["cells"])

    def has_num(r):
        return any(isnum(v) for v in r["cells"])

    width = max(len(r["cells"]) for r in rows)
    grid = [r["cells"] + [None] * (width - len(r["cells"])) for r in rows]
    hi = None
    if strs(rows[0]) >= 2:
        hi = 0
        while hi + 1 < len(rows) and strs(rows[hi + 1]) > strs(rows[hi]) and not has_num(rows[hi + 1]):
            hi += 1
    filled = [any(g[c] not in (None, "") for g in grid) for c in range(width)]
    segs, start = [], None
    for c in range(width + 1 if hi is not None else 0):
        if c < width and filled[c]:
            start = c if start is None else start
        elif start is not None:
            segs.append((start, c)); start = None
    if hi is None:
        segs = [(0, width)]
    else:
        cut = []
        for a, b in segs:
            head = grid[hi][a:b]
            li = next((j for j, v in enumerate(head) if v not in (None, "")), None)
            reps = [] if li is None else [a + j for j in range(li + 1, b - a) if head[j] == head[li]]
            ks = [a] + reps + [b]
            cut += list(zip(ks, ks[1:]))
        segs = cut
    out = []
    for a, b in segs:
        caps = [esc(v) for g in grid[:hi or 0] for v in g[a:b] if v not in (None, "")]
        head = [esc(v) if v is not None else "" for v in grid[hi][a:b]] if hi is not None else [""] * (b - a)
        body = [g[a:b] for g in grid[(hi + 1 if hi is not None else 0):] if any(v not in (None, "") for v in g[a:b])]
        if hi is not None and not any(head) and not caps:
            caps = [f"xlsx {_col_letter(c0 + a)} 欄旁註"]
        if body or any(head):
            out.append({"captions": caps, "head": head, "rows": body})
    return out


def pc(v, d=2) -> str:
    return "—" if v is None else f"{v:.{d}f}%"


def th(cols, numcols=()):
    return "<tr>" + "".join(f'<th{" class=num" if i in numcols else ""}>{c}</th>' for i, c in enumerate(cols)) + "</tr>"


def table(head, rows, numcols=(), cls="", caption=None, foot=None, row_titles=None):
    h = f'<table class="table {cls}">'
    if caption:
        h += f"<caption>{caption}</caption>"
    h += "<thead>" + th(head, numcols) + "</thead><tbody>"
    for ri, r in enumerate(rows):
        t = f' title="{esc(row_titles[ri])}"' if row_titles and ri < len(row_titles) and row_titles[ri] else ""
        h += f"<tr{t}>" + "".join(f'<td{" class=num" if i in numcols else ""}>{c}</td>' for i, c in enumerate(r)) + "</tr>"
    h += "</tbody>"
    if foot:
        h += "<tfoot><tr>" + "".join(f'<td{" class=num" if i in numcols else ""}>{c}</td>' for i, c in enumerate(foot)) + "</tr></tfoot>"
    return f'<div class="table-wrap">{h}</table></div>'


def bar(v, mx, label=None, color="var(--c1)"):
    w = 0 if not mx else max(0, min(100, v / mx * 100))
    return f'<span class="cellbar"><i style="width:{w:.1f}%;background:{color}"></i><b>{label if label is not None else num(v)}</b></span>'


def heat(v, mx, label=None, hue="var(--c1)"):
    p = 0 if not mx else max(0, min(1, v / mx))
    return f'<td class="num heat{" ink" if p > 0.62 else ""}" style="--p:{p*72:.0f}%;--hue:{hue}">{label if label is not None else num(v)}</td>'


def chip(t, cls=""):
    return f'<span class="chip {cls}">{t}</span>'


def sec(id_, no, title, body, src=None):
    s = f'<span class="src">{src}</span>' if src else ""
    return f'<section class="section" id="{id_}"><div class="section-head"><span class="section-no">{no}</span><h2>{title}</h2>{s}</div>{body}</section>'


def sym_cls(s: str) -> str:
    s = str(s).upper()
    if s in ("WW", "WILD", "W") or s.startswith("WILD"):
        return "WW"
    if s.startswith("SC"):
        return "SC"
    if s.startswith("SS"):
        return "SS"
    if s.startswith("M") or s.startswith("H"):
        return "high"
    return "low"


def sym(s: str) -> str:
    return f'<span class="sym {sym_cls(s)}">{esc(s)}</span>'


def inline(t: str) -> str:
    """行內 markdown：**bold**、`code`、標籤字（SPEC / DECIDED…）、待決議 紅字。"""
    t = esc(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"(?<![\w-])(SPEC|DECIDED|UNKNOWN|FROM_KB|OBSERVED|INFERRED|PROPOSED)(?![\w-])", r'<span class="tag \1">\1</span>', t)
    t = t.replace(PENDING, f'<span class="pending">{PENDING}</span>')
    return t


def vcell(v: str) -> str:
    """表格值：數字右對齊格式化、待決議紅字、其餘行內渲染。"""
    s = v.strip()
    if s == "":
        return ""
    if s == PENDING:
        return f'<span class="pending">{PENDING}</span>'
    if len(s) > LONG_CELL and not s.startswith("**"):
        return cell(s)
    return inline(s)


def md_to_html(md: str) -> str:
    """最小 markdown → html（人工區 / 段落用）。"""
    doc = M.parse_md("## x\n" + md) if not md.startswith("## ") else M.parse_md(md)
    out = []
    for s in doc["sections"]:
        out.append(render_blocks(s["blocks"], generic_only=True))
    return "".join(out)


# ------------------------------------------------------------------ block renderers

def render_blocks(blocks: list[dict], generic_only: bool = False, ctx: dict | None = None) -> str:
    out = []
    for b in blocks:
        k = b["kind"]
        if k == "h3":
            m = re.match(r"^(表\s*[A-Z]-[\w-]+)\s*[　 ]*(.*)$", b["text"])
            if m:
                out.append(f'<h3><span class="tid">{esc(m.group(1))}</span>{inline(m.group(2))}</h3>')
            else:
                out.append(f"<h3>{inline(b['text'])}</h3>")
        elif k == "h4":
            out.append(f"<h4>{inline(b['text'])}</h4>")
        elif k == "bold":
            out.append(f"<h4>{inline(b['text'])}</h4>")
        elif k == "p":
            out.append(f"<p>{inline(b['text'])}</p>")
        elif k == "ul":
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in b["items"]) + "</ul>")
        elif k == "ol":
            out.append("<ol>" + "".join(f"<li>{inline(x)}</li>" for x in b["items"]) + "</ol>")
        elif k == "quote":
            out.append(f"<blockquote>{inline(b['text'])}</blockquote>")
        elif k == "code":
            if b["lang"] == "mermaid":
                out.append(f'<pre class="mermaid">{esc(b["text"])}</pre>')
            elif b["lang"] == "strip":
                out.append(render_strip_fence(b))
            else:
                out.append(f"<pre><code>{esc(b['text'])}</code></pre>")
        elif k == "human":
            inner = md_to_html(b["text"]) if b["text"].strip() else '<p class="note">（尚未填寫）</p>'
            out.append(f'<div class="human" data-id="{esc(b["id"])}">{inner}</div>')
        elif k == "table":
            out.append(render_table(b, ctx or {}) if not generic_only else r_generic(b))
    return "".join(out)


def _strip_src(tbl: dict) -> tuple[list[str], list[list[str]], list[str]]:
    """去掉「來源」欄（放到列的 title）；回傳 head, rows, sources。"""
    head = [M._h(c) for c in tbl["head"]]
    rows = [[c for c in r] for r in tbl["rows"]]
    srcs = [""] * len(rows)
    if head and head[-1] in ("來源", "source", "Source"):
        idx = len(head) - 1
        srcs = [(r[idx] if idx < len(r) else "") for r in rows]
        head = head[:-1]
        rows = [r[:idx] for r in rows]
    width = len(head)
    rows = [r + [""] * (width - len(r)) if len(r) < width else r[:width] for r in rows]
    return head, rows, srcs


def render_table(tbl: dict, ctx: dict) -> str:
    if tbl.get("caption") and tbl["caption"] == ctx.get("heading"):
        tbl = {**tbl, "caption": None}
    fn = globals().get("r_" + tbl.get("cls", "generic")) or r_generic
    try:
        return fn(tbl, ctx) if fn is not r_generic else r_generic(tbl)
    except Exception:  # noqa: BLE001  任何分類渲染失敗都退回通用表，不讓一張表炸掉整頁
        return r_generic(tbl)


def r_generic(tbl: dict, ctx: dict | None = None) -> str:
    head, rows, srcs = _strip_src(tbl)
    numcols = tuple(i for i in range(len(head)) if M.numeric_col(rows, i))
    body = [[vcell(c) for c in r] for r in rows]
    cap = tbl.get("caption")
    return table([inline(h) for h in head], body, numcols=numcols, cls="compact", caption=inline(cap) if cap and cap not in (ctx or {}).get("used_caps", set()) else None, row_titles=[f"來源 {s}" if s else "" for s in srcs])


def r_summary(tbl: dict, ctx: dict) -> str:
    head, rows, srcs = _strip_src(tbl)
    return '<div class="spec">' + "".join(f'<div title="{esc(s)}"><div class="k">{inline(r[0])}</div><div class="v">{vcell(r[1]) if len(r) > 1 else ""}</div></div>' for r, s in zip(rows, srcs)) + "</div>"


def r_kv(tbl: dict, ctx: dict) -> str:
    head, rows, srcs = _strip_src(tbl)
    if len(rows) > 24:
        return r_generic(tbl, ctx)
    cells = []
    for r, s in zip(rows, srcs):
        extra = f'<small>{inline(r[2])}</small>' if len(r) > 2 and r[2] else ""
        cells.append(f'<div title="{esc(s)}"><div class="k">{inline(r[0])}</div><div class="v">{vcell(r[1]) if len(r) > 1 else ""} {extra}</div></div>')
    return '<div class="spec">' + "".join(cells) + "</div>"


def r_base(tbl: dict, ctx: dict) -> str:
    head, rows, srcs = _strip_src(tbl)
    keep = [r for r in rows if not all(M.tonum(c) in (None, 0.0) for c in r[1:])]  # 全 0 / 全 — 的列省略（Feature / GRAND 未啟用）
    numcols = tuple(range(1, len(head)))
    return table([inline(h) for h in head], [[inline(r[0])] + [vcell(c) for c in r[1:]] for r in keep], numcols=numcols, cls="compact", caption=inline(tbl.get("caption") or "") or None)


def r_symhit(tbl: dict, ctx: dict) -> str:
    head, rows, srcs = _strip_src(tbl)
    xcols = [i for i, h in enumerate(head) if re.fullmatch(r"x\d+", h.lower())]
    tot_i = len(head) - 1
    body_rows = [r for r in rows if M._h(r[0]).upper() not in ("TOTAL", "合計")]
    tot_row = next((r for r in rows if M._h(r[0]).upper() in ("TOTAL", "合計")), None)
    keep = [i for i in xcols if any((M.tonum(r[i]) or 0) > 0 for r in body_rows)]
    mx = max([(M.tonum(r[i]) or 0) for r in body_rows for i in keep] or [1]) or 1
    cap = tbl.get("caption")
    h = f'<table class="table compact">{("<caption>" + inline(cap) + "</caption>") if cap else ""}<thead>' + th(["符號"] + [esc(head[i]) for i in keep] + ["TOTAL"], tuple(range(1, len(keep) + 2))) + "</thead><tbody>"
    for r in body_rows:
        h += f"<tr><td>{esc(r[0])}</td>" + "".join(heat(M.tonum(r[i]) or 0, mx, esc(r[i])) for i in keep) + f'<td class="num"><strong>{esc(r[tot_i])}</strong></td></tr>'
    if tot_row:
        h += "</tbody><tfoot><tr><td>TOTAL</td>" + "".join(f'<td class="num">{esc(tot_row[i])}</td>' for i in keep) + f'<td class="num">{esc(tot_row[tot_i])}</td></tr></tfoot>'
    return f'<div class="table-wrap">{h}</table></div>'


def _flags_cell(cells: list[str], as_index: bool = False) -> str:
    vals = [M.tonum(c) for c in cells]
    if not as_index and all(v in (0.0, 1.0) for v in vals):
        return '<span class="flagcell">' + "".join(f'<span class="flag{" on" if v else ""}">{i+1}</span>' for i, v in enumerate(vals)) + "</span>"
    return '<span class="flagcell">' + "".join(f'<span class="flag{" on" if (v or 0) > 0 else ""}" title="R{i+1} 用組 {esc(c)}">{esc(c)}</span>' for i, (v, c) in enumerate(zip(vals, cells))) + "</span>"


def r_reelsets(tbl: dict, ctx: dict) -> str:
    head, rows, srcs = _strip_src(tbl)
    rcols = [i for i, h in enumerate(head) if re.match(r"R\d", h)]
    as_index = any("用組" in head[i] for i in rcols)   # qt 模式：值 = 用第幾組帶，不是換帶旗標
    wi = next(i for i, h in enumerate(head) if h in ("權重", "Weight"))
    rest = [i for i in range(len(head)) if i not in rcols and i not in (0, wi)]
    data = [r for r in rows if M.tonum(r[0]) is not None or M._h(r[0]) not in ("", "Σ", "合計", "加權")]
    foot_rows = [r for r in rows if r not in data]
    ws = [M.tonum(r[wi]) for r in data]
    nums_ = [w for w in ws if w is not None]
    wsum = sum(nums_) if nums_ else 0
    mx = max(nums_) if nums_ else 1
    out_rows = []
    for r, w in zip(data, ws):
        row = [f"<strong>{esc(r[0])}</strong>", _flags_cell([r[i] for i in rcols], as_index), bar(w, mx, num(w)) if w is not None else vcell(r[wi]), pc(w / wsum * 100, 1) if (w is not None and wsum) else "—"]
        for i in rest:
            v = M.tonum(r[i])
            row.append(pc(v * 100 if (v is not None and v < 5) else v) if ("RTP" in head[i].upper() and v is not None) else (f'<span style="white-space:nowrap">{vcell(r[i])}</span>'))
        out_rows.append(row)
    foot = ["Σ", "", num(wsum), "100%"]
    for i in rest:
        fv = next((M.tonum(fr[i]) for fr in foot_rows if i < len(fr) and M.tonum(fr[i]) is not None), None)
        foot.append((pc(fv * 100 if fv < 5 else fv) if "RTP" in head[i].upper() else num(fv)) if fv is not None else "")
    numcols = (2, 3) + tuple(4 + j for j, i in enumerate(rest) if "RTP" in head[i].upper() or M.numeric_col(data, i))
    return table(["Index", ("R1–R%d 用組" if as_index else "R1–R%d 換帶") % len(rcols), "權重", "佔比"] + [inline(head[i]) for i in rest], out_rows, numcols=numcols, foot=foot, cls="compact",
                 caption=inline(tbl.get("caption") or "") or None, row_titles=[f"來源 {s}" if s else "" for s in srcs])


def r_reelset_rtp(tbl: dict, ctx: dict) -> str:
    head, rows, srcs = _strip_src(tbl)
    rcols = [i for i, h in enumerate(head) if ("RTP" in h.upper())]
    allv = [M.tonum(r[i]) or 0 for r in rows for i in rcols]
    mx = max(allv or [1]) or 1
    out_rows, foot = [], None
    for r in rows:
        if M._h(r[0]) in ("加權", "Σ", "合計"):
            foot = [inline(r[0])] + [vcell(c) for c in r[1:]]
            continue
        row = []
        for i, c in enumerate(r):
            if i in rcols and M.tonum(c) is not None:
                row.append(bar(M.tonum(c), mx, esc(c), "var(--c6)" if "理論" in head[i] else ("var(--c2)" if "FG" in head[i].upper() else "var(--c1)")))
            elif i == 1 and re.search(r"換帶|R1", head[i]):
                row.append(_flags_cell(c.replace("/", " ").split()))
            else:
                row.append(vcell(c))
        out_rows.append(row)
    numcols = tuple(i for i in range(len(head)) if M.numeric_col(rows, i) and i not in rcols)
    return table([inline(h) for h in head], out_rows, numcols=numcols, foot=foot, cls="compact", caption=inline(tbl.get("caption") or "") or None) + \
        '<p class="note">理論值來自參數表的單組 RTP，實測值來自快測；單組差異加權後應收斂到總 RTP。</p>'


def r_range(tbl: dict, ctx: dict) -> str:
    head, rows, srcs = _strip_src(tbl)
    ri = next((i for i, h in enumerate(head) if h.startswith("RTP")), None)
    mx = max([M.tonum(r[ri]) or 0 for r in rows] or [1]) if ri is not None else 1
    out_rows = []
    for r in rows:
        if ri is not None and all((M.tonum(c) or 0) == 0 for c in r[1:]):
            continue
        out_rows.append([esc(r[0])] + [bar(M.tonum(c) or 0, mx, esc(c), "var(--c2)") if (i == ri and M.tonum(c) is not None) else vcell(c) for i, c in enumerate(r) if i > 0])
    return table([inline(h) for h in head], out_rows, numcols=tuple(i for i in range(1, len(head)) if i != ri), cls="compact", caption=inline(tbl.get("caption") or "各贏分區間出現率與 RTP 貢獻"))


def r_multiple(tbl: dict, ctx: dict) -> str:
    head, rows, srcs = _strip_src(tbl)
    return table([inline(h) for h in head], [[vcell(c) for c in r] for r in rows if (M.tonum(r[1]) or 0) > 0], numcols=tuple(i for i in range(1, len(head)) if M.numeric_col(rows, i)), cls="compact", caption=inline(tbl.get("caption") or "倍數出現頻率（局數）"))


def r_asset(tbl: dict, ctx: dict) -> str:
    head, rows, srcs = _strip_src(tbl)
    return table([inline(h) for h in head], [[esc(r[0]), bar(M.tonum(r[1]) or 0, 100, esc(r[1]))] + [vcell(c) for c in r[2:]] for r in rows], cls="compact", caption=inline(tbl.get("caption") or "100 手資產轉 100 手後分布"))


def r_decile(tbl: dict, ctx: dict) -> str:
    head, rows, srcs = _strip_src(tbl)
    return table([inline(h) for h in head], [[vcell(c) for c in r] for r in rows], numcols=tuple(range(1, len(head))), cls="compact", caption=inline(tbl.get("caption") or "十分位 Decile"))


def r_fg_groups(tbl: dict, ctx: dict) -> str:
    head, rows, srcs = _strip_src(tbl)
    rtp_i = next((i for i, h in enumerate(head) if "RTP" in h.upper()), None)
    mx = max([M.tonum(r[rtp_i]) or 0 for r in rows] or [1]) if rtp_i is not None else 1
    out_rows = []
    for gi, r in enumerate(rows):
        row = [f'<span class="chip" style="border-color:{GROUP_COLORS[gi % 4]};color:{GROUP_COLORS[gi % 4]}">{esc(r[0])}</span>']
        for i, c in enumerate(r[1:], 1):
            row.append(bar(M.tonum(c) or 0, mx, esc(c), GROUP_COLORS[gi % 4]) if (i == rtp_i and M.tonum(c) is not None) else vcell(c))
        out_rows.append(row)
    return table([inline(h) for h in head], out_rows, numcols=tuple(i for i in range(1, len(head)) if i != rtp_i), cls="compact", caption=inline(tbl.get("caption") or "") or None)


def r_paytable(tbl: dict, ctx: dict) -> str:
    head, rows, srcs = _strip_src(tbl)
    xs = [i for i, h in enumerate(head) if re.fullmatch(r"x\d+", h.lower())]
    return table([inline(h) for h in head], [[inline(r[0]), sym(r[1])] + [vcell(c) for c in r[2:]] for r in rows], numcols=tuple(xs), cls="compact", row_titles=[f"來源 {s}" if s else "" for s in srcs])


def r_odds(tbl: dict, ctx: dict) -> str:
    head, rows, srcs = _strip_src(tbl)
    xs = [i for i, h in enumerate(head) if re.fullmatch(r"x\d+", h.lower())]
    keep = [i for i in range(len(head)) if i not in xs or any((M.tonum(r[i]) or 0) > 0 or r[i].strip() == PENDING for r in rows)]
    out_rows = [[sym(r[0]) if i == 0 else vcell(r[i]) for i in keep] for r in rows]
    return table([inline(head[i]) for i in keep], out_rows, numcols=tuple(j for j, i in enumerate(keep) if i in xs or head[i] == "sym_id"), cls="compact", row_titles=[f"來源 {s}" if s else "" for s in srcs])


def r_strip_counts(tbl: dict, ctx: dict) -> str:
    head, rows, srcs = _strip_src(tbl)
    symcols = list(range(3, len(head)))
    groups: dict[str, list] = {}
    for r in rows:
        groups.setdefault(M._h(r[0]), []).append(r)
    out = []
    for g, rs in groups.items():
        keep = [i for i in symcols if any((M.tonum(r[i]) or 0) > 0 for r in rs)]
        mx = max([(M.tonum(r[i]) or 0) for r in rs for i in keep] or [1]) or 1
        h = f'<table class="table compact"><caption>{inline(tbl.get("caption") or "")} 組 {esc(g)} · 各軸符號顆數</caption><thead>' + th(["軸", "長度"] + [sym(head[i]) for i in keep], tuple(range(1, len(keep) + 2))) + "</thead><tbody>"
        for r in rs:
            h += f'<tr><td>{esc(r[1])}</td><td class="num">{esc(r[2])}</td>' + "".join(heat(M.tonum(r[i]) or 0, mx, esc(r[i]) if (M.tonum(r[i]) or 0) else '<span style="opacity:.35">0</span>', "var(--sym-%s)" % {"WW": "wild", "SC": "sc", "SS": "ss", "high": "high", "low": "low"}[sym_cls(head[i])]) for i in keep) + "</tr>"
        out.append(f'<div class="table-wrap">{h}</tbody></table></div>')
    return "".join(out)


def r_yesno(tbl: dict, ctx: dict) -> str:
    head, rows, srcs = _strip_src(tbl)
    yi, ni = head.index("是"), head.index("否")
    out_rows = []
    for gi, r in enumerate(rows):
        y, n = M.tonum(r[yi]) or 0, M.tonum(r[ni]) or 0
        label = r[0] if r[0] else f"列 {gi+1}"
        out_rows.append([f'<span class="chip" style="border-color:{GROUP_COLORS[gi % 4]};color:{GROUP_COLORS[gi % 4]}">{esc(label)}</span>', bar(y, y + n, num(y), "var(--c3)"), num(n)] + [vcell(c) for i, c in enumerate(r) if i not in (0, yi, ni)])
    return table(["組別", "是", "否"] + [inline(h) for i, h in enumerate(head) if i not in (0, yi, ni)], out_rows, numcols=(2,), cls="compact", caption=inline(tbl.get("caption") or "") or None, row_titles=[f"來源 {s}" if s else "" for s in srcs])


def r_dual(tbl: dict, ctx: dict) -> str:
    head, rows, srcs = _strip_src(tbl)
    pairs = [(j, j + 1) for j in range(len(head) - 1) if head[j].endswith("倍數") and head[j + 1].endswith("權重")]
    hues = ["var(--sym-sc)", "var(--sym-ss)", "var(--c3)", "var(--c4)"]
    data = [r for r in rows if not (M._h(r[0]) in ("Σ", "合計", "均倍") or all(M.tonum(r[j]) is None for j, _ in pairs))]
    foot_rows = [r for r in rows if r not in data]
    out_head, out_rows = [], []
    for j, _ in pairs:
        out_head += [inline(head[j]), inline(head[j + 1]), "%"]
    tots = [sum((M.tonum(r[w]) or 0) for r in data) for _, w in pairs]
    mxs = [max([(M.tonum(r[w]) or 0) for r in data] or [1]) or 1 for _, w in pairs]
    for r in data:
        row = []
        for k, (v, w) in enumerate(pairs):
            wv = M.tonum(r[w])
            row += [vcell(r[v]), bar(wv, mxs[k], num(wv), hues[k % 4]) if wv is not None else vcell(r[w]), pc(wv / tots[k] * 100, 1) if (wv is not None and tots[k]) else "—"]
        out_rows.append(row)
    foot = []
    for k, (v, w) in enumerate(pairs):
        ex = " · ".join(esc(fr[v]) for fr in foot_rows if fr[v] and M.tonum(fr[v]) is None) or "Σ"
        foot += [ex, num(tots[k]), "100%"]
    return table(out_head, out_rows, numcols=tuple(i for i in range(len(out_head)) if i % 3 != 1), foot=foot, cls="compact", caption=inline(tbl.get("caption") or "") or None)


def r_matrix(tbl: dict, ctx: dict) -> str:
    head, rows, srcs = _strip_src(tbl)
    numeric_idx = [i for i, h in enumerate(head) if i > 0 and re.fullmatch(r"\d+(\.\d+)?", h)]
    tail_idx = [i for i in range(1, len(head)) if i not in numeric_idx]
    last = numeric_idx[-1] if numeric_idx else 0
    while last > 0 and all(not (M.tonum(r[last]) or 0) for r in rows if last < len(r)):
        last -= 1
    keep = [i for i in numeric_idx if i <= last] + tail_idx
    cap = tbl.get("caption") or ctx.get("heading", "")
    hue = SERIES[(sum(map(ord, cap)) % 6)]
    h = f'<table class="table compact{" tight" if len(keep) > 12 else ""}"><caption>{inline(cap)}</caption><thead>' + th(["組別"] + [esc(head[i]) for i in keep], tuple(range(1, len(keep) + 1))) + "</thead><tbody>"
    for gi, r in enumerate(rows):
        nums_ = [M.tonum(r[i]) for i in numeric_idx if i < len(r) and M.tonum(r[i]) is not None]
        mx = max(nums_) if nums_ else 1
        h += f'<tr><td><span class="chip" style="border-color:{GROUP_COLORS[gi % 4]};color:{GROUP_COLORS[gi % 4]}">{esc(r[0])}</span></td>'
        for i in keep:
            v = M.tonum(r[i]) if i < len(r) else None
            if i in numeric_idx:
                h += heat(v or 0, mx, esc(r[i]) if v else '<span style="opacity:.35">0</span>', hue)
            else:
                h += f'<td class="num"><strong>{vcell(r[i]) if i < len(r) else ""}</strong></td>'
        h += "</tr>"
    return f'<div class="table-wrap">{h}</tbody></table></div>'


def r_weights(tbl: dict, ctx: dict) -> str:
    head, rows, srcs = _strip_src(tbl)
    data = [r for r in rows if M._h(r[0]) not in ("Σ", "合計", "權重和", "Total")]
    ws = [M.tonum(r[1]) for r in data]
    nums_ = [w for w in ws if w is not None]
    tot, mx = sum(nums_), (max(nums_) if nums_ else 1)
    extra = [i for i in range(2, len(head)) if head[i] != "%"]
    out_rows = [[inline(r[0]), bar(w, mx, num(w)) if w is not None else vcell(r[1]), pc(w / tot * 100, 1) if (tot and w is not None) else "—"] + [vcell(r[i]) for i in extra] for r, w in zip(data, ws)]
    return table(["項目", "權重", "%"] + [inline(head[i]) for i in extra], out_rows, numcols=(2,), foot=["Σ", num(tot), "100%"] + [""] * len(extra), cls="compact", caption=inline(tbl.get("caption") or "") or None, row_titles=[f"來源 {s}" if s else "" for s in srcs])


def r_series(tbl: dict, ctx: dict) -> str:
    head, rows, srcs = _strip_src(tbl)
    out_rows = []
    for r in rows:
        vals = [M.tonum(c) for c in r[1:]]
        is_total_last = head[-1].lower() in ("total", "合計", "權重和", "σ")
        body = vals[:-1] if is_total_last else vals
        mx = max([v for v in body if v is not None] or [1]) or 1
        cells = [inline(r[0])]
        for i, v in enumerate(body):
            cells.append(bar(v, mx, num(v), SERIES[i % 6] if len(rows) == 1 else "var(--c2)") if v else '<span style="opacity:.35">0</span>' if v == 0 else vcell(r[i + 1]))
        if is_total_last:
            cells.append(f"<strong>{vcell(r[-1])}</strong>")
        out_rows.append(cells)
    return table([inline(h) if h else "" for h in head], out_rows, numcols=tuple(range(1, len(head))), cls="compact", caption=inline(tbl.get("caption") or "") or None, row_titles=[f"來源 {s}" if s else "" for s in srcs])


def render_strip_fence(b: dict) -> str:
    fences = M.strip_fences({"sections": [{"id": "x", "blocks": [b]}]})
    if not fences:
        return f"<pre><code>{esc(b['text'])}</code></pre>"
    f = fences[0]
    grid = ""
    for i, r in enumerate(f["reels"]):
        groups_html = "".join(f'<span class="grp"><em>{j+1}</em>' + "".join(f'<span class="sym {sym_cls(s)}" title="R{i+1} #{j+k+1} {esc(s)}">{esc(s)}</span>' for k, s in enumerate(r[j:j + 10])) + "</span>" for j in range(0, len(r), 10))
        grid += f'<div class="rowstrip"><h5>R{i+1} · {len(r)} 格（由上而下 = 由左而右，每 10 格標位置）</h5><div class="cells">{groups_html}</div></div>'
    lens = " / ".join(str(len(r)) for r in f["reels"])
    return f'<details><summary>{esc(f["name"])} 帶面 <span class="sub-note">長度 {lens}</span></summary><div>{grid}</div></details>'


# ------------------------------------------------------------------ page

class View:
    def __init__(self, doc: dict, meta: dict, data: dict | None):
        self.doc, self.meta, self.pdata = doc, meta, data or {}
        self.fm = doc["fm"]
        self.game = str(self.fm.get("game") or self.meta.get("game") or self.fm.get("slug") or "")
        self.slug = str(self.fm.get("slug") or self.meta.get("slug") or "")
        self.mode = str(self.fm.get("mode") or self.meta.get("mode") or ("qt" if self.fm.get("odds_version") else "md"))
        self.summary = M.summary_of(doc)
        self.verdict = str(self.fm.get("verdict") or self.meta.get("verdict") or "未快測")
        self.pending = self.fm.get("pending_params", self.meta.get("pending_params", 0))
        self.human = M.human_blocks(doc)
        g = self.summary.get("golden") or self.summary.get("target")
        self.golden = g["num"] if g else None
        self.golden_kind = "golden" if self.summary.get("golden") else ("target" if self.summary.get("target") else None)
        self.tol = (self.summary.get("tol") or {}).get("num")
        rt = self.summary.get("rtp_total")
        self.rtp_total = rt["num"] if rt else None
        self.rtp_main = (self.summary.get("rtp_main") or {}).get("num")
        self.rtp_free = (self.summary.get("rtp_free") or {}).get("num")
        dl = self.summary.get("delta")
        self.delta = dl["num"] if (dl and dl["num"] is not None) else ((self.rtp_total - self.golden) if (self.rtp_total is not None and self.golden is not None) else None)

    def sv(self, key, default="—"):
        v = self.summary.get(key)
        return esc(v["text"]) if v and v["text"] else default

    # ---- header / toc
    def header(self):
        cls = "ok" if self.verdict == "confirmed" else ("danger" if self.verdict == "rejected" else "warn")
        srcs = self.fm.get("sources") if isinstance(self.fm.get("sources"), dict) else {}
        chips = []
        first = (srcs.get("xlsx") or srcs.get("odds") or next(iter(srcs.values()), None)) if srcs else None
        if first:
            chips.append(chip(f"來源 {esc(pathlib.Path(str(first)).name)}" + (f" +{len(srcs)-1}" if len(srcs) > 1 else "")))
        if self.summary.get("spins"):
            n = self.summary["spins"]["num"]
            chips.append(chip(f"快測 {n/1e8:g} 億手" if n and n >= 1e8 else f"快測 {self.sv('spins')} 手") if n else chip(f"快測 {self.sv('spins')}"))
        if self.golden is not None:
            chips.append(chip(f"{'golden' if self.golden_kind == 'golden' else '目標'} {self.golden:.2f}%"))
        chips.append(chip(f'<span class="dot"></span> 數據 {esc(self.verdict)}' + (f" · 誤差 {self.delta:+.3f} pp" if self.delta is not None else ""), cls))
        chips.append(chip(f"pending_params {esc(self.pending)}", "ghost"))
        chips.append(chip(f"{esc(self.mode)} 模式", "ghost"))
        lede = {"xlsx": "由機率表 xlsx 程式化轉成 Content 軌 prob-spec.md 再渲染：總覽先看 RTP 是否收斂 golden，再往下看參數表、流程與輪帶。文字與數字都來自 prob-spec.md，皆可回溯。",
                "qt": "由快測產物（odds.json + rtp-report.json + 決議）組成 Content 軌 prob-spec.md 再渲染：總覽先看三向 verdict，再看參數表、流程與輪帶。文字與數字都來自 prob-spec.md，皆可回溯。"}.get(self.mode,
                "由 Content 軌 prob-spec.md 直接渲染（無 xlsx）：表格照契約表頭命名即可得到同一套視圖。文字與數字都來自 prob-spec.md。")
        return f"""<header class="report-header"><div class="eyebrow">機率規格書 · PROB-SPEC · {esc(self.game)} {esc(self.slug)}</div>
<h1>{esc(self.game)} 機率規格書</h1>
<p class="lede">{lede}</p>
<div class="meta">{''.join(chips)}</div></header>"""

    def toc(self, items):
        lis = "".join(f'<li><a href="#{i}"><span class="no">{n}</span>{t}</a></li>' for i, t, n in items)
        return f'<nav class="toc" aria-label="章節"><div class="toc-title">Sections</div><ol>{lis}</ol></nav>'

    # ---- overview
    def overview(self):
        if self.rtp_total is None:
            return '<div class="callout callout-warning"><div class="callout-title">未快測</div><p>Content 軌 §2 沒有快測摘要或 BASE INFO 表。跑快測後重產 prob-spec.md（或照契約手填 §2「快測摘要」表），本頁總覽會自動出現 KPI 與 RTP 組成圖。</p></div>' + self.gates()
        k = []
        d = ""
        if self.delta is not None:
            tol = self.tol if self.tol is not None else 0.2
            d = f'<div class="kpi-delta {"good" if abs(self.delta) <= tol else "bad"}">{self.delta:+.3f} pp vs {"golden" if self.golden_kind == "golden" else "目標"} {self.golden:.2f}%</div>'
        k.append(f'<div class="kpi hero"><div class="kpi-label">總 RTP</div><div class="kpi-value">{self.rtp_total:.2f}<small>%</small></div>{d}</div>')
        if self.rtp_main is not None:
            hit = self.summary.get("mg_hit")
            k.append(f'<div class="kpi"><div class="kpi-label">主遊戲 RTP</div><div class="kpi-value">{self.rtp_main:.2f}<small>%</small></div><div class="kpi-delta">{("Hit " + esc(hit["text"])) if hit else ""}</div></div>')
        if self.rtp_free is not None:
            share = f"佔總 RTP {self.rtp_free / self.rtp_total * 100:.1f}%" if self.rtp_total else ""
            k.append(f'<div class="kpi"><div class="kpi-label">免費／特色遊戲 RTP</div><div class="kpi-value">{self.rtp_free:.2f}<small>%</small></div><div class="kpi-delta">{share}</div></div>')
        if self.summary.get("fg_rate"):
            fq = self.summary.get("fg_freq")
            k.append(f'<div class="kpi"><div class="kpi-label">FG 觸發率</div><div class="kpi-value">{esc(self.summary["fg_rate"]["text"]).replace("%", "")}<small>%</small></div><div class="kpi-delta">{("每 " + esc(fq["text"]) + " 手觸發一次") if fq else ""}</div></div>')
        if self.summary.get("fg_avg"):
            k.append(f'<div class="kpi"><div class="kpi-label">FG 平均倍率</div><div class="kpi-value">{self.sv("fg_avg")}<small>x</small></div><div class="kpi-delta">最大 {self.sv("fg_max")}x</div></div>')
        if self.summary.get("mg_max"):
            k.append(f'<div class="kpi"><div class="kpi-label">主遊戲最大倍數</div><div class="kpi-value">{self.sv("mg_max")}<small>x</small></div><div class="kpi-delta">{self.sv("flag", "")}</div></div>')
        return f'<div class="kpi-grid">{"".join(k)}</div>' + self.rtp_bar() + self.gates()

    def rtp_bar(self):
        if self.rtp_main is None or self.rtp_free is None or self.rtp_total is None:
            return ""
        W, x0, x1 = 900, 20, 880
        top = max(104.0, self.rtp_total + 4, (self.golden or 0) + 4)
        sc = (x1 - x0) / top
        X = lambda v: x0 + v * sc  # noqa: E731
        ticks = "".join(f'<line class="grid" x1="{X(t):.1f}" y1="24" x2="{X(t):.1f}" y2="66"/><text x="{X(t):.1f}" y="96" text-anchor="middle" class="muted">{t}</text>' for t in range(0, int(top) + 1, 20))
        gold = ""
        if self.golden is not None:
            lab = "golden" if self.golden_kind == "golden" else "目標"
            gold = f'<rect x="{X(self.golden-0.2):.1f}" y="16" width="{0.4*sc:.1f}" height="46" fill="var(--accent-soft)"/><line x1="{X(self.golden):.1f}" y1="14" x2="{X(self.golden):.1f}" y2="64" stroke="var(--accent)" stroke-width="2"/><text x="{X(self.golden):.1f}" y="10" text-anchor="middle" class="lbl" style="font-weight:600;fill:var(--accent)">{lab} {self.golden:.2f}%</text>'
        return f"""<div class="chart-card"><div class="chart-head"><h4>RTP 組成與 {'golden' if self.golden_kind == 'golden' else '目標'} 對照</h4><span class="chart-sub">單位 % · 以總押注為分母</span></div>
<div class="svg-scroll"><svg class="chart" viewBox="0 0 {W} 104" role="img" aria-label="RTP 組成">{ticks}
<rect x="{X(0):.1f}" y="30" width="{max(0, X(self.rtp_main)-X(0)-2):.1f}" height="24" rx="3" fill="var(--c1)"><title>主遊戲 {self.rtp_main}%</title></rect>
<rect x="{X(self.rtp_main)+1:.1f}" y="30" width="{max(0, X(self.rtp_total)-X(self.rtp_main)-1):.1f}" height="24" rx="3" fill="var(--c2)"><title>免費遊戲 {self.rtp_free}%</title></rect>
<text x="{X(self.rtp_main/2):.1f}" y="46" text-anchor="middle" style="fill:#fff;font-weight:600">MG {self.rtp_main:.2f}%</text>
<text x="{X(self.rtp_main+self.rtp_free/2):.1f}" y="46" text-anchor="middle" style="fill:#fff;font-weight:600">FG {self.rtp_free:.2f}%</text>
{gold}<text x="{X(self.rtp_total):.1f}" y="78" text-anchor="end" class="lbl" style="font-weight:600">實測 {self.rtp_total:.4f}% ▲</text></svg></div>
<div class="legend"><span><i style="background:var(--c1)"></i>主遊戲</span><span><i style="background:var(--c2)"></i>免費／特色遊戲</span>{'<span><i style="background:var(--accent);width:2px;height:14px;border-radius:0"></i>' + ('golden（參數表加權理論值）' if self.golden_kind == 'golden' else '目標 RTP（quicktest.yaml）') + '</span>' if self.golden is not None else ''}</div></div>"""

    def gates(self):
        rows = []
        if self.delta is not None:
            tol = self.tol if self.tol is not None else 0.2
            ok = abs(self.delta) <= tol
            rows.append([f"總 RTP 收斂 {'golden' if self.golden_kind == 'golden' else '目標'}", f"{self.golden:.2f}% ± {tol:.2f} pp", f"{self.rtp_total:.4f}%", f"{self.delta:+.3f} pp", '<span class="ok">PASS</span>' if ok else '<span class="danger">FAIL</span>'])
        # 三向 checks（qt 模式 §2 的「- rtp：… [PASS]」條列）
        data = M.section(self.doc, "data")
        if data:
            for b in data["blocks"]:
                if b["kind"] != "ul":
                    continue
                for it in b["items"]:
                    m = re.match(r"^([\w:：\-]+)：(.*?)\s*\[(PASS|FAIL|SKIP)\]\s*$", it)
                    if m:
                        st = m.group(3)
                        rows.append([f"三向 {esc(m.group(1))}", "P-003", inline(m.group(2)), "—", f'<span class="{ {"PASS": "ok", "FAIL": "danger", "SKIP": "warn"}[st] }">{st}</span>'])
        fg = M.find_tables(self.doc, "fg_groups", "data")
        if fg:
            t = fg[0]
            head = [M._h(c) for c in t["head"]]
            ti = next((i for i, h in enumerate(head) if "理論" in h), None)
            ai = next((i for i, h in enumerate(head) if "實際" in h or "佔比" in h), None)
            if ti is not None and ai is not None and ti != ai:
                devs = [abs((M.tonum(r[ai]) or 0) - (M.tonum(r[ti]) or 0)) for r in t["rows"]]
                dev = max(devs) if devs else 0
                rows.append(["FG 強中弱實測 ≈ 表 F-1 權重", " / ".join(esc(r[ti]) for r in t["rows"]), " / ".join(esc(r[ai]) for r in t["rows"]), f"最大偏差 {dev:.2f} pp", '<span class="ok">PASS</span>' if dev < 0.5 else '<span class="warn">CHECK</span>'])
        pend = M.tonum(str(self.pending)) or 0
        rows.append(["待決議參數", "0", str(int(pend)), "—", '<span class="ok">PASS</span>' if not pend else '<span class="warn">待決議</span>'])
        return "<h3>驗收守門</h3>" + table(["驗收項", "基準", "實測", "偏差", "結果"], rows, cls="compact")

    # ---- generic section render
    SIDE = {"symhit", "range", "multiple", "asset", "decile"}

    def section_body(self, sid: str, skip_kinds: tuple = ()) -> str:
        s = M.section(self.doc, sid)
        if not s:
            return ""
        ctx = {"heading": ""}
        blocks = s["blocks"]
        out: list[str] = []
        i = 0
        while i < len(blocks):
            b = blocks[i]
            # 被略過的表（如總覽已畫的快測摘要）：連同它前面緊鄰的小標 / 引言一起略過
            if b["kind"] in ("h3", "h4", "bold", "quote"):
                j = i
                while j < len(blocks) and blocks[j]["kind"] in ("h3", "h4", "bold", "quote", "p"):
                    j += 1
                if j < len(blocks) and blocks[j]["kind"] == "table" and blocks[j].get("cls") in skip_kinds:
                    i = j + 1
                    continue
            if b["kind"] in ("h3", "h4", "bold"):
                ctx["heading"] = b["text"]
            if b["kind"] == "bold" and i + 1 < len(blocks) and blocks[i + 1]["kind"] == "table" and blocks[i + 1].get("caption") == b["text"]:
                i += 1   # 粗體小標已成為下一張表的 caption，不重複印
                continue
            if b["kind"] == "table" and b.get("cls") in skip_kinds:
                i += 1
                continue
            # 兩張可並排的表（各自可帶一個小標）→ .two
            if b["kind"] in ("h3", "bold", "table"):
                grp = self._side_group(blocks, i)
                if grp:
                    cols = []
                    for hb, tb in grp:
                        c = ""
                        if hb is not None:
                            ctx["heading"] = hb["text"]
                            c += render_blocks([hb], ctx=ctx)
                        c += render_blocks([tb], ctx=ctx)
                        cols.append(f"<div>{c}</div>")
                    out.append('<div class="two">' + "".join(cols) + "</div>")
                    i += sum(2 if hb is not None else 1 for hb, _ in grp)
                    continue
            out.append(render_blocks([b], ctx=ctx))
            i += 1
        return "".join(out)

    def _side_group(self, blocks: list[dict], i: int) -> list[tuple]:
        """從 i 起連續兩個「(小標?) + SIDE 表」→ [(小標|None, 表)]×2；否則 []。"""
        grp = []
        j = i
        while len(grp) < 2 and j < len(blocks):
            hb = None
            if blocks[j]["kind"] in ("h3", "bold"):
                hb = blocks[j]; j += 1
            if j < len(blocks) and blocks[j]["kind"] == "table" and blocks[j].get("cls") in self.SIDE:
                grp.append((hb, blocks[j])); j += 1
            else:
                break
        return grp if len(grp) == 2 else []

    def brief(self):
        return self.section_body("brief") or "<p>（無資料）</p>"

    def data(self):
        body = self.section_body("data", skip_kinds=("summary",))   # 摘要已在總覽畫過
        raw = self.pdata.get("raw_log") if self.pdata else None
        if raw:
            body += f'<details><summary>原始快測輸出 <span class="sub-note">prob-data.json raw_log，{len(raw.splitlines())} 行</span></summary><div><pre class="raw">{esc(raw)}</pre></div></details>'
        return body or '<p class="note">未快測。</p>'

    def flow(self):
        body = self.section_body("flow")
        return '<p>流程圖來自 Content 軌 §3（自動骨架 + 人工「流程補充」）；每個節點標對應的參數表編號。</p><div class="flow-wrap flow-md">' + (body or "<p>（無流程圖）</p>") + "</div>"

    def params(self):
        return '<p>依 Content 軌 §4 逐表轉出；權重欄以長條與列內色階呈現，表編號在標題左側，滑過列可看來源座標。</p>' + (self.section_body("params") or "<p>（無參數表）</p>")

    def kcards(self):
        return self.section_body("kcards") or '<p class="note">（尚未填寫 human:competitor）</p>'

    def hidden(self):
        return self.section_body("hidden") or '<p class="note">（尚未填寫；請在 prob-spec.md 的 human:hidden-rules 區填規則與設計目的）</p>'

    def strips(self):
        body = self.section_body("strips")
        fences = M.strip_fences(self.doc)
        counts = M.find_tables(self.doc, "strip_counts")
        if not body and not fences and not counts:
            return '<p class="note">Content 軌無輪帶資料（xlsx 無 Strip 分頁，或 odds.json 輪帶為 null）。</p>'
        legend = '<div class="legend"><span><i style="background:var(--sym-high)"></i>M 系列高賠</span><span><i style="background:var(--sym-low)"></i>低賠</span><span><i style="background:var(--sym-wild)"></i>WW</span><span><i style="background:var(--sym-sc)"></i>SC</span><span><i style="background:var(--sym-ss)"></i>SS</span></div>'
        if not body:  # 輪帶只在 §4（qt 模式 strip_counts）→ 指回 §4
            body = '<p class="note">輪帶符號顆數表在 §4 參數表；本節為帶面。</p>' + "".join(render_strip_fence({"lang": "strip", "text": "# " + f["name"] + "\n" + "\n".join(f"R{i+1}: " + " ".join(r) for i, r in enumerate(f["reels"]))}) for f in fences if f["section"] != "strips")
        return legend + body

    def appendix(self):
        srcs = self.fm.get("sources") if isinstance(self.fm.get("sources"), dict) else {}
        meta_src = self.meta.get("sources") or {}
        rows = []
        for k, p in srcs.items():
            sha = (meta_src.get(k) or {}).get("sha256_16", "")
            rows.append([esc(k), f'<code class="key wrap">{esc(p)}</code>', f"sha256 {sha}" if sha else ""])
        rows.append(["Content 軌", '<code class="key">prob-spec.md</code>', f'md sha256 {self.meta.get("md_sha256_16","")} · verdict {esc(self.verdict)}'])
        bounds = self.section_body("bounds")
        return "<h4>來源</h4>" + table(["層", "檔案", "說明"], rows, cls="compact") + (f"<h4>邊界聲明</h4>{bounds}" if bounds else "")

    def render(self, css: str, body_only: bool, md_name: str, md_sha: str) -> str:
        has_strips = bool(M.section(self.doc, "strips") or M.strip_fences(self.doc) or M.find_tables(self.doc, "strip_counts"))
        items = [("overview", "總覽", "0"), ("brief", "規格簡述", "1"), ("data", "數據資料", "2"), ("flow", "機率流程圖", "3"), ("params", "參數表", "4"), ("kcards", "手法對應", "5"), ("hidden", "隱性規則", "6")] + ([("strips", "輪帶", "7")] if has_strips else []) + [("appendix", "來源", "A")]
        main = [
            sec("overview", "0", "總覽：規格與快測一眼看", self.overview(), "prob-spec.md §2 快測摘要"),
            sec("brief", "1", "規格簡述", self.brief(), "prob-spec.md §1"),
            sec("data", "2", "數據資料（快測結果）", self.data(), "prob-spec.md §2"),
            sec("flow", "3", "機率流程圖", self.flow(), "prob-spec.md §3"),
            sec("params", "4", "參數表", self.params(), "prob-spec.md §4"),
            sec("kcards", "5", "競品資料／手法對應", self.kcards(), "prob-spec.md §5"),
            sec("hidden", "6", "隱性規則與設計目的", self.hidden(), "prob-spec.md §6"),
        ]
        if has_strips:
            main.append(sec("strips", "7", "輪帶 Strip", self.strips(), "prob-spec.md 附錄"))
        main.append(sec("appendix", "A", "來源與版本", self.appendix()))
        foot = f'<footer><span>{esc(self.game)} 機率規格書 · View 軌 · ark-game-prob ps_html（md-first）· 數字未經手抄</span><span>content-src: {md_name} sha256:{md_sha} ｜ 產出 {dt.date.today().isoformat()}</span></footer>'
        js = """<script>(function(){var links=[].slice.call(document.querySelectorAll('.toc a'));var secs=links.map(function(a){return document.getElementById(a.getAttribute('href').slice(1));});function setActive(id){links.forEach(function(a){a.classList.toggle('active',a.getAttribute('href')==='#'+id);});}if('IntersectionObserver' in window){var vis={};var io=new IntersectionObserver(function(es){es.forEach(function(e){vis[e.target.id]=e.isIntersecting?e.boundingClientRect.top:null;});var best=null;secs.forEach(function(s){if(vis[s.id]!=null&&(best==null||vis[s.id]<vis[best]))best=s.id;});if(best)setActive(best);},{rootMargin:'-10% 0px -70% 0px',threshold:[0,0.1]});secs.forEach(function(s){io.observe(s);});}setActive('overview');})();</script>"""
        mermaid = """<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script><script>if(window.mermaid){try{mermaid.initialize({startOnLoad:true,theme:(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'neutral')});}catch(e){}}</script>"""
        extra_css = (".flow-md pre.mermaid{background:transparent;border:0;overflow-x:auto}.human{border:1px dashed var(--accent);padding:8px 14px;margin:8px 0;border-radius:var(--radius-sm)}"
                     ".human::before{content:'人工填寫區';font-family:var(--font-mono);font-size:11px;color:var(--accent);display:block}.section table{margin:10px 0}"
                     ".tag{display:inline-block;font-family:var(--font-mono);font-size:10px;padding:0 6px;border-radius:3px;margin-right:4px;font-weight:600;background:var(--accent-soft);color:var(--accent)}"
                     ".pending{color:var(--danger);font-weight:600}.spec .v small{display:block;font-size:11px;color:var(--text-3);font-weight:400;margin-top:2px}.spec>div>div{outline:none;padding:0;background:transparent}"
                     ".section ul,.section ol{padding-left:22px;color:var(--text-2);font-size:14px;display:grid;gap:4px;margin:10px 0}.section blockquote{border-left:3px solid var(--border);padding:6px 14px;color:var(--text-2);margin:10px 0;font-size:14px}"
                     ".section pre code{font-family:var(--font-mono);font-size:12px}.section pre{background:var(--surface-2);padding:12px;border-radius:var(--radius-sm);overflow-x:auto;margin:10px 0}")
        head = f'<!-- content-src: {md_name} sha256:{md_sha} -->\n<title>{esc(self.game)} 機率規格書</title>\n<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&family=JetBrains+Mono:wght@400;500;600&display=swap">\n<style>\n{css}\n{extra_css}\n</style>\n'
        body = head + f'<div class="page">{self.header()}<div class="layout">{self.toc(items)}<main>{"".join(main)}{foot}</main></div></div>{js}{mermaid}'
        if body_only:
            return body
        return '<!DOCTYPE html>\n<html lang="zh-TW"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">' + body.replace("</style>\n", "</style>\n</head><body>", 1) + "</body></html>"


def render_file(md_p: pathlib.Path, out: pathlib.Path | None = None, css_p: pathlib.Path | None = None, body_only: bool = False) -> tuple[pathlib.Path, str, int]:
    """給 ps_probspec / ps_run 直接呼叫：回傳 (輸出路徑, 戳記 sha16, bytes)。"""
    d = md_p.parent
    metap, dp = d / "prob-spec.meta.json", d / "prob-data.json"
    meta = json.loads(metap.read_text(encoding="utf-8")) if metap.exists() else {}
    data = None
    if dp.exists():
        try:
            data = json.loads(dp.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            data = None
    css_p = css_p or DEFAULT_CSS
    css = css_p.read_text(encoding="utf-8") if css_p.exists() else ""
    sha = C.sha16(md_p)
    doc = M.parse_md(md_p.read_text(encoding="utf-8"))
    text = View(doc, meta, data).render(css, body_only, md_p.name, sha)
    out = out or d / "prob-spec.html"
    C.atomic_write(out, text)
    return out, sha, len(text.encode("utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", help="prob 目錄（含 prob-spec.md；prob-spec.meta.json / prob-data.json 選配）")
    ap.add_argument("--md", help="直接指定 prob-spec.md（md 模式；沒有 xlsx 也能渲染）")
    ap.add_argument("--css", default=str(DEFAULT_CSS))
    ap.add_argument("--out", help="輸出檔（預設 md 同目錄 prob-spec.html）")
    ap.add_argument("--body-only", action="store_true", help="不含 doctype/html/head/body（給會自己包骨架的發佈端）")
    a = ap.parse_args()
    if not a.dir and not a.md:
        C.fail("BAD_INPUT", "需要 --dir 或 --md")
    md_p = pathlib.Path(a.md) if a.md else pathlib.Path(a.dir) / "prob-spec.md"
    if not md_p.exists():
        C.fail("BAD_INPUT", f"缺 {md_p}", "先跑 ps_probspec（或照 assets/prob-spec.template.md 手寫）")
    out, sha, nbytes = render_file(md_p, pathlib.Path(a.out) if a.out else None, pathlib.Path(a.css), a.body_only)
    C.emit({"out": str(out), "bytes": nbytes, "stamp": sha, "sections": 9, "input": "prob-spec.md",
            "delivery": f"View 軌已落盤 {out}｜章節 9｜戳記 sha256:{sha}"}, {"stage": "ps_html"})


if __name__ == "__main__":
    main()
