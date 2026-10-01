#!/usr/bin/env python3
"""qt_report — 快測範本 report_<ver>.txt → rtp-report.json → ark-md-report（type: data）+ P-003 三向守門。

輸入：快測範本（data/dev-sample/機率工作流/快測範本）跑出的 report_<ver>.txt（+ 同目錄 AwardRangeData_<ver>.csv 選配）。
守門（P-003）：① |RTP−target| ≤ tolerance（預設 0.005）② 各特殊遊戲觸發率落在體感區間（P-005）③ config-spec 無效值阻斷。
目標與區間來自 quicktest.yaml（沒有目標 → 該向 skip，verdict 最多 inconclusive；回報數值不下結論）。

用法:
    python qt_report.py --report <report_1.0.0.txt> [--targets quicktest.yaml] [--config-spec config-spec.yaml]
                        [--out <dir>] [--publish docs/reports] [--wiki-schema knowledge/shared/schema.md]
exit: 0 / 2 BAD_INPUT / 6 lint FAIL（引擎 bug）
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qt_common as C  # noqa: E402

FEEL_BANDS = {  # P-005 體感分級 → 觸發率區間（rate = 1/Freq）
    "驚喜型": (1 / 50, 1 / 25), "期待型": (1 / 20, 1 / 8), "節奏型": (1 / 8, 1 / 3), "核心體驗型": (1 / 3, 1.0),
    "稀有大事件": (1 / 300, 1 / 150), "標準節奏": (1 / 150, 1 / 80), "高頻小獎": (1 / 80, 1 / 40),
}


# ── 解析 ──────────────────────────────────────────────────────────────────

def parse_report(text: str) -> dict:
    lines = text.splitlines()
    out: dict = {"contract": C.CONTRACT, "version": None, "generated_at": None, "spins": None, "total_win": None, "total_bet": None,
                 "games": {}, "detail": {}, "symbol_hit_rate": {}, "symbol_hit_rtp": {}, "reel_set_rtp": {}, "asset_100": [],
                 "multiple": [], "special_range": [], "decile": {}, "raw_sections": []}
    m = re.search(r"版本:\s*(\S+)\s*=+\s*([\d\-]+ [\d:.]+)", text)
    if m:
        out["version"], out["generated_at"] = m.group(1), m.group(2)
    m = re.search(r"Times:(\d+)\s+TotalWin:(-?\d+)\s+TotalBet:(\d+)", text)
    if m:
        out["spins"], out["total_win"], out["total_bet"] = int(m.group(1)), int(m.group(2)), int(m.group(3))
    sec, hdr = None, []
    for ln in lines:
        s = ln.strip()
        if s.startswith("*****"):
            sec = s.strip("* ").strip()
            out["raw_sections"].append(sec)
            hdr = []
            continue
        if not s or sec is None:
            continue
        if sec == "BASE INFO":
            if s.startswith("Game"):
                hdr = s.split()
                continue
            parts = re.split(r"\s+-\s+", s, maxsplit=1)
            if len(parts) == 2:
                name, vals = parts[0].strip(), parts[1].split()
                keys = [h.rstrip(".").lower() for h in hdr if h != "-"][1:]
                rec = {}
                if name == "Total" and len(vals) == 2:      # Total 列只有 RTP 與 MaxMulti
                    rec = {"rtp": C.num(vals[0]), "maxmulti": C.num(vals[1])}
                else:
                    for k, v in zip(keys, vals):
                        rec[k] = C.num(v)
                out["games"][name] = rec
        elif sec == "Game Detail Information":
            d = out["detail"]
            if s.startswith("SD:"):
                d["sd"] = C.num(s.split(":", 1)[1])
            elif "confidence level" in s:
                m = re.match(r"(\d+)% confidence level:\s*([\d.]+%)\s*~\s*([\d.]+%)", s)
                if m:
                    d.setdefault("confidence", {})[m.group(1)] = [C.num(m.group(2)), C.num(m.group(3))]
            elif s.startswith("P.I.:"):
                d["pi"] = C.num(s.split(":", 1)[1])
            elif s.startswith("Pay Out Rate:"):
                d["pay_out_rate"] = C.num(s.split(":", 1)[1])
            elif "可洗分一次" in s:
                m = re.search(r"([\d.]+)", s)
                d["avg_cashout_players"] = float(m.group(1)) if m else None
            elif s.startswith("高均率:"):
                d["high_avg_rate"] = C.num(s.split(":", 1)[1])
            elif s.startswith("中均值:"):
                d["mid_avg"] = C.num(s.split(":", 1)[1])
            elif s.startswith("maxwin"):
                d["maxwin_note"] = s
        elif sec in ("Main Symbol Hit Rate", "Main Symbol Hit RTP"):
            key = "symbol_hit_rate" if sec.endswith("Rate") else "symbol_hit_rtp"
            parts = s.split()
            if parts[0] == "SYMBOL":
                hdr = parts[1:]
                continue
            if len(parts) == len(hdr) + 1:
                out[key][parts[0]] = {h.lower(): C.num(v) for h, v in zip(hdr, parts[1:])}
        elif sec == "Reel Set RTP":
            m = re.match(r"SET\s+(\d+):\s*(\S+)", s)
            if m:
                out["reel_set_rtp"][int(m.group(1))] = C.num(m.group(2))
        elif sec.startswith("100手"):
            m = re.match(r"(.+?)\s+([\d.]+%)$", s)
            if m:
                out["asset_100"].append({"range": re.sub(r"\s+", " ", m.group(1)), "pct": C.num(m.group(2))})
        elif sec == "Multiple Information":
            m = re.match(r"(.+?)\s+-\s+約\s+(\S+)局觸發\(\s*(\S+?)倍以上\s+-\s+約\s+(\S+)局觸發", s)
            if m:
                out["multiple"].append({"range": re.sub(r"\s+", " ", m.group(1)), "spins_per_hit": C.num(m.group(2)),
                                        "ge": re.sub(r"\s+", "", m.group(3)), "spins_per_hit_ge": C.num(m.group(4))})
        elif sec == "SpecialGame Range":
            if "Range" in s or "AppearRate" in s:
                continue
            m = re.match(r"(.+?)\s+-\s+(.+)$", s)
            if m:
                vals = [v for v in re.split(r"[\s|]+", m.group(2).strip()) if v]
                if len(vals) == 7:
                    out["special_range"].append({"range": re.sub(r"\s+", " ", m.group(1)),
                                                 "appear": {"total": C.num(vals[0]), "main": C.num(vals[1]), "free": C.num(vals[2])},
                                                 "rtp": {"total": C.num(vals[3]), "main": C.num(vals[4]), "free": C.num(vals[5])},
                                                 "fg_avg_spin": C.num(vals[6])})
        elif sec == "Decile Table":
            parts = re.split(r"\s+-\s+", s, maxsplit=1)
            if len(parts) == 2 and parts[0].strip() != "":
                name = parts[0].strip()
                if name == "" or name.startswith("-"):
                    continue
                vals = parts[1].split()
                cols = ["total", "main", "free", "fspin"]
                out["decile"][name.replace(" ", "")] = {c: C.num(v) for c, v in zip(cols, vals)}
    tot = out["games"].get("Total", {})
    out["rtp_total"] = tot.get("rtp")
    out["rtp_main"] = out["games"].get("MainGame", {}).get("rtp")
    out["rtp_special"] = out["games"].get("SpecialGameTotal", {}).get("rtp")
    fq = out["games"].get("SpecialGameTotal", {}).get("freq")
    out["special_trigger_rate"] = (1 / fq) if fq else None
    return out


def load_award_csv(p: pathlib.Path) -> list[dict]:
    rows = []
    for ln in p.read_text(encoding="utf-8").splitlines()[1:]:
        parts = ln.split(",")
        if len(parts) == 3:
            rows.append({"range": parts[0], "spins_per_hit": C.num(parts[1]), "rtp": C.num(parts[2])})
    return rows


# ── 守門（P-003 三向）───────────────────────────────────────────────────────

def gate(rep: dict, targets: dict, config_spec: dict | None) -> dict:
    checks = []
    tol = float(targets.get("rtp_tolerance", 0.005))
    tgt = targets.get("target_rtp")
    if tgt is None or rep.get("rtp_total") is None:
        checks.append({"id": "rtp", "status": "SKIP", "msg": "無 target_rtp（quicktest.yaml）或報告無 Total RTP"})
    else:
        diff = rep["rtp_total"] - float(tgt)
        checks.append({"id": "rtp", "status": "PASS" if abs(diff) <= tol else "FAIL", "sim": rep["rtp_total"], "target": float(tgt), "diff": diff, "tol": tol,
                       "msg": f"模擬 {rep['rtp_total']:.4%} vs 目標 {float(tgt):.2%}（差 {diff:+.4%}，容許 ±{tol:.1%}）"})
    feels = targets.get("feel") or []
    if not feels:
        checks.append({"id": "feel", "status": "SKIP", "msg": "無體感目標（quicktest.yaml.feel）"})
    for f in feels:
        game = f.get("game", "SpecialGameTotal")
        fq = rep["games"].get(game, {}).get("freq")
        rate = (1 / fq) if fq else None
        band = f.get("band") or FEEL_BANDS.get(f.get("preset", ""))
        if rate is None or not band:
            checks.append({"id": f"feel:{game}", "status": "SKIP", "msg": f"{game} 無 Freq 或無區間（preset/band）"})
            continue
        lo, hi = float(band[0]), float(band[1])
        ok = lo <= rate <= hi
        checks.append({"id": f"feel:{game}", "status": "PASS" if ok else "FAIL", "rate": rate, "freq": fq, "band": [lo, hi], "preset": f.get("preset"),
                       "msg": f"{game} 觸發 1/{fq:.1f}（{rate:.2%}）{'落在' if ok else '不在'}{f.get('preset') or '自訂'}區間 1/{1/hi:.0f}~1/{1/lo:.0f}"})
    if config_spec is None:
        checks.append({"id": "null", "status": "SKIP", "msg": "未提供 config-spec.yaml"})
    else:
        decided = set()
        for p in config_spec.get("parameters", []) or []:
            if p.get("value") is not None and not p.get("decision"):
                decided.add(p.get("name"))
        checks.append({"id": "null", "status": "FAIL" if decided else "PASS",
                       "msg": ("未經決議卻有值的參數：" + ", ".join(sorted(decided))) if decided else "parameters.value 全為 null 或附 decision", "params": sorted(decided)})
    st = [c["status"] for c in checks]
    if "FAIL" in st:
        verdict = "rejected"
    elif "PASS" in st and "SKIP" not in st:
        verdict = "confirmed"
    else:
        verdict = "inconclusive"
    return {"checks": checks, "verdict": verdict}


# ── Markdown（ark-md-report type: data）────────────────────────────────────

def _pct(v) -> str:
    return "—" if v is None else f"{v:.2%}"


def render_md(rep: dict, g: dict, targets: dict, src: pathlib.Path, date: str, md_name: str, award: list[dict]) -> str:
    spins = rep.get("spins") or 0
    conf = "high" if spins >= 10_000_000 else "medium" if spins >= 1_000_000 else "low"
    findings = []
    for c in g["checks"]:
        if c["status"] == "FAIL":
            sev = "P1" if c["id"].startswith("feel") else "P0"
            findings.append({"sev": sev, "what": c["msg"], "where": c["id"], "impact": {"rtp": "RTP 偏離目標，不得進 Dev-spec", "null": "競品值偷渡成定案，P-002 違規"}.get(c["id"], "體感節奏偏離企劃目標"),
                             "ev": c, "action": {"rtp": "調整輪帶 / 權重後重跑；差距大先查 Reel Set RTP 哪組偏", "null": "走 ark-grill-me 補 Decision Record 或把 value 改回 null"}.get(c["id"], "調整觸發帶的 Scatter 權重，對照 P-005 區間重跑")})
    for c in g["checks"]:
        if c["status"] == "SKIP":
            findings.append({"sev": "P3", "what": c["msg"], "where": c["id"], "impact": "該向未驗，verdict 最多 inconclusive", "ev": c,
                             "action": "在 quicktest.yaml 補 target_rtp / feel，或提供 config-spec.yaml"})
    if spins and spins < 10_000_000:
        findings.append({"sev": "P2", "what": f"樣本 {spins:,} 轉 < 1,000 萬", "where": "report header", "impact": "低頻事件（JP / 高倍）信賴區間不足", "ev": {"msg": f"Times:{spins}"}, "action": "TotalRound 調到 ≥ 1e7 重跑"})
    order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    findings.sort(key=lambda x: (order[x["sev"]], x["where"]))
    sev = {"p0": 0, "p1": 0, "p2": 0, "p3": 0}
    for f in findings:
        sev[f["sev"].lower()] += 1
    L = ["---", f'title: "快測 RTP 驗證：{targets.get("game") or rep.get("version") or src.stem}"', "type: data",
         f'subject: "quicktest/{targets.get("slug") or src.parent.name}"', f"date: {date}", "author: ark-game-quicktest", "source_skill: ark-game-quicktest",
         f"verdict: {g['verdict']}", f"confidence: {conf}", f"findings: {{ p0: {sev['p0']}, p1: {sev['p1']}, p2: {sev['p2']}, p3: {sev['p3']} }}",
         f"score: {round((rep.get('rtp_total') or 0) * 100, 4)}", 'score_version: "qt-rtp-1"', "tags: [rtp, case]", "loop_stage: post-quicktest",
         "sources:", f"  - {src.as_posix()}"]
    if award:
        L.append(f"  - {src.with_name('AwardRangeData_' + str(rep.get('version')) + '.csv').as_posix()}")
    L += ["quicktest:", f"  version: \"{rep.get('version')}\"", f"  spins: {spins}", f"  generated_at: \"{rep.get('generated_at')}\"", "---", "",
          f"# 快測 RTP 驗證：{targets.get('game') or rep.get('version')}", "",
          f"> 由 qt_report 從 `{src.name}` deterministic 解析；數值原樣引用，**本報告只回報不下結論**（結論由 prob-architect / math-reviewer 判）。", "",
          "## Verdict", "",
          f"{g['verdict']} — P-003 三向：" + "；".join(f"{c['id']} {c['status']}" for c in g["checks"]) + f"。樣本 {spins:,} 轉，Total RTP {_pct(rep.get('rtp_total'))}"
          + (f"（95% CI {_pct(rep['detail']['confidence']['95'][0])} ~ {_pct(rep['detail']['confidence']['95'][1])}）" if rep.get("detail", {}).get("confidence", {}).get("95") else "") + "。", "",
          "## 假設與方法", "",
          "- 假設：快測範本輸出的 RTP / 觸發率 / 分佈足以判定規格是否可進 Dev-spec（P-003）。",
          "- 方法：解析 report 的 BASE INFO / Game Detail / Symbol Hit / Reel Set / Multiple / SpecialGame Range / Decile 區塊；三向守門：① |RTP−target| ≤ 容許 ② 觸發率對照 P-005 體感區間 ③ config-spec 無效值阻斷。",
          f"- 目標來源：{'quicktest.yaml' if targets else '無（全部 SKIP）'}；信心依樣本數：≥1e7 high / ≥1e6 medium / 其餘 low。", "",
          "## 驗證報告 (Verification Report)", "", f"- 測試輪數：{spins:,} 轉 (Monte Carlo)"]
    for c in g["checks"]:
        icon = {"PASS": "🟢", "FAIL": "🔴", "SKIP": "⚪"}[c["status"]]
        L.append(f"- {c['id']}：{c['msg']} {icon} [{c['status']}]")
    L += ["", "## Findings", "", "| ID | 嚴重度 | 現象 | 來源 | 影響 |", "|----|--------|------|------|------|"]
    for i, f in enumerate(findings, 1):
        f["id"] = f"F-{i}"
        L.append(f"| {f['id']} | {f['sev']} | {f['what']} | {f['where']} | {f['impact']} |")
    if not findings:
        L.append("| — | — | 三向皆 PASS | — | — |")
    L += ["", "## Evidence", ""]
    for i, f in enumerate(findings, 1):
        L += [f"### E-{i}（支持 F-{i}）", "", f"- 方法：解析 `{src.name}` 對應區塊並與 quicktest.yaml 目標比對", f"- 輸出：`{json.dumps({k: v for k, v in f['ev'].items() if k != 'msg'}, ensure_ascii=False)}`", "- confidence: high", ""]
    if not findings:
        L += ["- 三向皆 PASS，無需額外證據。", ""]
    L += ["## Actions", "", "| ID | 對應 Finding | 建議 | 估時 |", "|----|--------------|------|------|"]
    for i, f in enumerate(findings, 1):
        L.append(f"| A-{i} | F-{i} | {f['action']} | 視調參 |")
    L += ["", "## RTP 拆解", "", "| Game | RTP | HitRate | Freq. | Multi | PlayTimes | RetriRate | MaxMulti |", "|---|---|---|---|---|---|---|---|"]
    for name, r in rep["games"].items():
        L.append(f"| {name} | {_pct(r.get('rtp'))} | {_pct(r.get('hitrate'))} | {r.get('freq') if r.get('freq') is not None else '—'} | {r.get('multi') if r.get('multi') is not None else '—'} | {r.get('playtimes') if r.get('playtimes') is not None else '—'} | {_pct(r.get('retrirate'))} | {r.get('maxmulti') if r.get('maxmulti') is not None else '—'} |")
    d = rep.get("detail", {})
    L += ["", f"- SD {d.get('sd')}；P.I. {d.get('pi')}；Pay Out Rate {_pct(d.get('pay_out_rate'))}；高均率 {_pct(d.get('high_avg_rate'))}；中均值 {d.get('mid_avg')}",
          "- 信賴區間：" + "；".join(f"{k}% {_pct(v[0])}~{_pct(v[1])}" for k, v in (d.get("confidence") or {}).items()), ""]
    L += ["## 符號命中與 RTP 貢獻", "", "| SYMBOL | x2 | x3 | x4 | x5 | 命中合計 | RTP 貢獻 |", "|---|---|---|---|---|---|---|"]
    for sym, r in rep["symbol_hit_rate"].items():
        rtp = rep["symbol_hit_rtp"].get(sym, {})
        L.append(f"| {sym} | {_pct(r.get('x2'))} | {_pct(r.get('x3'))} | {_pct(r.get('x4'))} | {_pct(r.get('x5'))} | {_pct(r.get('total'))} | {_pct(rtp.get('total'))} |")
    L += ["", "## 輪帶組 RTP", "", "| SET | RTP |", "|---|---|"] + [f"| {k} | {_pct(v)} |" for k, v in rep["reel_set_rtp"].items()]
    L += ["", "## 贏分倍數分佈", "", "| 區間 | 約每 N 局觸發 | ≥ 下限 每 N 局 |", "|---|---|---|"]
    for r in rep["multiple"]:
        L.append(f"| {r['range']} | {r['spins_per_hit'] if r['spins_per_hit'] is not None else '∞'} | {r['spins_per_hit_ge'] if r['spins_per_hit_ge'] is not None else '∞'} |")
    L += ["", "## 特殊遊戲區間", "", "| 區間 | 出現 Total | Main | Free | RTP Total | Main | Free | FG 平均手數 |", "|---|---|---|---|---|---|---|---|"]
    for r in rep["special_range"]:
        L.append(f"| {r['range']} | {_pct(r['appear']['total'])} | {_pct(r['appear']['main'])} | {_pct(r['appear']['free'])} | {_pct(r['rtp']['total'])} | {_pct(r['rtp']['main'])} | {_pct(r['rtp']['free'])} | {r['fg_avg_spin'] if r['fg_avg_spin'] is not None else '—'} |")
    L += ["", "## 十分位", "", "| | Total | Main | Free | FSpin |", "|---|---|---|---|---|"]
    for k, r in rep["decile"].items():
        L.append(f"| {k} | {r.get('total')} | {r.get('main')} | {r.get('free')} | {r.get('fspin')} |")
    L += ["", "## 邊界聲明", "",
          f"- 本報告基於 `{src.name}`（版本 {rep.get('version')}，{rep.get('generated_at')}）單次模擬；重跑快測後需重產。",
          "- 只回報數值與是否落在目標區間；不提出數值定案，不改寫規格（P-002）。",
          "- 未涵蓋：Jackpot 累積模擬（範本未啟用）、道具卡 / Play Bonus 區間（報告為「尚無資料」）、Volatility / Percentiles 定義（待 math-reviewer）。",
          f"- Content 軌檔名：`{md_name}`。", ""]
    return "\n".join(L)


def run_tool(script: str, *args) -> tuple[int, str]:
    p = C.MD_REPORT / script
    if not p.exists():
        return 0, f"（略過：找不到 {p}）"
    r = subprocess.run([sys.executable, str(p), *args], capture_output=True, text=True, encoding="utf-8")
    return r.returncode, (r.stdout + r.stderr)[-1200:]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--targets", help="quicktest.yaml：target_rtp / rtp_tolerance / feel[] / game / slug")
    ap.add_argument("--config-spec")
    ap.add_argument("--out", help="輸出目錄（預設 report 同目錄 /qt-report）")
    ap.add_argument("--publish")
    ap.add_argument("--wiki-schema")
    ap.add_argument("--date")
    a = ap.parse_args()
    src = pathlib.Path(a.report)
    if not src.exists():
        C.fail("BAD_INPUT", f"找不到 {src}")
    rep = parse_report(src.read_text(encoding="utf-8", errors="replace"))
    if rep.get("spins") is None or not rep["games"]:
        C.fail("QUERY_FAILED", "報告格式無法解析（缺 Times/TotalWin 或 BASE INFO）")
    award_p = src.with_name(f"AwardRangeData_{rep.get('version')}.csv")
    award = load_award_csv(award_p) if award_p.exists() else []
    rep["award_range"] = award
    targets = C.yaml_load(pathlib.Path(a.targets)) if a.targets else {}
    cfg = C.yaml_load(pathlib.Path(a.config_spec)) if a.config_spec else None
    g = gate(rep, targets, cfg)
    rep["gate"] = g
    out = pathlib.Path(a.out) if a.out else src.parent / "qt-report"
    out.mkdir(parents=True, exist_ok=True)
    C.atomic_write(out / "rtp-report.json", json.dumps(rep, ensure_ascii=False, indent=1))
    date = a.date or (rep.get("generated_at") or "")[:10] or dt.date.today().isoformat()
    if not re.match(r"\d{4}-\d{2}-\d{2}$", date):
        date = dt.date.today().isoformat()
    slug = re.sub(r"[^a-z0-9-]+", "-", str(targets.get("slug") or targets.get("game") or f"v{rep.get('version')}").lower()).strip("-")
    md_name = f"{date}-quicktest-{slug}.md"
    md_text = render_md(rep, g, targets, src, date, md_name, award)
    md_path = out / md_name
    C.atomic_write(md_path, md_text)
    rc, lint_out = run_tool("report_lint.py", *(["--wiki-schema", a.wiki_schema] if a.wiki_schema else []), str(md_path))
    result = {"json": str(out / "rtp-report.json"), "md": str(md_path), "lint": "PASS" if rc == 0 else "FAIL", "lint_output": lint_out.strip().splitlines()[-4:],
              "verdict": g["verdict"], "checks": [{"id": c["id"], "status": c["status"]} for c in g["checks"]],
              "rtp_total": rep.get("rtp_total"), "spins": rep.get("spins")}
    if rc != 0:
        C.fail("QUERY_FAILED", "qt_report 產出未通過 report_lint（引擎 bug）", lint_out, result)
    if a.publish:
        dst = pathlib.Path(a.publish)
        dst.mkdir(parents=True, exist_ok=True)
        shutil.copy2(md_path, dst / md_name)
        rrc, rout = run_tool("report_register.py", str(dst / md_name))
        result["published"] = str(dst / md_name)
        result["register"] = "OK" if rrc == 0 else rout
    C.emit(result, {"stage": "qt_report"})


if __name__ == "__main__":
    main()
