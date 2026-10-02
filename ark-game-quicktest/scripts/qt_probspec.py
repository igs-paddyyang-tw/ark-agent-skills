#!/usr/bin/env python3
"""qt_probspec — 機率規格書 Content 軌：把 C 段既有產物組成 `data/prob/<slug>/prob-spec.md`（+ html）。

章節照機率規格書公版「製作方針」：1 規格簡述 → 2 數據資料 → 3 機率流程圖 → 4 參數表 → 5 競品資料／手法對應 → 6 隱性規則。
deterministic、不呼叫 LLM；每個數字都能回溯到來源檔（odds.json / rtp-report.json / qt-config / gdd-pack / decisions / state-machine）。
人工填寫區以 `<!-- human:<id> -->…<!-- /human -->` 標示，重產時原文保留。

用法: python qt_probspec.py --qt data/quicktest/<slug> [--gdd data/gdd/<pack>] [--run <run>] [--out data/prob] [--slug <slug>] [--version 1.0.0]
交付格式：prob-spec 已落盤 data/prob/<slug>/prob-spec.md｜6 段｜參數 N（待決議 M）｜數據：<verdict|未快測>｜html: …
"""
from __future__ import annotations

import argparse
import datetime as dt
import html as _html
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qt_common as C  # noqa: E402

PS_CONTRACT = "1"
HUMAN_RE = re.compile(r"<!--\s*human:([a-z0-9_-]+)\s*-->\n?(.*?)<!--\s*/human\s*-->", re.S)
SCALAR_PARAMS = [  # (key, 中文, 單位/說明)
    ("extra_rate", "額外押注倍率（Extra Bet）", ""),
    ("enter_free_game_gate", "進免費遊戲門檻（Scatter 顆數）", "顆"),
    ("free_game_num", "免費遊戲手數", "手"),
    ("free_game_retrigger_gate", "免費遊戲 retrigger 門檻", "顆"),
    ("free_game_retrigger_spin_num", "retrigger 加手數", "手"),
    ("max_win", "最大贏分倍數（MaxWin）", "倍"),
    ("is_item_card", "道具卡", "0/1"),
]
PENDING = "待決議"


def fmt_pct(v) -> str | None:
    return None if v is None else f"{v * 100:.2f}%"


def fmt_num(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.4g}" if abs(v) < 1 else f"{v:,.2f}".rstrip("0").rstrip(".")
    return str(v)


def pack_spec_rows(gdd: dict) -> list[tuple[str, str]]:
    out = []
    for kv in gdd.get("spec") or []:
        if kv.get("kv") is False:
            continue
        out.append((str(kv.get("k")), str(kv.get("v"))))
    return out


def rules_bullets(md: str) -> list[str]:
    out = []
    for ln in md.splitlines():
        s = ln.rstrip()
        if not s.strip() or s.startswith("<!--"):
            continue
        if s.startswith("### "):
            out.append(f"**{s[4:].strip()}**")
        elif s.startswith("- "):
            out.append(f"- **SPEC** {s[2:].strip()}")
        elif s.startswith("|"):
            out.append(s)
        elif s.startswith("> "):
            out.append(f"- **SPEC** {s[2:].strip()}")
        else:
            out.append(f"- **SPEC** {s.strip()}")
    # 區塊之間補空行（CommonMark：標題 / 清單 / 表格要分開）
    fixed: list[str] = []
    kind = lambda x: "h" if x.startswith("**") else "li" if x.startswith("- ") else "tb" if x.startswith("|") else "p"  # noqa: E731
    for ln in out:
        if fixed and kind(fixed[-1]) != kind(ln):
            fixed.append("")
        fixed.append(ln)
    return fixed


def mermaid_of(md: str) -> str | None:
    m = re.search(r"```mermaid\n(.*?)```", md, re.S)
    return m.group(1).rstrip() if m else None


def strip_counts(reel: list, sym_order: list[str]) -> dict[str, int]:
    c = {s: 0 for s in sym_order}
    for v in reel:
        c[str(v)] = c.get(str(v), 0) + 1
    return c


