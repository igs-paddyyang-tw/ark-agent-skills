#!/usr/bin/env python3
"""gr_closeout — 十階段結案報告（工作流最後產出）：定版家檔案 → ark-md-report 契約的 md ＋ 單檔 HTML。

彙整（全部從檔案讀，不手抄數字）：
  十階段狀態（①～⑩）、④ 快測（quicktest/qt-report/rtp-report.json）、⑥ 逐局對帳（proto/go-parity*.json）、
  ⑨ 送審拍板（review/<slug>-decision/ 各章拍板欄）、⑩ 上線成效（docs/reports/*-<slug>-d<N>.json 的 verdict）。
Findings 由規則自動列出、verdict 自動判定（草擬）；md 內 <!-- human:notes --> 區段重產保留。
同層有 ark-md-report 時自動跑 report_lint 與 report_pair stamp。

用法:
  python gr_closeout.py --slug <slug> [--repo .] [--domain slot] [--date YYYY-MM-DD] [--out <md>] [--no-lint]
規格：專案 docs/specs/2026-10-20-ark-game-report-closeout-spec.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gr_common as C  # noqa: E402

MD_REPORT = C.SKILLS_ROOT / "ark-md-report" / "scripts"
STAGES = [  # (編號, 段, 名稱, 判定檔 glob)
    ("①", "A 競品", "競品分析", ["analysis/game-analysis.yaml"]),
    ("②", "B 規格", "遊戲規格書", ["spec/game-spec.v1.md", "spec/dev-spec/game-spec.md"]),
    ("③", "C 機率", "機率規格書（骨架）", ["prob/prob-spec.md"]),
    ("④", "C 機率", "Go 快測", ["quicktest/qt-report/rtp-report.json"]),
    ("⑤", "C 機率", "機率報告", ["prob/prob-spec.html"]),
    ("⑥", "C 驗證", "機率可視化驗證", ["proto/index.html", "proto/go-parity*.json"]),
    ("⑦", "D 實作", "遊戲試玩版", ["game/pixi-client/game.js"]),
    ("⑧", "D 實作", "Game Server", ["game/handoff.md", "game/go-server/go.mod"]),
    ("⑨", "E 送審", "送審拍板（上線前）", ["review/index.html"]),
    ("⑩", "F 成效", "上線成效", ["docs/reports/*-d[0-9]*.json"]),
]
LIGHT = {"g": "達標", "y": "觀察", "r": "未達標", "na": "資料不足"}
QNAME = {"Q1": "Q1 規模", "Q2": "Q2 玩家結構", "Q3": "Q3 黏著", "Q4": "Q4 深度", "Q5": "Q5 機率表現", "Q6": "Q6 增量", "H": "健康觀察"}


def game_name(data: pathlib.Path, slug: str) -> str:
    rd = data / "README.md"
    if rd.is_file():
        m = re.search(r'^game:\s*"?(.+?)"?\s*$', rd.read_text(encoding="utf-8", errors="replace"), re.M)
        if m:
            return m.group(1)
    gc = data / "proto" / "game-config.json"
    if gc.is_file():
        return json.loads(gc.read_text(encoding="utf-8")).get("game") or slug
    return slug


def is_restore(data: pathlib.Path) -> bool:
    """還原局（已上線遊戲回頭補資料）：有 kb/ 或 README mode: restore → 設計階段不適用。"""
    rd = data / "README.md"
    return (data / "kb").is_dir() or (rd.is_file() and re.search(r"^mode:\s*restore", rd.read_text(encoding="utf-8", errors="replace"), re.M) is not None)


def stage_rows(data: pathlib.Path) -> list[dict]:
    restore = is_restore(data)
    rows = []
    for no, seg, name, pats in STAGES:
        done = any(list(data.glob(p)) for p in pats)
        rows.append({"no": no, "seg": seg, "name": name, "done": done,
                     "status": "done" if done else ("n/a（還原局）" if restore and no not in ("④", "⑩") else "not-started")})
    return rows


def quicktest(data: pathlib.Path) -> dict | None:
    p = data / "quicktest" / "qt-report" / "rtp-report.json"
    if not p.is_file():
        return None
    r = json.loads(p.read_text(encoding="utf-8"))
    g = r.get("games", {})
    total = (g.get("Total") or {}).get("rtp") or r.get("rtp_total")
    feats = [(k, v) for k, v in g.items() if k not in ("Total", "MainGame", "SpecialGameTotal", "BonusTotal") and isinstance(v, dict) and v.get("freq")]
    return {"spins": r.get("spins"), "total": total, "main": (g.get("MainGame") or {}).get("rtp"), "feats": feats}


def parity(data: pathlib.Path) -> dict | None:
    files = sorted((data / "proto").glob("go-parity*.json")) if (data / "proto").is_dir() else []
    if not files:
        return None
    spins = mism = 0
    for f in files:
        try:
            x = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for run in (x.get("runs") if isinstance(x.get("runs"), list) else [x]):
            spins += int(run.get("spins") or run.get("rounds") or 0)
            mism += int(run.get("mismatch") or run.get("mismatches") or 0)
    return {"files": len(files), "spins": spins, "mismatch": mism}


def decisions(data: pathlib.Path) -> list[dict]:
    """⑨ 拍板書各章拍板欄：| R-x 項目 | 決議 | 拍板人 | 日期 |（同 ark-game-proto review_build 規則）。"""
    out = []
    for book in sorted((data / "review").glob("*/book.yaml")) if (data / "review").is_dir() else []:
        for md in sorted(book.parent.glob("[0-8][0-9]-*.md")):
            txt = md.read_text(encoding="utf-8")
            sec = txt.split("### 拍板欄", 1)
            if len(sec) < 2:
                continue
            row = next((r for r in sec[1].splitlines() if re.match(r"\|\s*R-\d", r)), None)
            if not row:
                continue
            c = [x.strip() for x in row.strip().strip("|").split("|")] + ["", "", ""]
            out.append({"id": c[0].split()[0], "item": c[0].split(" ", 1)[-1], "decision": c[1], "by": c[2], "date": c[3],
                        "pending": c[1].startswith("（待拍板") or not c[1], "file": md.relative_to(data).as_posix()})
    return out


def perf_reports(data: pathlib.Path, slug: str) -> list[dict]:
    out = []
    for p in sorted((data / "docs" / "reports").glob(f"*-{slug}-d*.json")) if (data / "docs" / "reports").is_dir() else []:
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        m = r.get("meta", {})
        v = r.get("verdict", {})
        q5_base = any("暫定基準" in str((vv.get("rtp") or {}).get("baseline", "")) for vv in (r.get("views") or {}).values())
        out.append({"stage": int(m.get("stage") or 0), "through": m.get("data_through"), "launch": m.get("launch_date"),
                    "headline": v.get("headline", ""), "lights": v.get("lights", {}), "next": v.get("next", []),
                    "json": p, "html": p.with_suffix(".html"), "q5_provisional": q5_base, "bench": m.get("benchmark_label")})
    return sorted(out, key=lambda x: x["stage"])


def rules(stages, qt, dec, perf) -> list[dict]:
    """Findings 規則（FR-5）。每條：sev、what、where、impact、evidence、action、owner。"""
    f = []
    if qt is None:
        f.append({"sev": "P1", "what": "缺 ④ 快測報告 rtp-report.json", "where": "quicktest/qt-report/", "impact": "機率沒有模擬驗證，不能送審",
                  "evidence": "定版家查無 quicktest/qt-report/rtp-report.json", "action": "跑 ark-game-quicktest 產出報告", "owner": "機率"})
    for p in perf:
        reds = [QNAME.get(k, k) for k, v in p["lights"].items() if v == "r"]
        if reds:
            f.append({"sev": "P1", "what": f"⑩ D+{p['stage']} 未達標：{'、'.join(reds)}", "where": p["json"].name, "impact": "上線表現有問題項，需定調處置",
                      "evidence": f"{p['json'].name} verdict.lights：{', '.join(f'{k}={v}' for k, v in p['lights'].items())}", "action": "依成效報告「下一步」逐條處置並在下一檢查點複查", "owner": "企劃／營運／機率"})
    if perf and perf[-1]["q5_provisional"]:
        p = perf[-1]
        f.append({"sev": "P2", "what": f"⑩ D+{p['stage']} 的 Q5 機率表現用暫定基準（同期新機實際 RTP），線上設定檔目標 RTP 未提供",
                  "where": "report/report-d<N>.yaml spec", "impact": "只能判斷是否落在平台常態，不能判斷是否符合設計",
                  "evidence": f"{p['json'].name} views.*.rtp.baseline 標「暫定基準」", "action": "機率人員提供線上設定檔版本、目標 RTP、σ，回填 spec 後重跑", "owner": "機率"})
    pend = [d for d in dec if d["pending"]]
    if pend:
        f.append({"sev": "P2", "what": f"⑨ 送審拍板尚有 {len(pend)} 件待拍板（{'、'.join(d['id'] for d in pend)}）", "where": "review/<slug>-decision/",
                  "impact": "待拍板事項未決前不能排上線", "evidence": "；".join(f"{d['id']} {d['item']}：{d['decision']}" for d in pend),
                  "action": "主管逐章拍板、填各章拍板欄後重跑 review_build 與本報告", "owner": "主管"})
    done = {s["no"]: s["done"] for s in stages}
    if done.get("⑨") is False and all(done.get(n) for n in ("④", "⑦", "⑧")):
        f.append({"sev": "P2", "what": "①～⑧ 已完成但沒有 ⑨ 送審拍板包", "where": "review/", "impact": "主管拍板缺一致的入口",
                  "evidence": "定版家查無 review/index.html", "action": "跑 ark-game-proto review_build 發布拍板包", "owner": "企劃"})
    return f


def compose(slug: str, game: str, date: str, stages, qt, par, dec, perf, findings, human: str) -> tuple[str, str]:
    n_done = sum(1 for s in stages if s["done"])
    p0 = sum(1 for x in findings if x["sev"] == "P0")
    p1 = sum(1 for x in findings if x["sev"] == "P1")
    verdict = "broken" if p0 else ("needs-work" if p1 else "sound")
    cnt = {k.lower(): sum(1 for x in findings if x["sev"] == k) for k in ("P0", "P1", "P2", "P3")}
    srcs = ["README.md"] + [s for s, ok in (("quicktest/qt-report/rtp-report.json", qt), ("review/index.html", any(s_["no"] == "⑨" and s_["done"] for s_ in stages))) if ok]
    srcs += [p["json"].name and f"docs/reports/{p['json'].name}" for p in perf]
    fm = (f'---\ntitle: "{game} 結案報告：十階段完成 {n_done} 站"\ntype: review\nsubject: "data/slot/{slug}"\ndate: {date}\nauthor: ark-game-report gr_closeout\n'
          f"source_skill: ark-game-report\nverdict: {verdict}\nconfidence: medium\nfindings: {{ p0: {cnt['p0']}, p1: {cnt['p1']}, p2: {cnt['p2']}, p3: {cnt['p3']} }}\n"
          f"tags: [slot, pipeline, workflow, quicktest, probability]\nsources:\n" + "".join(f"  - data/slot/{slug}/{s}\n" for s in srcs) + "---\n\n")
    L = [fm, f"# {game} 結案報告：十階段完成 {n_done} 站\n\n> 由 ark-game-report gr_closeout 於 {date} 依定版家檔案草擬；數字皆可追溯到 sources。verdict 與 Findings 為規則判定，人工確認後定版。\n\n"]
    # Verdict
    last = perf[-1] if perf else None
    pend = [d for d in dec if d["pending"]]
    parts = [f"{verdict} — 十階段完成 {n_done} 個"]
    if qt and qt.get("total"):
        parts.append(f"快測 {int(qt['spins'] or 0):,} 局總 RTP {qt['total']:.2%}")
    if par:
        parts.append(f"逐局對帳 {par['spins']:,} 局不一致 {par['mismatch']}")
    if dec:
        parts.append(f"⑨ 拍板 {len(dec) - len(pend)}／{len(dec)} 件已決")
    if last:
        parts.append(f"⑩ D+{last['stage']}：{last['headline'].rstrip('。')}")
    elif not any(s["no"] == "⑩" and s["done"] for s in stages):
        parts.append("⑩ 上線成效待上線後補")
    restore = any(s["status"].startswith("n/a") for s in stages)
    L.append("## Verdict\n\n" + "；".join(parts) + "。\n\n" + ("> 本款是還原局（已上線遊戲回頭補資料），①②⑥～⑨ 設計階段不適用。\n\n" if restore else ""))
    # 十階段
    L.append("## 十階段完成度\n\n| # | 段 | 階段 | 狀態 |\n|---|---|---|---|\n" + "".join(f"| {s['no']} | {s['seg']} | {s['name']} | {s['status']} |\n" for s in stages) + "\n")
    # 快測
    if qt:
        L.append("## 快測關鍵數字\n\n" + (f"總 RTP {qt['total']:.2%}" if qt.get("total") else "總 RTP —") + (f"（主遊戲 {qt['main']:.2%}）" if qt.get("main") else "") + f"，{int(qt['spins'] or 0):,} 局。\n\n")
        if perf and perf[-1]["q5_provisional"]:
            L.append("> 快測數字屬於定版家的設計版本；線上設定檔版本未確認一致，⑩ 的機率表現改用同期新機暫定基準（見 Findings）。\n\n")
        if qt["feats"]:
            L.append("| 玩法 | 多久來一次 | 平均倍數 | 佔 RTP |\n|---|---|---|---|\n" + "".join(f"| {k} | 每 {v['freq']:,.1f} 轉 | {v.get('multi') or 0:,.2f}× | {(v.get('rtp') or 0):.2%} |\n" for k, v in qt["feats"]) + "\n")
    # ⑨
    if dec:
        L.append("## ⑨ 送審拍板\n\n| # | 待拍板事項 | 決議 | 拍板人 | 日期 |\n|---|---|---|---|---|\n" + "".join(f"| {d['id']} | {d['item']} | {d['decision']} | {d['by'] or '—'} | {d['date'] or '—'} |\n" for d in dec) + "\n")
    # ⑩
    if perf:
        keys = list(QNAME)
        L.append("## ⑩ 上線成效\n\n" + f"基準：{perf[-1].get('bench') or '—'}。上線日 {perf[-1].get('launch') or '—'}。\n\n")
        L.append("| 問題 | " + " | ".join(f"D+{p['stage']}" for p in perf) + " |\n|---|" + "---|" * len(perf) + "\n")
        for k in keys:
            L.append(f"| {QNAME[k]} | " + " | ".join(LIGHT.get(p["lights"].get(k, "na"), "—") for p in perf) + " |\n")
        L.append("\n報告：" + "、".join(f"[D+{p['stage']}]({p['html'].name})" for p in perf if p["html"].is_file()) + "\n\n")
        if last and last["next"]:
            L.append("最新檢查點的下一步：\n\n" + "".join(f"- {x}\n" for x in last["next"]) + "\n")
    # 人工區
    L.append("## 人工補充\n\n<!-- human:notes -->\n" + (human.strip() + "\n" if human.strip() else "（人工填寫：案例敘事、技術亮點、結案後還要決定的事；重產時保留本區）\n") + "<!-- /human -->\n\n")
    # Findings／Evidence／Actions
    L.append("## Findings\n\n")
    if findings:
        L.append("| ID | 嚴重度 | 現象 | 位置 | 影響 |\n|----|--------|------|------|------|\n" + "".join(f"| F-{i} | {x['sev']} | {x['what']} | `{x['where']}` | {x['impact']} |\n" for i, x in enumerate(findings, 1)) + "\n")
    else:
        L.append("規則檢查未發現問題。\n\n")
    L.append("## Evidence\n\n")
    for i, x in enumerate(findings, 1):
        L.append(f"### E-{i}（支持 F-{i}）\n\n{x['evidence']}\n\n")
    if not findings:
        L.append("各階段判定依據見「十階段完成度」與 sources。\n\n")
    L.append("## Actions\n\n")
    if findings:
        L.append("| ID | 對應 Finding | 建議 | 負責 |\n|----|--------------|------|------|\n" + "".join(f"| A-{i} | F-{i} | {x['action']} | {x['owner']} |\n" for i, x in enumerate(findings, 1)) + "\n")
    else:
        L.append("無待辦。\n\n")
    L.append("## 邊界聲明\n\n"
             f"- 分析基準：{date} 的 `data/slot/{slug}/` 定版家檔案；之後的修改不在結論範圍\n"
             "- 快測 RTP 為模擬結果；上線後實際 RTP 以 ⑩ 成效報告為準\n"
             "- verdict 與 Findings 由規則草擬，最終結論由人確認\n")
    return "".join(L), verdict


CSS = """:root{--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--border:#e1e0d9;--accent:#2a78d6;--good:#0ca30c;--warn:#b07a00;--crit:#d03b3b}
@media (prefers-color-scheme:dark){:root{--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;--border:#2c2c2a;--accent:#3987e5}}
*{box-sizing:border-box}body{margin:0;background:var(--page);color:var(--ink);font:14px/1.65 "Microsoft JhengHei","PingFang TC",system-ui,sans-serif}
.wrap{max-width:980px;margin:0 auto;padding:24px 16px 56px}h1{font-size:24px;margin:0 0 8px}h2{font-size:17px;margin:28px 0 10px;padding-top:6px;border-top:1px solid var(--border)}h3{font-size:14px;margin:16px 0 6px}
blockquote{margin:8px 0;padding:8px 12px;border-left:4px solid var(--accent);background:var(--surface);color:var(--ink2)}
table{width:100%;border-collapse:collapse;background:var(--surface);border:1px solid var(--border);border-radius:10px;overflow:hidden;margin:8px 0}
th,td{padding:7px 10px;border-bottom:1px solid var(--border);text-align:left;vertical-align:top}th{color:var(--ink2);font-weight:600;background:rgba(127,127,127,.06)}
code{font-size:12px;background:rgba(127,127,127,.12);padding:1px 4px;border-radius:4px}a{color:var(--accent)}
.lg{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;font-weight:700}.lg-g{background:rgba(12,163,12,.14);color:var(--good)}.lg-y{background:rgba(250,178,25,.18);color:var(--warn)}.lg-r{background:rgba(208,59,59,.14);color:var(--crit)}.lg-na{background:rgba(137,135,129,.15);color:var(--muted)}
footer{margin-top:32px;color:var(--muted);font-size:12px}"""


def to_html(md: str, title: str) -> str:
    import markdown  # noqa: PLC0415
    body = re.sub(r"\A---\n.*?\n---\n", "", md, flags=re.S)
    body = re.sub(r"<!-- /?human[^>]*-->", "", body)
    h = markdown.markdown(body, extensions=["tables", "fenced_code"])
    for word, cls in (("達標", "g"), ("觀察", "y"), ("未達標", "r"), ("資料不足", "na")):   # 燈號表格上色
        h = re.sub(rf"<td>{word}</td>", f'<td><span class="lg lg-{cls}">{word}</span></td>', h)
    h = re.sub(r'<a href="([^"#][^"]*)"', r'<a target="_blank" rel="noopener" href="\1"', h)
    return (f'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body><div class=\"wrap\">{h}"
            "<footer>ark-game-report gr_closeout · 內部文件</footer></div></body></html>\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="十階段結案報告（ark-game-report 工作流最後產出）")
    ap.add_argument("--slug", required=True)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--domain", default="slot")
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--out")
    ap.add_argument("--no-lint", action="store_true")
    a = ap.parse_args()
    repo = pathlib.Path(a.repo).resolve()
    data = repo / "data" / a.domain / a.slug
    if not data.is_dir():
        C.fail("BAD_INPUT", f"找不到定版家 {data}")
    out = pathlib.Path(a.out) if a.out else data / "docs" / "reports" / f"{a.date}-{a.slug}-closeout.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    human = ""
    if out.is_file():
        m = re.search(r"<!-- human:notes -->\n(.*?)<!-- /human -->", out.read_text(encoding="utf-8"), re.S)
        if m and not m.group(1).strip().startswith("（人工填寫"):
            human = m.group(1)
    game = game_name(data, a.slug)
    stages, qt, par, dec = stage_rows(data), quicktest(data), parity(data), decisions(data)
    perf = perf_reports(data, a.slug)
    findings = rules(stages, qt, dec, perf)
    md, verdict = compose(a.slug, game, a.date, stages, qt, par, dec, perf, findings, human)
    out.write_text(md, encoding="utf-8")
    hp = out.with_suffix(".html")
    hp.write_text(to_html(md, f"{game} 結案報告"), encoding="utf-8")
    lint = pair = None
    if not a.no_lint and (MD_REPORT / "report_lint.py").is_file():
        r = subprocess.run([sys.executable, "-X", "utf8", str(MD_REPORT / "report_lint.py"), str(out)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        lint = {"rc": r.returncode, "tail": (r.stdout or r.stderr).strip().splitlines()[-1:]}
        r = subprocess.run([sys.executable, "-X", "utf8", str(MD_REPORT / "report_pair.py"), "stamp", str(out), str(hp)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        pair = {"rc": r.returncode}
    C.emit({"md": str(out), "html": str(hp), "verdict": verdict, "stages_done": sum(1 for s in stages if s["done"]),
            "findings": [f"{x['sev']} {x['what']}" for x in findings], "perf_reports": [f"D+{p['stage']}" for p in perf],
            "decisions": f"{sum(1 for d in dec if not d['pending'])}/{len(dec)}", "report_lint": lint, "report_pair": pair}, {"stage": "closeout"})
    if lint and lint["rc"] != 0:
        sys.exit(3)


if __name__ == "__main__":
    main()
