#!/usr/bin/env python3
"""ps_html — View 軌：`prob-data.json` + `prob-spec.md` → 單檔 `prob-spec.html`（給企劃／機率／程式三方一眼看懂規格與快測結果）。

- 數字只來自 prob-data.json（xlsx 程式化轉出）；文字段（簡述 / 流程補充 / 手法對應 / 隱性規則）只來自 prob-spec.md 的人工區。
- 頁首戳記 `<!-- content-src: prob-spec.md sha256:<16> -->`，ps_lint PS-STALE 據此驗 md ↔ html 一致。
- 版面：左側章節導覽（窄螢幕變橫向膠囊）、總覽 KPI + RTP/golden 對照 + 驗收守門、2 數據資料（BASE INFO / 符號命中熱度 /
  輪帶組理論 vs 實測 / 贏分分布 / FG 詳細）、3 流程圖（mermaid）、4 參數表（權重列內色階與長條）、5 手法對應、6 隱性規則、7 輪帶、附錄。
- 雙主題（light / dark）、手機寬度不橫向捲動；CSS token 遵 ark-html-report 契約（--bg/--surface/--accent/--c1…）。
- 不依賴 LLM；缺段自動略過（例如未快測 → 總覽顯示「未快測」，§2 顯示空表）。

用法: python ps_html.py --dir data/prob/<slug> [--css assets/view.css] [--body-only]
交付格式：View 軌已落盤 <dir>/prob-spec.html｜章節 N｜戳記 sha256:<16>
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
from ps_probspec import md_to_html  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_CSS = HERE.parent / "assets" / "view.css"
HUMAN_RE = re.compile(r"<!--\s*human:([a-z0-9_-]+)\s*-->\n?(.*?)<!--\s*/human\s*-->", re.S)
GROUP_COLORS = ["var(--g1)", "var(--g2)", "var(--g3)", "var(--g4)"]
SERIES = ["var(--c1)", "var(--c2)", "var(--c3)", "var(--c4)", "var(--c5)", "var(--c6)"]


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


def pc(v, d=2) -> str:
    return "—" if v is None else f"{v:.{d}f}%"


def th(cols, numcols=()):
    return "<tr>" + "".join(f'<th{" class=num" if i in numcols else ""}>{c}</th>' for i, c in enumerate(cols)) + "</tr>"


def table(head, rows, numcols=(), cls="", caption=None, foot=None):
    h = f'<table class="table {cls}">'
    if caption:
        h += f"<caption>{caption}</caption>"
    h += "<thead>" + th(head, numcols) + "</thead><tbody>"
    for r in rows:
        h += "<tr>" + "".join(f'<td{" class=num" if i in numcols else ""}>{c}</td>' for i, c in enumerate(r)) + "</tr>"
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


def pct_of(s):
    try:
        return float(str(s).rstrip("%"))
    except ValueError:
        return None


# ------------------------------------------------------------------ builders
class View:
    def __init__(self, data: dict, md: str, meta: dict):
        self.D, self.md, self.meta = data, md, meta
        self.K = data.get("known") or {}
        self.R = data.get("report") or {}
        self.base = self.R.get("base") or {}
        self.summ = self.R.get("summary") or {}
        self.human = {m.group(1): m.group(2).strip() for m in HUMAN_RE.finditer(md)}
        rs = self.K.get("reelsets") or {}
        g = (rs.get("totals") or {}).get("TOTAL RTP")
        self.golden = (g * 100 if g is not None and g < 5 else g)
        gf = (rs.get("totals") or {}).get("FG RTP")
        self.golden_fg = (gf * 100 if gf is not None and gf < 5 else gf)
        self.rtp_total = self.summ.get("rtp_total")
        self.rtp_main = self.summ.get("rtp_main")
        self.rtp_free = self.summ.get("rtp_free")
        if self.rtp_total is None and self.base.get("Total"):
            self.rtp_total = pct_of(self.base["Total"][0])
        self.delta = (self.rtp_total - self.golden) if (self.rtp_total is not None and self.golden is not None) else None
        self.game = data.get("game") or data.get("slug")

    # ---- header / toc
    def header(self):
        verdict = self.meta.get("verdict", "未快測")
        cls = "ok" if verdict == "confirmed" else ("danger" if verdict == "rejected" else "warn")
        chips = [chip(f"來源 {esc(self.D['source']['name'])}"), chip(f"sha256 {self.D['source']['sha256_16']}", "ghost")]
        run = self.R.get("run") or {}
        if run.get("total"):
            chips.append(chip(f"快測 {run['total']/1e8:g} 億手" + (f" · {run['timestamp'][:10]}" if run.get("timestamp") else "")))
        if self.golden is not None:
            chips.append(chip(f"golden {self.golden:.2f}%"))
        chips.append(chip(f'<span class="dot"></span> 數據 {esc(verdict)}' + (f" · 誤差 {self.delta:+.3f} pp" if self.delta is not None else ""), cls))
        chips.append(chip(f"pending_params {self.meta.get('pending_params', 0)}", "ghost"))
        return f"""<header class="report-header"><div class="eyebrow">機率規格書 · PROB-SPEC · {esc(self.game)} {esc(self.D.get('slug'))} · {esc(self.meta.get('mode','xlsx'))} 模式</div>