def md_to_html(md: str) -> str:
    """最小 markdown → html：#/##/###、bullet、表格、mermaid fence、段落；行內 **bold** / `code`。"""
    def inline(t: str) -> str:
        t = _html.escape(t, quote=False)
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        t = re.sub(r"\b(SPEC|DECIDED|UNKNOWN|FROM_KB|OBSERVED|INFERRED|PROPOSED)\b", r'<span class="tag \1">\1</span>', t, count=1) if t.startswith("<strong>") else t
        return t
    out, lines, i = [], md.splitlines(), 0
    in_ul = in_tbl = False
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            lang = ln[3:].strip(); buf = []; i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i]); i += 1
            code = _html.escape("\n".join(buf), quote=False)
            out.append(f'<pre class="mermaid">{code}</pre>' if lang == "mermaid" else f"<pre><code>{code}</code></pre>")
            i += 1; continue
        if ln.startswith("|"):
            if not in_tbl:
                out.append("<table>"); in_tbl = True; hdr = True
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                i += 1; continue
            tag = "th" if hdr else "td"
            out.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in cells) + "</tr>"); hdr = False
            i += 1; continue
        elif in_tbl:
            out.append("</table>"); in_tbl = False
        if ln.startswith("- "):
            if not in_ul:
                out.append("<ul>"); in_ul = True
            out.append(f"<li>{inline(ln[2:])}</li>"); i += 1; continue
        elif in_ul:
            out.append("</ul>"); in_ul = False
        if ln.startswith("<!--"):
            if "human:" in ln:
                out.append('<div class="human">')
            elif "/human" in ln:
                out.append("</div>")
            i += 1; continue
        if ln.startswith("# "):
            out.append(f"<h1>{inline(ln[2:])}</h1>")
        elif ln.startswith("## "):
            out.append(f'<h2 id="s{len([o for o in out if o.startswith("<h2")]) + 1}">{inline(ln[3:])}</h2>')
        elif ln.startswith("### "):
            out.append(f"<h3>{inline(ln[4:])}</h3>")
        elif ln.startswith("> "):
            out.append(f"<blockquote>{inline(ln[2:])}</blockquote>")
        elif ln.strip():
            out.append(f"<p>{inline(ln)}</p>")
        i += 1
    if in_ul:
        out.append("</ul>")
    if in_tbl:
        out.append("</table>")
    return "\n".join(out)


HTML_CSS = """
:root{--bg:#14110e;--panel:#1f1813;--line:#3d2f24;--fg:#efe6d6;--muted:#a89a8a;--accent:#e9b949;--spec:#5fb0e6;--dec:#7bd389;--unk:#e07a5f}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.65 "Noto Sans TC","Microsoft JhengHei",system-ui,sans-serif}
main{max-width:1080px;margin:0 auto;padding:32px 24px 80px}h1{font-size:28px;color:var(--accent);margin:0 0 4px}h2{font-size:21px;border-bottom:1px solid var(--line);padding-bottom:6px;margin-top:40px;color:var(--accent)}
h3{font-size:16px;color:var(--fg);margin:22px 0 6px}blockquote{margin:8px 0;padding:8px 14px;border-left:3px solid var(--accent);background:var(--panel);color:var(--muted)}
table{border-collapse:collapse;margin:10px 0;width:100%;font-size:13.5px}th,td{border:1px solid var(--line);padding:5px 9px;text-align:left;vertical-align:top}th{background:var(--panel);color:var(--accent)}
code{background:var(--panel);padding:1px 5px;border-radius:3px;font-size:13px}pre{background:var(--panel);padding:12px;overflow:auto;border:1px solid var(--line)}pre.mermaid{background:#fff;color:#111}
.tag{display:inline-block;font-size:11px;padding:0 6px;border-radius:3px;margin-right:4px;font-weight:600}.tag.SPEC{background:var(--spec);color:#06202e}.tag.DECIDED{background:var(--dec);color:#06260f}.tag.UNKNOWN,.tag.PROPOSED{background:var(--unk);color:#2b0e06}
.human{border:1px dashed var(--accent);padding:8px 14px;margin:8px 0;background:#201a12}.human::before{content:"人工填寫區";font-size:11px;color:var(--accent)}
.pending{color:var(--unk);font-weight:600}footer{margin-top:48px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:10px}
p.sub{color:var(--muted);font-size:13px;margin:0 0 14px}nav{font-size:13px;color:var(--muted);margin-bottom:24px}nav a{color:var(--accent);text-decoration:none;margin-right:12px}
"""


def build_html(md_body: str, title: str, md_name: str, md_sha16: str, meta: dict) -> str:
    body = md_to_html(md_body).replace(f">{PENDING}<", f'><span class="pending">{PENDING}</span><')
    toc = " ".join(f'<a href="#s{i}">{i}. {t}</a>' for i, t in enumerate(meta["sections"], 1))
    return f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><title>{_html.escape(title)}</title>
<!-- content-src: {md_name} sha256:{md_sha16} -->
<meta name="viewport" content="width=device-width,initial-scale=1"><style>{HTML_CSS}</style></head><body><main>
<h1>{_html.escape(title)}</h1>
<p class="sub">odds {_html.escape(str(meta["odds_version"]))} · 數據：{_html.escape(str(meta["verdict"]))} · 待決議參數 {meta["pending_params"]} · {meta["generated"]} · distribution: internal</p>
<nav>{toc}</nav>
{body}
<footer>distribution: internal · 由 ark-game-quicktest qt_probspec 自 Content 軌 {md_name} 渲染（sha256:{md_sha16}）· 數字皆可回溯來源，請勿只改 HTML</footer>
</main><script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script><script>if(window.mermaid){{try{{mermaid.initialize({{startOnLoad:true,theme:'neutral'}});}}catch(e){{}}}}</script></body></html>
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--qt", required=True, help="data/quicktest/<slug>")
    ap.add_argument("--gdd", help="gdd-pack（預設 qt-config.sources.gdd）")
    ap.add_argument("--run", help="影片 run 目錄（預設由 qt-config.sources.config_spec 推）")
    ap.add_argument("--out", default="data/prob")
    ap.add_argument("--slug")
    ap.add_argument("--version", help="odds 版本（預設取 qt-config.version）")
    ap.add_argument("--author", default=os.getenv("ARK_AUTHOR", "paddyyang"))
    ap.add_argument("--date", default=dt.date.today().isoformat())
    a = ap.parse_args()

    qt = pathlib.Path(a.qt).resolve()
    cfg_p = qt / "qt-config.yaml"
    if not cfg_p.exists():
        C.fail("BAD_INPUT", f"{qt} 缺 qt-config.yaml", "先跑 qt_config.py")
    cfg = C.yaml_load(cfg_p)
    ver = a.version or str(cfg.get("version") or "1.0.0")
    odds_p = qt / "odds" / f"odds_{ver}.json"
    if not odds_p.exists():
        C.fail("BAD_INPUT", f"缺 {odds_p}")
    odds = json.loads(odds_p.read_text(encoding="utf-8"))
    eo = odds.get("extra_odds") or {}
    prov = cfg.get("provenance") or {}
    srcs = cfg.get("sources") or {}
    slug = a.slug or qt.name
    if not re.match(r"^[a-z][a-z0-9-]{1,48}$", slug):
        C.fail("BAD_INPUT", f"slug 需 kebab-case：{slug}")
    cwd = pathlib.Path.cwd()

    def resolve(p) -> pathlib.Path | None:
        if not p:
            return None
        q = pathlib.Path(str(p))
        q = q if q.is_absolute() else (cwd / q)
        return q.resolve() if q.exists() else None

    gdd_dir = resolve(a.gdd or srcs.get("gdd"))
    run_dir = resolve(a.run)
    if run_dir is None and srcs.get("config_spec"):
        cs = resolve(srcs["config_spec"])
        if cs is not None and cs.parent.name == "dev-spec":
            run_dir = cs.parent.parent
    dec_p = resolve(srcs.get("decisions")) or ((run_dir / "decisions.yaml") if run_dir and (run_dir / "decisions.yaml").exists() else None)
    tgt_p = qt / "quicktest.yaml"
    targets = C.yaml_load(tgt_p) if tgt_p.exists() else {}
    rep_p = qt / "qt-report" / "rtp-report.json"
    rep = json.loads(rep_p.read_text(encoding="utf-8")) if rep_p.exists() else None
    sm_p = (run_dir / "dev-spec" / "state-machine.md") if run_dir else None
    sm = sm_p.read_text(encoding="utf-8") if sm_p and sm_p.exists() else None
    kb_p = (run_dir / "kb-refs.yaml") if run_dir else None
    kb = C.yaml_load(kb_p) if kb_p and kb_p.exists() else None
    ga_p = (run_dir / "game-analysis.yaml") if run_dir else None
    ga = C.yaml_load(ga_p) if ga_p and ga_p.exists() else None
    gdd = C.yaml_load(gdd_dir / "gdd.yaml") if gdd_dir and (gdd_dir / "gdd.yaml").exists() else None
    dec = C.yaml_load(dec_p) if dec_p else None

    out_dir = pathlib.Path(a.out) / slug
    md_p = out_dir / "prob-spec.md"
    # 人工區保留
    human: dict[str, str] = {}
    if md_p.exists():
        for m in HUMAN_RE.finditer(md_p.read_text(encoding="utf-8")):
            human[m.group(1)] = m.group(2).rstrip("\n")

    def hblock(hid: str, default: str) -> list[str]:
        return [f"<!-- human:{hid} -->", human.get(hid, default), "<!-- /human -->"]

    game = str(targets.get("game") or cfg.get("game") or (gdd or {}).get("short_title") or slug)
    st = cfg.get("structure") or {}
    reels, rows = st.get("reels"), st.get("rows")
    symbols = st.get("symbols") or []
    sym_by_id = {str(s.get("sym_id")): s for s in symbols}
    sources_used: dict[str, pathlib.Path] = {"qt-config": cfg_p, "odds": odds_p}
    if tgt_p.exists():
        sources_used["quicktest"] = tgt_p
    if rep:
        sources_used["rtp-report"] = rep_p
    if gdd_dir:
        sources_used["gdd"] = gdd_dir / "gdd.yaml"
        for rp in sorted((gdd_dir / "rules").glob("*.md")) if (gdd_dir / "rules").exists() else []:
            sources_used[f"rules/{rp.name}"] = rp
    if sm:
        sources_used["state-machine"] = sm_p
    if kb:
        sources_used["kb-refs"] = kb_p
    if ga:
        sources_used["game-analysis"] = ga_p
    if dec:
        sources_used["decisions"] = dec_p

    pending = 0
    derived: list[dict] = []  # 派生數字（給 ps_lint 的允許集）

    def dv(val: str, frm: str) -> str:
        derived.append({"value": val, "from": frm})
        return val

    L: list[str] = []
    sections = ["規格簡述", "數據資料", "機率流程圖", "參數表", "競品資料／手法對應", "隱性規則"]
    # ── 1 規格簡述 ──
    L += ["## 1. 規格簡述", ""]
    if gdd:
        L += ["### 基本規格", "", "| 項目 | 內容 | 來源 |", "|---|---|---|"]
        for k, v in pack_spec_rows(gdd):
            L.append(f"| {k} | {v.replace(chr(10), ' ')} | **SPEC** gdd.yaml.spec |")
        L.append("")
        for f in gdd.get("features") or []:
            rp = gdd_dir / (f.get("rules") or "")
            L += [f"### {f.get('title') or f.get('id')}", ""]
            if f.get("rules") and rp.exists():
                L += rules_bullets(rp.read_text(encoding="utf-8")) + [""]
            else:
                L += ["- **UNKNOWN** 本玩法尚無 rules 檔。", ""]
    else:
        L += ["- **UNKNOWN** 無 gdd-pack（qt-config.sources.gdd 未指定）；規格簡述待補。", ""]
    L += ["### 機率人員簡述（競品分析模式）", ""] + hblock("summary", "（待機率人員填寫：特色觸發與進行方式、與競品差異、設計意圖）") + [""]

    # ── 2 數據資料 ──
    L += ["## 2. 數據資料", ""]
    verdict = "未快測"
    if rep:
        spins = int(rep.get("spins") or 0)
        verdict = (rep.get("gate") or {}).get("verdict") or "inconclusive"
        L += [f"> 來源：`qt-report/rtp-report.json`（快測版本 {rep.get('version')}，{dv(f'{spins:,}', 'rtp-report.spins')} 手，{rep.get('generated_at')}）；P-003 三向 verdict：**{verdict}**。", "",
              "| 階段 | RTP | Hit % | 觸發率 | 平均觸發局數 | 平均倍率 | 最大倍率 | 平均局數 |", "|---|---|---|---|---|---|---|---|"]
        for name, r in (rep.get("games") or {}).items():
            freq = r.get("freq")
            trig = dv(fmt_pct(1.0 / freq), f"games.{name}.freq") if freq else "—"
            rtp = dv(fmt_pct(r.get("rtp")), f"games.{name}.rtp") if r.get("rtp") is not None else "—"
            hit = dv(fmt_pct(r.get("hitrate")), f"games.{name}.hitrate") if r.get("hitrate") is not None else "—"
            L.append(f"| {name} | {rtp} | {hit} | {trig} | " + " | ".join(dv(fmt_num(r.get(k)), f"games.{name}.{k}") for k in ("freq", "multi", "maxmulti", "playtimes")) + " |")
        g = rep.get("gate") or {}
        L += [""] + [f"- {c['id']}：{c['msg']} [{c['status']}]" for c in g.get("checks", [])]
        for c in rep.get("template_caveats") or []:
            L.append(f"- ⚠ 範本審查 {c['finding']}（{c['row']}）：{c['msg']}")
        d = rep.get("detail") or {}
        if d:
            L.append(f"- SD {dv(fmt_num(d.get('sd')), 'detail.sd')}；P.I. {dv(fmt_num(d.get('pi')), 'detail.pi')}；Pay Out Rate {dv(fmt_pct(d.get('pay_out_rate')), 'detail.pay_out_rate') if d.get('pay_out_rate') is not None else '—'}")
        L.append("")
    else:
        L += ["> **未快測**：`qt-report/rtp-report.json` 不存在。跑 `qt_run.py` 後重產本檔，本表自動填入。", "",
              "| 階段 | RTP | Hit % | 觸發率 | 平均觸發局數 | 平均倍率 | 最大倍率 | 平均局數 |", "|---|---|---|---|---|---|---|---|",
              "| Main Game | — | — | — | — | — | — | — |", "| Feature Game | — | — | — | — | — | — | — |", "| Jackpot | — | — | — | — | — | — | — |", "| Total | — | — | — | — | — | — | — |", ""]
    if targets.get("target_rtp") is not None:
        L.append(f"- 目標 RTP：{dv(fmt_pct(targets['target_rtp']), 'quicktest.target_rtp')}（容許 ±{dv(fmt_pct(targets.get('rtp_tolerance', 0.005)), 'quicktest.rtp_tolerance')}）；來源 quicktest.yaml。**RTP 是模擬結果不是輸入**（P-000）。")
    else:
        L.append(f"- 目標 RTP：{PENDING}（quicktest.yaml 無 target_rtp）。**RTP 是模擬結果不是輸入**（P-000）。")
        pending += 1
    L.append("")

    # ── 3 機率流程圖 ──
    L += ["## 3. 機率流程圖", ""]
    if sm and mermaid_of(sm):
        L += [f"> 來源：`dev-spec/state-machine.md`（run {run_dir.name}）；可編輯流程圖（drawio）為 View 軌，之後由本圖產生。", "", "```mermaid", mermaid_of(sm), "```", ""]
    else:
        L += ["- **UNKNOWN** 無 dev-spec/state-machine.md；流程圖待補（`gs_run --stage dev` 產）。", ""]
    L += hblock("flow-notes", "（流程補充：各狀態的機率抽選點、與公版流程圖的對應）") + [""]

    # ── 4 參數表 ──
    L += ["## 4. 參數表", "", "> 值來自 `odds/odds_" + ver + ".json`；來源欄為 qt-config.yaml.provenance（D-id = 決議、gdd.symbols = 規格書、template = 範本示範值、competitor_reference = 競品觀察）。" + f"**{PENDING}** = null，依 P-002 未決議不得帶值。", ""]
    L += ["### 基本資訊", "", "| 項目 | 值 | 來源 |", "|---|---|---|"]

    def prow(label: str, val, key: str, unit: str = "") -> str:
        nonlocal pending
        src = prov.get(key)
        if val is None:
            pending += 1
            return f"| {label} | {PENDING} | {src or '—'} |"
        return f"| {label} | {val}{unit} | {src or '**UNKNOWN** 無 provenance'} |"

    L.append(prow("盤面（軸 × 列）", f"{reels} × {rows}" if reels and rows else None, "structure.reels"))
    if gdd:
        for k, v in pack_spec_rows(gdd):
            if any(t in k for t in ("對獎", "線", "收費", "成本")):
                L.append(f"| {k} | {v} | **SPEC** gdd.yaml.spec |")
    L += [""]
    L += ["### Odds 表（k-of-a-kind 單線賠付）", ""]
    ncol = int(reels or 5)
    L += ["| 符號 | sym_id | 名稱 | 組 | " + " | ".join(f"x{k}" for k in range(1, ncol + 1)) + " | 來源 |", "|---|---|---|---|" + "---|" * ncol + "---|"]
    for s in symbols:
        sid = str(s.get("sym_id"))
        arr = (eo.get("odds") or {}).get(sid)
        src = prov.get(f"extra_odds.odds.{sid}") or prov.get("extra_odds.odds")
        if arr is None:
            pending += 1
            cells = [PENDING] * ncol
        else:
            cells = [str(x) for x in list(arr)[:ncol]] + ["—"] * max(0, ncol - len(arr))
        L.append(f"| {s.get('code')} | {sid} | {s.get('name') or ''} | {s.get('group') or ''} | " + " | ".join(cells) + f" | {src or ('—' if arr is None else '**UNKNOWN**')} |")
    L += ["", "### 觸發與上限參數", "", "| 參數 | 值 | 來源 |", "|---|---|---|"]
    for key, label, unit in SCALAR_PARAMS:
        L.append(prow(label, eo.get(key), f"extra_odds.{key}", (" " + unit) if unit and eo.get(key) is not None else ""))
    jm, ja = eo.get("jackpot_multiple"), eo.get("jackpot_acc_rate")
    L.append(prow("Jackpot 基底倍數（MINI→GRAND）", ", ".join(map(str, jm)) if isinstance(jm, list) else None, "extra_odds.jackpot_multiple"))
    L.append(prow("Jackpot 累積率", ", ".join(map(str, ja)) if isinstance(ja, list) else None, "extra_odds.jackpot_acc_rate"))
    L += ["", "### 輪帶組與權重（K-022 輪帶組權重混合）", ""]

    def idx_table(title: str, iset, wt, key: str) -> None:
        nonlocal pending, L
        L.append(f"**{title}**")
        L.append("")
        if not isinstance(iset, list) or not iset:
            L += [f"- {PENDING}（{key} 為 null）", ""]
            pending += 1
            return
        n = max(len(x) for x in iset if isinstance(x, list)) if any(isinstance(x, list) for x in iset) else 0
        L += ["| 組合 | " + " | ".join(f"R{i + 1} 用組" for i in range(n)) + " | 權重 | 來源 |", "|---|" + "---|" * n + "---|---|"]
        for i, combo in enumerate(iset):
            w = wt[i] if isinstance(wt, list) and i < len(wt) else None
            if isinstance(wt, list) and wt and isinstance(wt[0], list):  # free: weight[type][combo]
                w = "/".join(str(wt[t][i]) if i < len(wt[t]) else "—" for t in range(len(wt)))
            L.append(f"| {i} | " + " | ".join(str(c) for c in combo) + " | " + (str(w) if w is not None else PENDING) + f" | {prov.get(key + '_weight') or prov.get(key.replace('index_set', 'set_weight')) or '—'} |")
        L.append("")

    idx_table("主遊戲", eo.get("main_game_reel_index_set"), eo.get("main_game_reel_set_weight"), "extra_odds.main_game_reel_index_set")
    idx_table("免費遊戲（權重欄 = 超強/強/中/弱 四型）", eo.get("free_game_reel_index_set"), eo.get("free_game_reel_set_weight"), "extra_odds.free_game_reel_index_set")
    ftw = eo.get("free_game_type_weight")
    L.append(f"- 免費遊戲四型權重（超強/強/中/弱）：{', '.join(map(str, ftw)) if isinstance(ftw, list) else PENDING}；來源 {prov.get('extra_odds.free_game_type_weight') or '—'}")
    if not isinstance(ftw, list):
        pending += 1
    L.append("")
    L += ["### 輪帶符號顆數（Strip 統計；完整輪帶見 odds.json）", ""]
    sym_order = [str(s.get("sym_id")) for s in symbols]
    for label, key in (("主遊戲", "main_game_reel_data"), ("免費遊戲", "free_game_reel_data")):
        data = odds.get(key)
        if not isinstance(data, list) or not data:
            L += [f"- {label}：{PENDING}（{key} 為 null）", ""]
            pending += 1
            continue
        L += [f"**{label}**", "", "| 組 | 軸 | 長度 | " + " | ".join(sym_by_id.get(s, {}).get("code") or s for s in sym_order) + " |", "|---|---|---|" + "---|" * len(sym_order)]
        for gi, grp in enumerate(data):
            for ri, reel in enumerate(grp or []):
                cnt = strip_counts(reel or [], sym_order)
                L.append(f"| {gi} | R{ri + 1} | {dv(str(len(reel or [])), f'len({key}[{gi}][{ri}])')} | " + " | ".join(dv(str(cnt.get(s, 0)), f'count({key}[{gi}][{ri}],{s})') for s in sym_order) + " |")
        L.append("")
    L += hblock("param-notes", "（參數備註：隱性數值的設計目的、與編導規格書同步事項）") + [""]

    # ── 5 競品資料／手法對應 ──
    L += ["## 5. 競品資料／手法對應", ""]
    if kb and ga:
        names = {it.get("id"): it.get("name") for it in ga.get("items") or []}
        L += [f"> 來源：`kb-refs.yaml`（run {run_dir.name}）；每個機制對回知識庫頁或標「新設計」。", "", "| 機制 | 知識庫命中 | 狀態 |", "|---|---|---|"]
        for it in kb.get("items") or []:
            refs = it.get("refs") or []
            hit = "；".join(f"`{r['id']}` {r.get('title') or ''}" for r in refs) if refs else "—"
            L.append(f"| {it.get('item_id')} {names.get(it.get('item_id')) or ''} | {hit} | {'**FROM_KB**' if refs else '**PROPOSED** 新設計／未援引'} |")
        L.append("")
    else:
        L += ["- **UNKNOWN** 無 run 的 kb-refs.yaml / game-analysis.yaml；手法對應待補。", ""]
    L += hblock("competitor", "（選用：競品收錄目的、參考機台與差異）") + [""]

    # ── 6 隱性規則 ──
    L += ["## 6. 隱性規則", "", "> 更改需與編導規格書同步；每條須有設計目的（公版製作方針 §4）。", "",
          "| 編號 | 情況（topic） | 說明（值） | 設計目的 | 來源 |", "|---|---|---|---|---|"]
    n_dec = n_defer = 0
    for d in (dec or {}).get("decisions") or []:
        if d.get("decision") == "defer" or d.get("value") is None:
            n_defer += 1
            continue
        n_dec += 1
        L.append(f"| {d.get('decision_id')} | {d.get('topic')} | {json.dumps(d.get('value'), ensure_ascii=False)} | {d.get('reason') or '—'} | **DECIDED** {d.get('decided_by') or ''} |")
    if n_dec == 0:
        L.append(f"| — | — | — | — | 尚無已定案決議（defer {dv(str(n_defer), 'decisions.defer_count')} 筆） |")
    elif n_defer:
        L.append(f"| — | 另有 {dv(str(n_defer), 'decisions.defer_count')} 筆 defer | — | — | 待決議 |")
    L += [""] + hblock("hidden-rules", "（人工補充：上限保護、特殊盤面限制等隱性規則與其設計目的）") + [""]

    # ── 邊界 ──
    L += ["## 邊界聲明", "",
          f"- 本檔由 qt_probspec 自來源檔 deterministic 組出（重產覆蓋，人工區保留）；來源 sha 記於 `prob-spec.meta.json`，ps_lint 擋 STALE。",
          "- 不產 xlsx 公版、不畫 drawio；兩者為 View 軌，由本檔與 odds.json 另產。",
          "- RTP / 觸發率只引用快測結果，不在本檔定案；參數 null 依 P-002 顯示 待決議。", ""]

    body = "\n".join(L)
    fm = ["---", f'title: "機率規格書：{game}"', "contract: \"1\"", "kind: prob-spec", f"slug: {slug}", f'game: "{game}"', f'odds_version: "{ver}"',
          f"status: {'review' if rep else 'draft'}", "distribution: internal", f"date: {a.date}", f"author: {a.author}", "source_skill: ark-game-quicktest",
          f"verdict: {verdict}", f"pending_params: {pending}", "sources:"]
    def rel(p: pathlib.Path) -> str:
        try:
            return p.relative_to(cwd).as_posix()
        except ValueError:
            return p.as_posix()

    fm += [f"  {k}: {rel(v)}" for k, v in sources_used.items()]
    fm += ["---", "", f"# 機率規格書：{game}", "",
           f"> 依機率規格書公版「製作方針」六段組成；**SPEC** = 規格書、**DECIDED** = 決議、**FROM_KB** = 知識庫、{PENDING} = 未決議（null）。人工填寫區可直接編輯，重產保留。", ""]
    md = "\n".join(fm) + body
    C.atomic_write(md_p, md)
    sha = C.sha16(md_p)
    meta = {"contract": PS_CONTRACT, "slug": slug, "game": game, "odds_version": ver, "sections": sections, "pending_params": pending, "verdict": verdict,
            "sources": {k: {"path": rel(v), "sha256_16": C.sha16(v)} for k, v in sources_used.items()},
            "derived": derived, "md_sha256_16": sha, "generated": a.date}
    C.atomic_write(out_dir / "prob-spec.meta.json", json.dumps(meta, ensure_ascii=False, indent=1))
    html_p = out_dir / "prob-spec.html"
    C.atomic_write(html_p, build_html(body, f"機率規格書：{game}", "prob-spec.md", sha, meta))
    C.emit({"md": md_p.as_posix(), "html": html_p.as_posix(), "meta": (out_dir / "prob-spec.meta.json").as_posix(), "sections": len(sections), "pending_params": pending,
            "verdict": verdict, "sources": list(sources_used), "human_blocks_kept": len(human),
            "delivery": f"prob-spec 已落盤 {md_p.as_posix()}｜{len(sections)} 段｜待決議參數 {pending}｜數據：{verdict}｜html: {html_p.name}",
            "next": f"python ps_lint.py --dir {out_dir.as_posix()}"}, {"stage": "probspec"})


if __name__ == "__main__":
    main()