<h1>{esc(self.game)} 機率規格書</h1>
<p class="lede">由機率表 xlsx 程式化轉出的規格與快測結果對照頁：總覽先看 RTP 是否收斂 golden，再往下看參數表、流程與輪帶。文字段落來自 Content 軌 prob-spec.md 的人工區，數字來自 prob-data.json，兩者皆可回溯。</p>
<div class="meta">{''.join(chips)}</div></header>"""

    def toc(self, items):
        lis = "".join(f'<li><a href="#{i}"><span class="no">{n}</span>{t}</a></li>' for i, t, n in items)
        return f'<nav class="toc" aria-label="章節"><div class="toc-title">Sections</div><ol>{lis}</ol></nav>'

    # ---- overview
    def overview(self):
        B = self.base
        if not B:
            return '<div class="callout callout-warning"><div class="callout-title">未快測</div><p>xlsx 沒有可解析的「數據資料」分頁。跑快測後把報表貼回 xlsx，重跑 ps_extract → ps_probspec → ps_html。</p></div>' + self.gates()
        main, free = B.get("Main") or [], B.get("Free") or []
        k = []
        if self.rtp_total is not None:
            d = f'<div class="kpi-delta good">{self.delta:+.3f} pp vs golden {self.golden:.2f}%</div>' if self.delta is not None else ""
            k.append(f'<div class="kpi hero"><div class="kpi-label">總 RTP</div><div class="kpi-value">{self.rtp_total:.2f}<small>%</small></div>{d}</div>')
        if main:
            k.append(f'<div class="kpi"><div class="kpi-label">主遊戲 RTP</div><div class="kpi-value">{esc(main[0]).replace("%","")}<small>%</small></div><div class="kpi-delta">Hit {esc(main[2])} · 每 {esc(main[1])} 手中獎</div></div>')
        if free:
            share = f"佔總 RTP {pct_of(free[0]) / self.rtp_total * 100:.1f}%" if (self.rtp_total and pct_of(free[0])) else ""
            k.append(f'<div class="kpi"><div class="kpi-label">免費遊戲 RTP</div><div class="kpi-value">{esc(free[0]).replace("%","")}<small>%</small></div><div class="kpi-delta">{share}</div></div>')
            k.append(f'<div class="kpi"><div class="kpi-label">FG 觸發率</div><div class="kpi-value">{esc(free[2]).replace("%","")}<small>%</small></div><div class="kpi-delta">每 {esc(free[1])} 手觸發一次</div></div>')
            k.append(f'<div class="kpi"><div class="kpi-label">FG 平均倍率</div><div class="kpi-value">{esc(free[3])}<small>x</small></div><div class="kpi-delta">最大 {esc(free[6]) if len(free) > 6 else "—"}x</div></div>')
        if main:
            k.append(f'<div class="kpi"><div class="kpi-label">主遊戲最大倍數</div><div class="kpi-value">{esc(main[6]) if len(main) > 6 else "—"}<small>x</small></div><div class="kpi-delta">{esc((self.R.get("run") or {}).get("flag",""))}</div></div>')
        kpis = f'<div class="kpi-grid">{"".join(k)}</div>'
        return kpis + self.rtp_bar() + self.gates()

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
            gold = f'<rect x="{X(self.golden-0.2):.1f}" y="16" width="{0.4*sc:.1f}" height="46" fill="var(--accent-soft)"/><line x1="{X(self.golden):.1f}" y1="14" x2="{X(self.golden):.1f}" y2="64" stroke="var(--accent)" stroke-width="2"/><text x="{X(self.golden):.1f}" y="10" text-anchor="middle" class="lbl" style="font-weight:600;fill:var(--accent)">golden {self.golden:.2f}%</text>'
        svg = f"""<div class="chart-card"><div class="chart-head"><h4>RTP 組成與 golden 對照</h4><span class="chart-sub">單位 % · 以總押注為分母</span></div>
<div class="svg-scroll"><svg class="chart" viewBox="0 0 {W} 104" role="img" aria-label="RTP 組成">{ticks}
<rect x="{X(0):.1f}" y="30" width="{X(self.rtp_main)-X(0)-2:.1f}" height="24" rx="3" fill="var(--c1)"><title>主遊戲 {self.rtp_main}%</title></rect>
<rect x="{X(self.rtp_main)+1:.1f}" y="30" width="{X(self.rtp_total)-X(self.rtp_main)-1:.1f}" height="24" rx="3" fill="var(--c2)"><title>免費遊戲 {self.rtp_free}%</title></rect>
<text x="{X(self.rtp_main/2):.1f}" y="46" text-anchor="middle" style="fill:#fff;font-weight:600">MG {self.rtp_main:.2f}%</text>
<text x="{X(self.rtp_main+self.rtp_free/2):.1f}" y="46" text-anchor="middle" style="fill:#fff;font-weight:600">FG {self.rtp_free:.2f}%</text>
{gold}<text x="{X(self.rtp_total):.1f}" y="78" text-anchor="end" class="lbl" style="font-weight:600">實測 {self.rtp_total:.4f}% ▲</text></svg></div>
<div class="legend"><span><i style="background:var(--c1)"></i>主遊戲</span><span><i style="background:var(--c2)"></i>免費遊戲</span>{'<span><i style="background:var(--accent);width:2px;height:14px;border-radius:0"></i>golden（參數表加權理論值）</span>' if self.golden is not None else ''}</div></div>"""
        return svg

    def gates(self):
        rows = []
        if self.delta is not None:
            ok = abs(self.delta) <= 0.2
            rows.append(["總 RTP 收斂 golden", f"{self.golden:.2f}% ± 0.20 pp", f"{self.rtp_total:.4f}%", f"{self.delta:+.3f} pp", '<span class="ok">PASS</span>' if ok else '<span class="danger">FAIL</span>'])
        if self.golden_fg is not None and self.rtp_free is not None:
            d = self.rtp_free - self.golden_fg
            rows.append(["免費遊戲 RTP 對 golden", f"{self.golden_fg:.2f}%", f"{self.rtp_free:.4f}%", f"{d:+.3f} pp", '<span class="ok">PASS</span>' if abs(d) <= 0.2 else '<span class="warn">CHECK</span>'])
        fg = self.R.get("fg_detail") or {}
        w = next((x for x in self.K.get("weights", []) if x["block"].startswith("F-1")), None)
        if fg.get("groups") and w:
            tot = sum(i["weight"] for i in w["items"] if isnum(i["weight"]))
            exp = {i["label"]: i["weight"] / tot * 100 for i in w["items"] if isnum(i["weight"])}
            dev = max(abs(g["pct"] - exp.get(g["name"], g["pct"])) for g in fg["groups"])
            rows.append(["FG 強中弱實測 ≈ 表 F-1 權重", " / ".join(f"{exp[g['name']]:.0f}" for g in fg["groups"] if g["name"] in exp) + " %", " / ".join(f"{g['pct']:.2f}" for g in fg["groups"]) + " %", f"最大偏差 {dev:.2f} pp", '<span class="ok">PASS</span>' if dev < 0.5 else '<span class="warn">CHECK</span>'])
        pend = self.meta.get("pending_params", 0)
        rows.append(["待決議參數", "0", str(pend), "—", '<span class="ok">PASS</span>' if not pend else '<span class="warn">待決議</span>'])
        return "<h3>驗收守門</h3>" + table(["驗收項", "基準", "實測", "偏差", "結果"], rows, cls="compact")

    # ---- §1 brief
    def brief(self):
        out = []
        b = self.K.get("board") or {}
        if b:
            out.append('<div class="spec">' + "".join(f'<div><div class="k">{esc(k)}</div><div class="v">{num(v)}</div></div>' for k, v in b.items()) + "</div>")
        if self.human.get("summary"):
            out.append('<div class="card"><h4>機率人員簡述</h4>' + md_to_html(self.human["summary"]) + "</div>")
        pt = self.K.get("paytable") or []
        if pt:
            ks = list(pt[0]["odds"].keys())
            out.append("<h3>Pay table <span class=\"sub-note\">odds × Line bet</span></h3>" + table(["層級", "符號"] + [f"x{k}" for k in ks], [[esc(r["tier"]), f'<span class="sym {"high" if str(r["sym"]).startswith("M") else "low"}">{esc(r["sym"])}</span>'] + [num(r["odds"].get(k)) for k in ks] for r in pt], numcols=tuple(range(2, 2 + len(ks))), cls="compact"))
        if self.D.get("brief"):
            out.append('<details><summary>xlsx「規格簡述」分頁原文 <span class="sub-note">請機率人員確認是否為樣板殘留</span></summary><div><ul>' + "".join(f"<li>{esc(' ｜ '.join(r))}</li>" for r in self.D["brief"]) + "</ul></div></details>")
        return "".join(out) or "<p>（無資料）</p>"

    # ---- §2 data
    def data(self):
        R, out = self.R, []
        run = R.get("run") or {}
        if run:
            cells = []
            for k, lab in (("version", "引擎版本"), ("timestamp", "執行時間"), ("total", "總手數"), ("seconds", "耗時 (s)"), ("speed", "速度"), ("total_bet", "總押注"), ("total_win", "總贏分"), ("flag", "旗標")):
                if run.get(k) not in (None, ""):
                    v = run[k]
                    cells.append(f'<div><div class="k">{lab}</div><div class="v">{num(v) if isnum(v) else esc(str(v)[:19])}</div></div>')
            out.append('<div class="spec">' + "".join(cells) + "</div>")
        if self.base:
            rows = []
            for name in ("Main", "Free", "Feature", "Main Fea", "Free Fea", "GRAND", "Total"):
                v = self.base.get(name)
                if not v or (name not in ("Main", "Free", "Total") and all(x in ("0.0000%", "-", "0.00") for x in v)):
                    continue
                rows.append([{"Main": "主遊戲", "Free": "免費遊戲", "Total": "總計"}.get(name, name)] + [esc(x) for x in v] + [""] * (7 - len(v)))
            out.append("<h3>2.1 基本資訊 <span class=\"sub-note\">BASE INFO</span></h3>" + table(["區塊", "GAME %（RTP）", "Freq", "Trigger %", "Multi", "PlayTimes", "RetriRate", "MaxMulti"], rows, numcols=(1, 2, 3, 4, 5, 6, 7), cls="compact"))
        if R.get("symbol_hit_rate") or R.get("symbol_hit_rtp"):
            out.append("<h3>2.2 主遊戲符號命中</h3><div class=\"two\">" + self.symtab(R.get("symbol_hit_rate"), "命中率 Hit Rate") + self.symtab(R.get("symbol_hit_rtp"), "RTP 貢獻 Hit RTP") + "</div>")
        if R.get("reel_set_rtp"):
            out.append("<h3>2.3 輪帶組 RTP：理論 vs 實測</h3>" + self.reelset_table())
        two = []
        if R.get("special_range"):
            two.append(self.range_table())
        if R.get("multiple"):
            two.append(self.multiple_table())
        if two:
            out.append("<h3>2.4 贏分分布</h3><div class=\"two\">" + "".join(two) + "</div>")
        two = []
        if R.get("asset_100"):
            two.append(table(["100 手後剩餘資產", "佔比"], [[esc(a["range"]), bar(a["pct"], 100, pc(a["pct"]))] for a in R["asset_100"]], caption="100 手資產轉 100 手後分布", cls="compact"))
        if R.get("decile"):
            two.append(table(["分位", "Total", "Main", "Free", "F_Spin"], [[esc(d["label"])] + [esc(v) for v in d["vals"]] + [""] * (4 - len(d["vals"])) for d in R["decile"]], numcols=(1, 2, 3, 4), caption="十分位 Decile", cls="compact"))
        if two:
            out.append('<div class="two">' + "".join(two) + "</div>")
        if R.get("fg_detail"):
            out.append(self.fg_detail())
        if self.D.get("raw_log"):
            out.append(f'<details><summary>原始快測輸出 <span class="sub-note">xlsx 數據資料分頁全文，{len(self.D["raw_log"].splitlines())} 行</span></summary><div><pre class="raw">{esc(self.D["raw_log"])}</pre></div></details>')
        return "".join(out) or '<p class="note">未快測。</p>'

    def symtab(self, dat, title):
        if not dat:
            return ""
        keys = [k for k in dat if k != "TOTAL"]
        n = max(len(v) for v in dat.values())
        hdr = ["符號"] + [f"x{i+1}" for i in range(n - 1)] + ["TOTAL"]
        # 第一欄 x1/x2 常為 0 → 省略全 0 欄
        keep = [i for i in range(n - 1) if any(dat[k][i] for k in keys)]
        mx = max(dat[k][i] for k in keys for i in keep) if keep else 1
        h = f'<table class="table compact"><caption>{title}</caption><thead>' + th(["符號"] + [f"x{i+1}" for i in keep] + ["TOTAL"], tuple(range(1, len(keep) + 2))) + "</thead><tbody>"
        for k in keys:
            h += f"<tr><td>{esc(k)}</td>" + "".join(heat(dat[k][i], mx, pc(dat[k][i])) for i in keep) + f'<td class="num"><strong>{pc(dat[k][-1])}</strong></td></tr>'
        if "TOTAL" in dat:
            h += "</tbody><tfoot><tr><td>TOTAL</td>" + "".join(f'<td class="num">{pc(dat["TOTAL"][i])}</td>' for i in keep) + f'<td class="num">{pc(dat["TOTAL"][-1])}</td></tr></tfoot>'
        return f'<div class="table-wrap">{h}</table></div>'

    def reelset_table(self):
        sim = {r["set"]: r for r in self.R["reel_set_rtp"]}
        rs = self.K.get("reelsets")
        rows, mx = [], max(r["total"] for r in sim.values())
        if rs:
            wsum = (rs.get("totals") or {}).get("weight_sum") or sum(s["weight"] for s in rs["sets"] if isnum(s["weight"]))
            theo_key = next((k for k in (rs["sets"][0].get("extra") or {}) if "TOTAL" in k.upper()), None)
            if theo_key:
                mx = max(mx, max((s["extra"].get(theo_key) or 0) * 100 for s in rs["sets"]))
            for s in rs["sets"]:
                m = sim.get(s["idx"])
                flags = '<span class="flagcell">' + "".join(f'<span class="flag{" on" if f else ""}">{i+1}</span>' for i, f in enumerate(s["flags"])) + "</span>"
                theo = (s["extra"].get(theo_key) or 0) * 100 if theo_key else None
                desc = next((v for k, v in s["extra"].items() if isinstance(v, str)), "")
                rows.append([f"<strong>{s['idx']}</strong>", flags, f'<span style="white-space:nowrap">{esc(desc)}</span>', num(s["weight"]), pc(s["weight"] / wsum * 100, 1) if wsum else "—",
                             bar(theo, mx, pc(theo), "var(--c6)") if theo is not None else "—",
                             bar(m["total"], mx, pc(m["total"]), "var(--c1)") if m else "—", pc(m["fg"]) if m and m.get("fg") is not None else "—", f'{m["spins"]:,}' if m and m.get("spins") else "—"])
            wsim = sum(sim[s["idx"]]["total"] * s["weight"] for s in rs["sets"] if s["idx"] in sim) / wsum if wsum else None
            foot = ["加權", "", "Σ(組 RTP × 權重) / Σ權重", num(wsum), "100%", pc(self.golden) if self.golden is not None else "—", pc(wsim) if wsim is not None else "—", "", ""]
            return table(["組", "R1–R5 換帶", "說明", "權重", "佔比", "理論 Total RTP（xlsx）", "實測 Total RTP", "實測 FG RTP", "實測手數"], rows, numcols=(3, 4, 7, 8), foot=foot, cls="compact") + '<p class="note">灰底旗標 = 該輪換用替代帶。理論值來自參數表的單組 RTP，實測值來自快測；單組差異加權後應收斂到總 RTP。</p>'
        for k, m in sim.items():
            rows.append([str(k), bar(m["total"], mx, pc(m["total"])), pc(m["fg"]) if m.get("fg") is not None else "—"])
        return table(["組", "實測 Total RTP", "實測 FG RTP"], rows, cls="compact")

    def range_table(self):
        rows, mx = [], max(r["rtp"][0] for r in self.R["special_range"])
        for r in self.R["special_range"]:
            if r["appear"][0] == 0 and r["rtp"][0] == 0:
                continue
            rows.append([esc(r["range"]), pc(r["appear"][0]), pc(r["appear"][1]), pc(r["appear"][2]), bar(r["rtp"][0], mx, pc(r["rtp"][0]), "var(--c2)"), pc(r["rtp"][1]), pc(r["rtp"][2])])
        return table(["贏分區間（倍）", "出現 Total", "Main", "Free", "RTP Total", "Main", "Free"], rows, numcols=(1, 2, 3, 5, 6), caption="各贏分區間出現率與 RTP 貢獻", cls="compact")

    def multiple_table(self):
        rows = [[esc(m["range"]), f'{m["spins_per_hit"]:,.2f}', f'≥ {m["ge"]}', f'{m["spins_per_hit_ge"]:,.2f}'] for m in self.R["multiple"] if m["spins_per_hit"] > 0]
        return table(["贏分區間（倍）", "約每幾局", "累計", "約每幾局"], rows, numcols=(1, 3), caption="倍數出現頻率（局數）", cls="compact")

    def fg_detail(self):
        fg = self.R["fg_detail"]
        out = ['<h3>2.5 免費遊戲詳細統計' + (f' <span class="sub-note">FG 總觸發 {fg["trigger_total"]:,} 次</span>' if fg.get("trigger_total") else "") + "</h3>"]
        cards = []
        if fg.get("base_avg") is not None:
            a = fg.get("all888") or {}
            cards.append(f'<div class="card"><h4>初始基底</h4><div class="kpi-value" style="font-size:24px">{fg["base_avg"]}<small>x</small></div><p>平均進場基底倍數。' + (f'全放 888 事件 {a["count"]:,} 次（佔 FG {a["pct"]}%），平均贏分 {fg.get("all888_avg")} 倍。' if a else "") + "</p></div>")
        if fg.get("settle_avg") is not None:
            cards.append(f'<div class="card"><h4>結算面</h4><div class="kpi-value" style="font-size:24px">{fg["settle_avg"]}<small>x</small></div><p>平均 FG 贏分；最大 {fg.get("settle_max"):,} 倍。標準差 {fg.get("sd")}、變異係數 {fg.get("cv")}。' + (f'平均總乘倍 {fg["avg_mult"]}。' if fg.get("avg_mult") else "") + "</p></div>")
        if fg.get("avg_times"):
            cards.append('<div class="card"><h4>每場平均收集次數</h4><div class="legend" style="margin-top:4px">' + "".join(f'<span><i style="background:{SERIES[i % 6]}"></i>{esc(k)} <b class="mono">{v}</b></span>' for i, (k, v) in enumerate(fg["avg_times"].items())) + "</div></div>")
        if fg.get("contrib"):
            items = [(k, v, SERIES[i % 6]) for i, (k, v) in enumerate(fg["contrib"])]
            segs = "".join(f'<div style="flex:{v} 0 0;background:{c}" title="{esc(k)} {v}%">{(esc(k) + " " + pc(v, 1)) if v >= 8 else ""}</div>' for k, v, c in items if v > 0)
            leg = "".join(f'<span><i style="background:{c}"></i>{esc(k)} <b class="mono">{pc(v)}</b></span>' for k, v, c in items)
            cards.append(f'<div class="card"><h4>FG 贏分貢獻拆解</h4><div class="stack">{segs}</div><div class="legend">{leg}</div></div>')
        if cards:
            out.append(f'<div class="card-grid cols-4" style="margin-top:14px">{"".join(cards)}</div>')
        two = []
        if fg.get("trigger_dist"):
            mx = max(d["pct"] for d in fg["trigger_dist"])
            t = table(["觸發顆數", "次數", "佔 FG"], [[f'{d["k"]} 顆', f'{d["count"]:,}', bar(d["pct"], mx, pc(d["pct"]), "var(--c2)")] for d in fg["trigger_dist"]], numcols=(1,), caption="觸發面：進場特殊符號顆數分布", cls="compact")
            w, s = fg.get("with_ss"), fg.get("ss_mult")
            if w:
                t += f'<div class="legend" style="margin-top:8px"><span>有 SS <b class="mono">{w["pct"]}%</b></span><span>無 SS <b class="mono">{w["no_pct"]}%</b></span>' + (f'<span>SS 乘倍 <b class="mono">{s["pct"]}%</b></span><span>SS 數值 <b class="mono">{s["value_pct"]}%</b></span>' if s else "") + "</div>"
            two.append("<div>" + t + "</div>")
        if fg.get("sc_enter"):
            mx = max(x["avg"] for x in fg["sc_enter"])
            two.append(table(["進場 SC 顆數", "次數", "佔比", "均 FG 倍率"], [[f'{x["sc"]} 顆', f'{x["count"]:,}', pc(x["pct"]), bar(x["avg"], mx, num(x["avg"]), "var(--c2)")] for x in fg["sc_enter"]], numcols=(1, 2), caption="各進場 SC 顆數 → 平均 FG 倍率", cls="compact"))
        if two:
            out.append('<div class="two">' + "".join(two) + "</div>")
        if fg.get("groups"):
            w = next((x for x in self.K.get("weights", []) if x["block"].startswith("F-1")), None)
            exp = {}
            if w:
                tot = sum(i["weight"] for i in w["items"] if isnum(i["weight"]))
                exp = {i["label"]: (i["weight"], i["weight"] / tot * 100) for i in w["items"] if isnum(i["weight"])}
            grp_rtp = dict(fg.get("group_rtp") or [])
            mxr = max(grp_rtp.values()) if grp_rtp else 1
            det = {d[0]: d for d in (fg.get("group_detail") or [])}
            cols = fg.get("group_detail_cols") or []
            rows = []
            for i, g in enumerate(fg["groups"]):
                e = exp.get(g["name"])
                r = [f'<span class="chip" style="border-color:{GROUP_COLORS[i % 4]};color:{GROUP_COLORS[i % 4]}">{esc(g["name"])}</span>', num(e[0]) if e else "—", pc(e[1], 0) if e else "—", pc(g["pct"]), f'{g["count"]:,}', bar(grp_rtp.get(g["name"], 0), mxr, pc(grp_rtp.get(g["name"])), GROUP_COLORS[i % 4]) if grp_rtp else "—"]
                if g["name"] in det:
                    r += [esc(x) for x in det[g["name"]][2:]]
                rows.append(r)
            head = ["組別", "F-1 權重", "理論佔比", "實際佔比", "次數", "FG RTP 貢獻"] + ([esc(c) for c in cols[2:]] if cols else [])
            out.append("<h4>強中弱分層：設計權重 vs 實測</h4>" + table(head, rows, numcols=tuple(range(1, len(head))), cls="compact"))
        if fg.get("ss_rows"):
            out.append(table(["進場 SS 顆數"] + [esc(c) for c in fg["ss_cols"][1:]], [[f"{r[0]} 顆", f"{int(r[1]):,}"] + [esc(x) for x in r[2:]] for r in fg["ss_rows"]], numcols=tuple(range(1, len(fg["ss_cols"]))), caption="依進場 SS 顆數分項", cls="compact"))
        if fg.get("mult_decile"):
            out.append(table(["分位"] + [esc(k) for k, _ in fg["mult_decile"]], [["最後乘倍"] + [esc(v) for _, v in fg["mult_decile"]]], numcols=tuple(range(1, 11)), caption=f'最後乘倍十分位（{esc(fg.get("mult_note",""))}）', cls="compact"))
        return "".join(out)

    # ---- §3 flow
    def flow(self):
        m = re.search(r"## 3\. 機率流程圖(.*?)(?=\n## 4\.)", self.md, re.S)
        body = md_to_html(m.group(1)) if m else "<p>（無流程圖）</p>"
        return '<p>流程圖來自 Content 軌 §3（自動骨架 + 人工「流程補充」）；每個節點標對應的參數表編號。</p><div class="flow-wrap flow-md">' + body + "</div>"

    # ---- §4 params
    def params(self):
        out = ['<p>依 xlsx「參數表」逐表轉出；權重欄以長條與列內色階呈現。右上角標籤為表編號，滑過列可對照來源座標（Content 軌 §4 的來源欄）。</p>']
        K = self.K
        by_block = {}
        for kind in ("weights", "dual", "yesno", "matrix", "series", "scalars"):
            for x in K.get(kind) or []:
                by_block.setdefault(x["block"], []).append((kind, x))
        if K.get("reelsets"):
            by_block.setdefault(K["reelsets"]["block"], []).append(("reelsets", K["reelsets"]))
        for b in (self.D.get("params") or {}).get("blocks", []):
            bid = b["id"]
            if bid in ("基本資訊", "Odds表", "Odds 表", "Pay table"):
                continue
            tid = f'<span class="tid">表 {esc(bid)}</span>' if re.match(r"^[A-Z]-", bid) else ""
            out.append(f'<h3>{tid}{esc(b.get("title") or "")}</h3>')
            rec = by_block.get(bid, [])
            if not rec:
                for t in b["tables"]:
                    out.append(self.generic_table(t))
                continue
            for kind, x in rec:
                out.append(getattr(self, "r_" + kind)(x))
        if self.human.get("param-notes"):
            out.append('<div class="card"><h4>參數備註</h4>' + md_to_html(self.human["param-notes"]) + "</div>")
        return "".join(out)

    def generic_table(self, t):
        rows = t["rows"]
        flat = [v for r in rows for v in r["cells"] if v is not None]
        if len(rows) == 1 and len(flat) == 1:
            return f"<h4>{esc(flat[0])}</h4>"
        width = max(len(r["cells"]) for r in rows)
        first = rows[0]["cells"]
        if sum(1 for v in first if isinstance(v, str)) >= 2:
            head, body = [esc(v) if v is not None else "" for v in first], rows[1:]
        else:
            head, body = [""] * width, rows
        return table(head + [""] * (width - len(head)), [[num(v) if v is not None else "" for v in r["cells"]] + [""] * (width - len(r["cells"])) for r in body], cls="compact")

    def r_reelsets(self, x):
        wsum = (x.get("totals") or {}).get("weight_sum") or sum(s["weight"] for s in x["sets"] if isnum(s["weight"]))
        mx = max(s["weight"] for s in x["sets"] if isnum(s["weight"]))
        extra_keys = [k for k in (x["sets"][0].get("extra") or {})]
        rows = []
        for s in x["sets"]:
            flags = '<span class="flagcell">' + "".join(f'<span class="flag{" on" if f else ""}">{i+1}</span>' for i, f in enumerate(s["flags"])) + "</span>"
            rows.append([f"<strong>{s['idx']}</strong>", flags, bar(s["weight"], mx, num(s["weight"])), pc(s["weight"] / wsum * 100, 1) if wsum else "—"] + [(pc(v * 100) if isnum(v) and v < 5 and "RTP" in k.upper() else (num(v) if isnum(v) else f'<span style="white-space:nowrap">{esc(v)}</span>')) for k in extra_keys for v in [s["extra"].get(k)]])
        foot = ["Σ", "", num(wsum), "100%"] + [(pc(v * 100) if isnum(v) and v < 5 else num(v)) if (v := (x.get("totals") or {}).get(k)) is not None else "" for k in extra_keys]
        return table(["Index", "R1–R5 換帶", "權重", "佔比"] + [esc(k) for k in extra_keys], rows, numcols=(2, 3) + tuple(4 + i for i, k in enumerate(extra_keys) if "RTP" in k.upper()), foot=foot, cls="compact")

    def r_weights(self, x):
        items = [i for i in x["items"]]
        nums_ = [i["weight"] for i in items if isnum(i["weight"])]
        tot, mx = sum(nums_), (max(nums_) if nums_ else 1)
        rows = [[esc(i["label"]), bar(i["weight"], mx, num(i["weight"])) if isnum(i["weight"]) else esc(i["weight"]), pc(i["weight"] / tot * 100, 1) if (tot and isnum(i["weight"])) else "—"] + ([esc(" ".join(str(r) for r in i["rest"]))] if i["rest"] else [""]) for i in items]
        return table(["項目", "權重", "%", "備註"], rows, numcols=(2,), foot=["Σ", num(tot), "100%", ""], cls="compact")

    def r_dual(self, x):
        names = x.get("names") or [f"欄 {i+1}" for i in range(len(x["columns"]))]
        cols = x["columns"]
        n = max(len(c["pairs"]) for c in cols)
        head, rows = [], []
        for name in names[:len(cols)]:
            head += [f"{esc(name)} 倍數", f"{esc(name)} 權重", "%"]
        hues = ["var(--sym-sc)", "var(--sym-ss)", "var(--c3)", "var(--c4)"]
        for i in range(n):
            r = []
            for j, c in enumerate(cols):
                if i < len(c["pairs"]):
                    v, w = c["pairs"][i]
                    mx = max(p[1] for p in c["pairs"] if isnum(p[1]))
                    tot = c.get("total") or sum(p[1] for p in c["pairs"] if isnum(p[1]))
                    r += [num(v) if isnum(v) else esc(v), bar(w, mx, num(w), hues[j % 4]), pc(w / tot * 100, 1) if tot else "—"]
                else:
                    r += ["", "", ""]
            rows.append(r)
        foot = []
        for c in cols:
            ex = " · ".join(f"{esc(k)} {num(v)}" for k, v in (c.get("extra") or {}).items())
            foot += [ex, num(c.get("total")) if c.get("total") is not None else "", "100%"]
        return table(head, rows, numcols=tuple(i for i in range(len(head)) if i % 3 != 1), foot=foot, cls="compact")

    def r_yesno(self, x):
        rows = [[f'<span class="chip" style="border-color:{GROUP_COLORS[i % 4]};color:{GROUP_COLORS[i % 4]}">{esc(r["name"])}</span>', bar(r["yes"] or 0, (r["yes"] or 0) + (r["no"] or 0), num(r["yes"]), "var(--c3)"), num(r["no"])] for i, r in enumerate(x["rows"])]
        return table(["組別", "是", "否"], rows, numcols=(2,), cls="compact")

    def r_matrix(self, x):
        head = x["head"]
        # 去掉尾端全 0 欄（保留權重和／平均欄）
        numeric_idx = [i for i, h in enumerate(head) if re.fullmatch(r"\d+(\.\d+)?", str(h))]
        tail_idx = [i for i, h in enumerate(head) if i not in numeric_idx]
        last = numeric_idx[-1] if numeric_idx else -1
        while last > 0 and all(not (g["values"][last] if last < len(g["values"]) else 0) for g in x["groups"]):
            last -= 1
        keep = [i for i in numeric_idx if i <= last] + tail_idx
        hue = SERIES[(sum(map(ord, x.get("caption") or "")) % 6)]
        h = f'<table class="table compact{" tight" if len(keep) > 12 else ""}"><caption>{esc(x.get("caption") or x.get("title"))}</caption><thead>' + th(["組別"] + [esc(head[i]) for i in keep], tuple(range(1, len(keep) + 1))) + "</thead><tbody>"
        for gi, g in enumerate(x["groups"]):
            vals = g["values"]
            nums_ = [vals[i] for i in numeric_idx if i < len(vals) and isnum(vals[i])]
            mx = max(nums_) if nums_ else 1
            h += f'<tr><td><span class="chip" style="border-color:{GROUP_COLORS[gi % 4]};color:{GROUP_COLORS[gi % 4]}">{esc(g["name"])}</span></td>'
            for i in keep:
                v = vals[i] if i < len(vals) else None
                if i in numeric_idx:
                    h += heat(v or 0, mx, num(v) if v else '<span style="opacity:.35">0</span>', hue)
                else:
                    h += f'<td class="num"><strong>{num(v)}</strong></td>'
            h += "</tr>"
        h += "</tbody></table>"
        return f'<div class="table-wrap">{h}</div>'

    def r_series(self, x):
        head = x.get("head")
        rows = []
        if head:
            for r in x["rows"]:
                mx = max(r["values"][:-1] or [1]) if len(r["values"]) > 1 else 1
                rows.append([esc(r["label"])] + [bar(v, mx, num(v), SERIES[i % 6]) for i, v in enumerate(r["values"][:-1])] + [num(r["values"][-1])])
            return table([esc(h) or "" for h in head] if len(head) == len(rows[0]) else ["項目"] + [esc(h) for h in head[1:]], rows, cls="compact")
        # 兩列：第一列是索引、第二列是權重
        if len(x["rows"]) >= 2:
            idx, w = x["rows"][0], x["rows"][1]
            mx = max(w["values"] or [1])
            return table([esc(idx["label"])] + [num(v) for v in idx["values"]], [[esc(w["label"])] + [bar(v, mx, num(v), "var(--c2)") if v else '<span style="opacity:.35">0</span>' for v in w["values"]]], numcols=tuple(range(1, len(idx["values"]) + 1)), cls="compact")
        return self.generic_table({"rows": [{"cells": [r["label"]] + r["values"]} for r in x["rows"]]})

    def r_scalars(self, x):
        return f'<div class="card" style="display:inline-block;min-width:220px;margin:6px 8px 6px 0"><div class="kpi-label">{esc(x.get("label") or x.get("title"))}</div><div class="kpi-value">{num(x["value"])}</div></div>'

    # ---- §5 / §6 from md human blocks
    def md_section(self, hid, fallback):
        txt = self.human.get(hid)
        return md_to_html(txt) if txt else f"<p class=\"note\">{fallback}</p>"

    def hidden(self):
        out = []
        if self.D.get("hidden"):
            out.append('<details><summary>xlsx「隱性規則」分頁原文</summary><div><ul>' + "".join(f"<li>{esc(' ｜ '.join(r))}</li>" for r in self.D["hidden"]) + "</ul></div></details>")
        out.append(self.md_section("hidden-rules", "（尚未填寫；請在 prob-spec.md 的 human:hidden-rules 區填規則與設計目的）"))
        return "".join(out)

    # ---- §7 strips
    def strips(self):
        S = self.D.get("strips") or {}
        if not S:
            return '<p class="note">xlsx 無輪帶分頁。</p>'
        cls = lambda s: "WW" if s in ("WW", "WILD") else ("SC" if s == "SC" else ("SS" if s == "SS" else ("high" if s.startswith("M") else "low")))  # noqa: E731
        out = ['<div class="legend"><span><i style="background:var(--sym-high)"></i>M 系列高賠</span><span><i style="background:var(--sym-low)"></i>低賠</span><span><i style="background:var(--sym-wild)"></i>WW</span><span><i style="background:var(--sym-sc)"></i>SC</span><span><i style="background:var(--sym-ss)"></i>SS</span></div>']
        first = True
        for key, groups in S.items():
            for name, d in groups.items():
                lens = [len(r) for r in d["reels"]]
                ctab = ""
                if d.get("counts"):
                    tot = next((c for c in d["counts"] if c[0] == "Total"), None)
                    rows = []
                    for c in d["counts"]:
                        if c[0] == "Total":
                            continue
                        cells = "".join(heat(v or 0, (tot[i + 1] if tot and tot[i + 1] else 1), num(v) if v else '<span style="opacity:.35">0</span>', "var(--sym-" + {"WW": "wild", "SC": "sc", "SS": "ss"}.get(c[0], "high" if str(c[0]).startswith("M") else "low") + ")") for i, v in enumerate(c[1:]))
                        rows.append(f'<tr><td><span class="sym {cls(str(c[0]))}">{esc(c[0])}</span></td>{cells}</tr>')
                    ctab = f'<div class="table-wrap"><table class="table compact"><caption>{esc(name)} 各輪符號顆數</caption><thead>' + th(["符號"] + [f"R{i+1}" for i in range(len(lens))], tuple(range(1, len(lens) + 1))) + "</thead><tbody>" + "".join(rows) + ("</tbody><tfoot><tr><td>Total</td>" + "".join(f'<td class="num">{num(v)}</td>' for v in tot[1:]) + "</tr></tfoot>" if tot else "</tbody>") + "</table></div>"
                grid = ""
                for i, r in enumerate(d["reels"]):
                    groups_html = "".join(f'<span class="grp"><em>{j+1}</em>' + "".join(f'<span class="sym {cls(s)}" title="R{i+1} #{j+k+1} {esc(s)}">{esc(s)}</span>' for k, s in enumerate(r[j:j + 10])) + "</span>" for j in range(0, len(r), 10))
                    grid += f'<div class="rowstrip"><h5>R{i+1} · {len(r)} 格（由上而下 = 由左而右，每 10 格標位置）</h5><div class="cells">{groups_html}</div></div>'
                out.append(f'<details{" open" if first else ""}><summary>{esc(key)} / {esc(name)} <span class="sub-note">長度 {" / ".join(map(str, lens))}</span></summary><div>{ctab}<h4>帶面</h4>{grid}</div></details>')
                first = False
        return "".join(out)

    def appendix(self):
        sheets = "".join(chip(esc(s["name"]) + ("（隱藏）" if s["hidden"] else ""), "ghost" if s["hidden"] else "") for s in self.D.get("sheets", []))
        src = [["機率表 xlsx", f'<code class="key wrap">{esc(self.D["source"]["name"])}</code>', f'sha256 {self.D["source"]["sha256_16"]}'],
               ["Content 軌", '<code class="key">prob-spec.md</code>', f'md sha256 {self.meta.get("md_sha256_16","")} · verdict {esc(self.meta.get("verdict"))}'],
               ["中繼資料", '<code class="key">prob-data.json</code>', f'ps_extract {esc(self.D.get("generated",""))}']]
        guide = "".join((f'<li style="margin-top:6px"><strong>{esc(" ".join(g))}</strong></li>' if g and g[0][:1].isdigit() else f'<li style="padding-left:1.6em;color:var(--text-2)">{esc(" ".join(g))}</li>') for g in self.D.get("guide", []))
        return "<h4>來源</h4>" + table(["層", "檔案", "說明"], src, cls="compact") + '<div class="two"><div><h4>xlsx 分頁</h4><div class="meta" style="margin-top:6px">' + sheets + "</div></div>" + (f'<div><h4>機率規格書製作方針（xlsx）</h4><ul style="list-style:none;font-size:13.5px;display:grid;gap:2px">{guide}</ul></div>' if guide else "") + "</div>"

    def render(self, css: str, body_only: bool, md_name: str, md_sha: str) -> str:
        items = [("overview", "總覽", "0"), ("brief", "規格簡述", "1"), ("data", "數據資料", "2"), ("flow", "機率流程圖", "3"), ("params", "參數表", "4"), ("kcards", "手法對應", "5"), ("hidden", "隱性規則", "6"), ("strips", "輪帶", "7"), ("appendix", "來源", "A")]
        main = "".join([
            sec("overview", "0", "總覽：規格與快測一眼看", self.overview(), "數據資料 · 參數表"),
            sec("brief", "1", "規格簡述", self.brief(), "prob-spec.md §1"),
            sec("data", "2", "數據資料（快測結果）", self.data(), "數據資料分頁"),
            sec("flow", "3", "機率流程圖", self.flow(), "prob-spec.md §3"),
            sec("params", "4", "參數表", self.params(), "參數表分頁"),
            sec("kcards", "5", "競品資料／手法對應", self.md_section("competitor", "（尚未填寫 human:competitor）"), "prob-spec.md §5"),
            sec("hidden", "6", "隱性規則與設計目的", self.hidden(), "prob-spec.md §6"),
            sec("strips", "7", "輪帶 Strip", self.strips(), "Strip 分頁"),
            sec("appendix", "A", "來源與版本", self.appendix()),
        ])
        foot = f'<footer><span>{esc(self.game)} 機率規格書 · View 軌 · ark-game-prob ps_html · 數字未經手抄</span><span>content-src: {md_name} sha256:{md_sha} ｜ 產出 {dt.date.today().isoformat()}</span></footer>'
        js = """<script>(function(){var links=[].slice.call(document.querySelectorAll('.toc a'));var secs=links.map(function(a){return document.getElementById(a.getAttribute('href').slice(1));});function setActive(id){links.forEach(function(a){a.classList.toggle('active',a.getAttribute('href')==='#'+id);});}if('IntersectionObserver' in window){var vis={};var io=new IntersectionObserver(function(es){es.forEach(function(e){vis[e.target.id]=e.isIntersecting?e.boundingClientRect.top:null;});var best=null;secs.forEach(function(s){if(vis[s.id]!=null&&(best==null||vis[s.id]<vis[best]))best=s.id;});if(best)setActive(best);},{rootMargin:'-10% 0px -70% 0px',threshold:[0,0.1]});secs.forEach(function(s){io.observe(s);});}setActive('overview');})();</script>"""
        mermaid = """<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script><script>if(window.mermaid){try{mermaid.initialize({startOnLoad:true,theme:(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'neutral')});}catch(e){}}</script>"""
        extra_css = ".flow-md pre.mermaid{background:transparent;border:0;overflow-x:auto}.flow-md .human{border:1px dashed var(--accent);padding:8px 14px;margin:8px 0;border-radius:var(--radius-sm)}.flow-md .human::before{content:'人工填寫區';font-family:var(--font-mono);font-size:11px;color:var(--accent);display:block}.human{border:1px dashed var(--border);padding:4px 14px;border-radius:var(--radius-sm)}.section table{margin:10px 0}.tag{display:inline-block;font-family:var(--font-mono);font-size:10px;padding:0 6px;border-radius:3px;margin-right:4px;font-weight:600;background:var(--accent-soft);color:var(--accent)}"
        head = f'<!-- content-src: {md_name} sha256:{md_sha} -->\n<title>{esc(self.game)} 機率規格書</title>\n<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&family=JetBrains+Mono:wght@400;500;600&display=swap">\n<style>\n{css}\n{extra_css}\n</style>\n'
        body = head + f'<div class="page">{self.header()}<div class="layout">{self.toc(items)}<main>{main}{foot}</main></div></div>{js}{mermaid}'
        if body_only:
            return body
        return '<!DOCTYPE html>\n<html lang="zh-TW"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">' + body.replace("</style>\n", "</style>\n</head><body>", 1) + "</body></html>"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="data/prob/<slug>（含 prob-data.json、prob-spec.md、prob-spec.meta.json）")
    ap.add_argument("--css", default=str(DEFAULT_CSS))
    ap.add_argument("--out", help="輸出檔（預設 <dir>/prob-spec.html）")
    ap.add_argument("--body-only", action="store_true", help="不含 doctype/html/head/body（給會自己包骨架的發佈端）")
    a = ap.parse_args()
    d = pathlib.Path(a.dir)
    dp, mp, metap = d / "prob-data.json", d / "prob-spec.md", d / "prob-spec.meta.json"
    for p in (dp, mp, metap):
        if not p.exists():
            C.fail("BAD_INPUT", f"缺 {p.name}", "先跑 ps_extract → ps_probspec")
    data = json.loads(dp.read_text(encoding="utf-8"))
    md = mp.read_text(encoding="utf-8")
    meta = json.loads(metap.read_text(encoding="utf-8"))
    css = pathlib.Path(a.css).read_text(encoding="utf-8") if pathlib.Path(a.css).exists() else ""
    sha = C.sha16(mp)
    html_text = View(data, md, meta).render(css, a.body_only, mp.name, sha)
    out = pathlib.Path(a.out) if a.out else d / "prob-spec.html"
    C.atomic_write(out, html_text)
    C.emit({"out": str(out), "bytes": len(html_text.encode("utf-8")), "stamp": sha, "sections": 9,
            "delivery": f"View 軌已落盤 {out}｜章節 9｜戳記 sha256:{sha}"}, {"stage": "ps_html"})


if __name__ == "__main__":
    main()
