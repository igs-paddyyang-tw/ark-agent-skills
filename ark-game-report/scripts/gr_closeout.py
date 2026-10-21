#!/usr/bin/env python3
"""gr_closeout — 十階段結案報告（工作流最後產出）：定版家檔案 → ark-md-report 契約的 md ＋ 樣板版型單檔 HTML。

版型以「樂奇 aidev 結案報告」為樣板（ark-html-report boardroom 風格，CSS 在 assets/closeout.css）：
  header → 摘要 → KPI → 00 藍圖 → 第一部 01 十階段／02 ①～③／03 ④～⑥／04 ⑦⑧／05 ⑨⑩
  → 第二部 06 基礎建設／07 實戰落地 → 08 時間軸 → 09 導入 → 10 結案後還要決定的事 → Findings／Evidence／Actions／邊界聲明。
自動段全部讀檔（不手抄數字）：十階段（⑨ 拍板欄全填才算完成）、④ rtp-report（gate.checks 觸發目標／體感區間、95% CI）、
  ⑥ proto/go-parity.json、⑦ review/checks/stage-smoke.json＋截圖、⑨ 拍板欄、⑩ 本款 docs/reports/*-<slug>-d<N>.json。
⑩ 只放本款；未上線寫「上線後補」，不拿別款當範本。
敘事段用人工區 <!-- human:<key> -->…<!-- /human -->，重產保留；未填的人工區 HTML 不顯示。
同層有 ark-md-report 時自動跑 report_lint 與 report_pair stamp。

用法:
  python gr_closeout.py --slug <slug> [--repo .] [--domain slot] [--date YYYY-MM-DD] [--out <md>] [--no-lint]
規格：專案 docs/specs/2026-10-20-ark-game-report-closeout-spec.md（v0.2）
"""
from __future__ import annotations

import argparse
import base64
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
CSS_FILE = pathlib.Path(__file__).resolve().parents[1] / "assets" / "closeout.css"
STAGES = [  # (編號, 段, 名稱, 判定檔 glob)
    ("①", "A 競品", "競品分析", ["analysis/game-analysis.yaml"]),
    ("②", "B 規格", "遊戲規格書", ["spec/game-spec.v1.md", "spec/dev-spec/game-spec.md"]),
    ("③", "C 機率", "機率規格書（骨架）", ["prob/prob-spec.md"]),
    ("④", "C 機率", "Go 快測", ["quicktest/qt-report/rtp-report.json"]),
    ("⑤", "C 機率", "機率報告", ["prob/prob-spec.html"]),
    ("⑥", "C 驗證", "機率可視化驗證", ["proto/index.html", "proto/go-parity*.json"]),
    ("⑦", "D 實作", "遊戲試玩版", ["game/pixi-client/game.js"]),
    ("⑧", "D 實作", "Game Server", ["game/handoff.md", "game/go-server/go.mod"]),
    ("⑨", "E 送審", "送審拍板（上線前）", None),          # 特判：拍板欄全填才算完成
    ("⑩", "F 成效", "上線成效", ["docs/reports/*-d[0-9]*.json"]),
]
LIGHT = {"g": "達標", "y": "觀察", "r": "未達標", "na": "資料不足"}
QNAME = {"Q1": "Q1 規模", "Q2": "Q2 玩家結構", "Q3": "Q3 黏著", "Q4": "Q4 深度", "Q5": "Q5 機率表現", "Q6": "Q6 增量", "H": "健康觀察"}
STATUS_TXT = {"done": "完成", "review": "送審中", "pending-launch": "上線後", "not-started": "未開始"}
HUMAN_KEYS = [  # (key, md 段落標題, 填寫提示)
    ("title", None, "一句話標題（選填；空白則用「<遊戲> 結案報告：十階段完成 N 站」）"),
    ("lede", None, "副標一段話：這款做到哪、還差什麼"),
    ("summary", None, "摘要補充條列（方法可複製、亮點等）"),
    ("blueprint", "00 藍圖全貌", "兩層地基（基礎建設／實戰落地）與 N-M-P-Q"),
    ("s1-3", None, "①～③ 補充（決議數、手法卡、圖說）"),
    ("s4-6", None, "④～⑥ 補充（主菜佔比、壓力版覆蓋等）"),
    ("s7-8", None, "⑦⑧ 補充（Server 架構圖、引擎驗收結果）"),
    ("s9-10", None, "⑨⑩ 補充"),
    ("infra", "06 技術亮點：基礎建設", "大腦／記憶／技能、團隊編制、人做的事"),
    ("ground", "07 技術亮點：實戰落地", "知識庫、手法卡、佈局契約、守門腳本、共用引擎"),
    ("timeline", "08 實戰時間軸", "日期｜做了什麼（一行一筆：`- **10/16** 製程計畫…`）"),
    ("adopt", "09 導入與可複用資產", "導入步驟、可複用資產、經驗"),
    ("next", None, "結案後還要決定的事（補充列）"),
]


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
            sug = re.search(r"建議([^）]*)", c[1])
            out.append({"id": c[0].split()[0], "item": c[0].split(" ", 1)[-1], "decision": c[1], "by": c[2], "date": c[3],
                        "suggest": sug.group(1).lstrip("：") if sug else "",
                        "pending": c[1].startswith("（待拍板") or not c[1], "file": md.relative_to(data).as_posix()})
    return out


def stage_rows(data: pathlib.Path, dec: list[dict]) -> list[dict]:
    restore = is_restore(data)
    rows = []
    for no, seg, name, pats in STAGES:
        if pats is None:                                               # ⑨：拍板書存在且拍板欄全填才算完成
            has_pack = (data / "review" / "index.html").is_file()
            done = has_pack and bool(dec) and not any(d["pending"] for d in dec)
            status = "done" if done else ("review" if has_pack else ("n/a（還原局）" if restore else "not-started"))
        else:
            done = any(list(data.glob(p)) for p in pats)
            status = "done" if done else ("pending-launch" if no == "⑩" and not restore else ("n/a（還原局）" if restore and no not in ("④", "⑩") else "not-started"))
        rows.append({"no": no, "seg": seg, "name": name, "done": done, "status": status})
    return rows


def quicktest(data: pathlib.Path) -> dict | None:
    p = data / "quicktest" / "qt-report" / "rtp-report.json"
    if not p.is_file():
        return None
    r = json.loads(p.read_text(encoding="utf-8"))
    g = r.get("games", {})
    total = (g.get("Total") or {}).get("rtp") or r.get("rtp_total")
    feats = [(k, v) for k, v in g.items() if k not in ("Total", "MainGame", "SpecialGameTotal", "BonusTotal") and isinstance(v, dict) and v.get("freq")]
    gate = r.get("gate") or {}
    checks = gate.get("checks") or []
    rtp_chk = next((c for c in checks if c.get("id") == "rtp"), {})
    feel = [c for c in checks if str(c.get("id", "")).startswith("feel:")]
    ci = ((r.get("detail") or {}).get("confidence") or {}).get("95")
    return {"spins": r.get("spins"), "total": total, "main": (g.get("MainGame") or {}).get("rtp") or r.get("rtp_main"),
            "special": r.get("rtp_special"), "feats": feats, "verdict": gate.get("verdict"), "target": rtp_chk.get("target"),
            "tol": rtp_chk.get("tol"), "rtp_pass": rtp_chk.get("status") == "PASS" if rtp_chk else None, "feel": feel, "ci": ci}


def parity(data: pathlib.Path) -> dict | None:
    """⑥ 逐局對帳：有 proto/go-parity.json（彙整檔）就只讀它，避免與分檔重複計；否則加總分檔。"""
    pd = data / "proto"
    if not pd.is_dir():
        return None
    main = pd / "go-parity.json"
    files = [main] if main.is_file() else sorted(pd.glob("go-parity*.json"))
    if not files:
        return None
    runs = []
    for f in files:
        try:
            x = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for run in (x.get("runs") if isinstance(x.get("runs"), list) else [x]):
            runs.append({"kind": run.get("kind") or "", "seed": run.get("seed"), "odds": run.get("odds") or "",
                         "rounds": int(run.get("spins") or run.get("rounds") or 0), "features": run.get("features"),
                         "mismatch": int(run.get("mismatch") or run.get("mismatches") or 0)})
    formal = [r for r in runs if r["kind"] in ("formal", "")]
    return {"runs": runs, "spins": sum(r["rounds"] for r in runs), "mismatch": sum(r["mismatch"] for r in runs),
            "formal_spins": sum(r["rounds"] for r in formal), "source": files[0].relative_to(data).as_posix()}


def smoke(data: pathlib.Path) -> dict | None:
    p = data / "review" / "checks" / "stage-smoke.json"
    if not p.is_file():
        return None
    s = json.loads(p.read_text(encoding="utf-8"))
    res = s.get("checks") or s.get("results") or []
    return {"pass": s.get("pass"), "n_ok": sum(1 for x in res if x.get("ok")), "n": len(res), "fps": s.get("fps"),
            "browser": s.get("browser"), "scenes": s.get("scenes") or [], "shots": s.get("review_shots") or []}


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


def stage_outputs(data: pathlib.Path) -> dict[str, dict]:
    """②～⑧ 階段卡：一句說明、偵測到的產出、定版家路徑、同目錄 html（報告位置 docs/reports/ 起算的相對連結）。"""
    def ex(p):
        return (data / p).exists()

    def cnt(g):
        return len(list(data.glob(g)))

    def link(p, label):
        return (label, "../../" + p) if ex(p) else None

    rep_html = sorted(data.glob("analysis/report/*.html"))
    qt_html = sorted(data.glob("quicktest/qt-report/*.html"))
    ev = data / "analysis" / "evidence.jsonl"
    n_ev = sum(1 for _ in ev.open(encoding="utf-8")) if ev.is_file() else 0
    S = {
        "①": {"desc": "把競品素材拆成機制、證據與知識庫手法，作為規格書的依據。", "dir": "analysis/",
              "out": [x for x in ("game-analysis.yaml" if ex("analysis/game-analysis.yaml") else "",
                                  f"evidence.jsonl（{n_ev} 筆證據）" if n_ev else "", "kb-refs.yaml" if ex("analysis/kb-refs.yaml") else "",
                                  f"分析報告 {cnt('analysis/report/*.md')} 份（md＋html）" if cnt("analysis/report/*.md") else "") if x],
              "links": [x for x in ((("分析報告", "../../" + rep_html[0].relative_to(data).as_posix()) if rep_html else None),) if x]},
        "②": {"desc": "定玩法、規則與體驗；工程契約 config-spec 與 dev-spec 交給後續各站。", "dir": "spec/",
              "out": [x for x in ("game-spec.v1（md＋html）" if ex("spec/game-spec.v1.md") else "", "config-spec.yaml" if ex("spec/config-spec.yaml") else "",
                                  f"dev-spec {cnt('spec/dev-spec/*.md')} 份" if cnt("spec/dev-spec/*.md") else "", "gdd 原始檔（gdd-pack）" if ex("spec/gdd") else "") if x],
              "links": [x for x in (link("spec/game-spec.v1.html", "遊戲規格書"), link("review/gdd-overview.html", "素材總覽")) if x]},
        "③": {"desc": "先定體驗目標，再由知識庫手法卡推導參數；每個數字可回溯。", "dir": "prob/",
              "out": [x for x in ("prob-spec.md／.html" if ex("prob/prob-spec.md") else "",
                                  f"機率架構設計 {cnt('docs/designs/*prob-arch*.md')} 份" if cnt("docs/designs/*prob-arch*.md") else "",
                                  f"odds 設定檔 {cnt('quicktest/odds/*.json')} 份" if cnt("quicktest/odds/*.json") else "") if x],
              "links": [x for x in (link("prob/prob-spec.html", "機率規格書"),) if x]},
        "④": {"links": [x for x in ((("快測報告", "../../" + qt_html[0].relative_to(data).as_posix()) if qt_html else None),) if x]},
        "⑥": {"links": [x for x in (link("proto/index.html", "機率驗證台"),) if x]},
        "⑦": {"links": [x for x in (link("review/play.html", "試玩版"),) if x]},
        "⑧": {"links": [x for x in (link("game/handoff.html", "工程交付單"),) if x], "server": ex("game/go-server/go.mod"),
              "handoff": ex("game/handoff.md")},
        "⑨": {"links": [x for x in (link("review/index.html", "拍板書"),) if x]},
    }
    play = data / "review" / "play.html"
    S["⑦"]["play_mb"] = round(play.stat().st_size / 1024 / 1024, 1) if play.is_file() else None
    lr = data / "layout-report.json"
    S["⑤"] = {"layout": (json.loads(lr.read_text(encoding="utf-8")).get("verdict") if lr.is_file() else None)}
    return S


def rules(stages, qt, dec, perf, par) -> list[dict]:
    """Findings 規則。每條：sev、what、where、impact、evidence、action、owner。"""
    f = []
    if qt is None:
        f.append({"sev": "P1", "what": "缺 ④ 快測報告 rtp-report.json", "where": "quicktest/qt-report/", "impact": "機率沒有模擬驗證，不能送審",
                  "evidence": "定版家查無 quicktest/qt-report/rtp-report.json", "action": "跑 ark-game-quicktest 產出報告", "owner": "機率"})
    if par and par["mismatch"]:
        f.append({"sev": "P1", "what": f"⑥ 逐局對帳有 {par['mismatch']} 局不一致", "where": par["source"], "impact": "兩套引擎結果分岔，快測驗過的數學不等於上線的數學",
                  "evidence": "；".join(f"{r['kind']} seed {r['seed']}：{r['mismatch']}／{r['rounds']:,}" for r in par["runs"] if r["mismatch"]),
                  "action": "以 firstMismatch 定位分岔點修引擎後重跑 parity", "owner": "工程"})
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
    st = {s["no"]: s for s in stages}
    if st["⑨"]["status"] == "not-started" and all(st[n]["done"] for n in ("④", "⑦", "⑧")):
        f.append({"sev": "P2", "what": "①～⑧ 已完成但沒有 ⑨ 送審拍板包", "where": "review/", "impact": "主管拍板缺一致的入口",
                  "evidence": "定版家查無 review/index.html", "action": "跑 ark-game-proto review_build 發布拍板包", "owner": "企劃"})
    return f


# ───────────────────────── md（Content 軌） ─────────────────────────

def hblock(key: str, human: dict, hint: str) -> str:
    body = human.get(key, "").strip()
    return f"<!-- human:{key} -->\n" + (body if body else f"（人工填寫：{hint}）") + "\n<!-- /human -->\n\n"


def filled(human: dict, key: str) -> bool:
    v = human.get(key, "").strip()
    return bool(v) and not v.startswith("（人工填寫")


def pct(x, d=2):
    return f"{x:.{d}%}" if isinstance(x, (int, float)) else "—"


def dec_state(d: dict) -> str:
    if d["pending"]:
        return "⏳ 待拍板"
    who = f"（{d['by']} {d['date']}）".replace(" ）", "）") if d["by"] else ""
    return f"✅ {d['decision']}{who}"


def one_in(rate):
    return f"1/{1 / rate:,.0f}" if rate else "—"


def compose(slug, game, date, stages, qt, par, dec, perf, sm, so, findings, human: dict) -> tuple[str, str, dict]:
    n_done = sum(1 for s in stages if s["done"])
    p0 = sum(1 for x in findings if x["sev"] == "P0")
    p1 = sum(1 for x in findings if x["sev"] == "P1")
    verdict = "broken" if p0 else ("needs-work" if p1 else "sound")
    cnt = {k.lower(): sum(1 for x in findings if x["sev"] == k) for k in ("P0", "P1", "P2", "P3")}
    st = {s["no"]: s for s in stages}
    restore = any(s["status"].startswith("n/a") for s in stages)
    pend = [d for d in dec if d["pending"]]
    title = human.get("title", "").strip() if filled(human, "title") else f"{game} 結案報告：十階段完成 {n_done} 站"
    tails = []
    if st["⑨"]["status"] == "review":
        tails.append(f"⑨ 送審中（{len(dec) - len(pend)}／{len(dec)} 件已拍板）")
    if not perf and not restore:
        tails.append("⑩ 上線後補")
    lede = human.get("lede", "").strip() if filled(human, "lede") else (
        f"{game}：十階段完成 {n_done} 站" + ("；" + "，".join(tails) if tails else "") + "。數字皆讀自定版家檔案。")
    srcs = ["README.md"] + [s for s, ok in (("quicktest/qt-report/rtp-report.json", qt), ("proto/go-parity.json", par),
                                            ("review/index.html", (pathlib.Path("x"),) if st["⑨"]["status"] != "not-started" else None)) if ok]
    srcs += [f"docs/reports/{p['json'].name}" for p in perf]
    fm = (f'---\ntitle: "{title}"\ntype: review\nsubject: "data/slot/{slug}"\ndate: {date}\nauthor: ark-game-report gr_closeout\n'
          f"source_skill: ark-game-report\nverdict: {verdict}\nconfidence: medium\nfindings: {{ p0: {cnt['p0']}, p1: {cnt['p1']}, p2: {cnt['p2']}, p3: {cnt['p3']} }}\n"
          f"tags: [slot, pipeline, workflow, quicktest, probability]\nsources:\n" + "".join(f"  - data/slot/{slug}/{s}\n" for s in srcs) + "---\n\n")
    L = [fm, f"# {title}\n\n{hblock('title', human, HUMAN_KEYS[0][2])}> {lede}\n\n{hblock('lede', human, HUMAN_KEYS[1][2])}"]
    L.append(f"> 由 ark-game-report gr_closeout 於 {date} 依定版家檔案產出；自動段數字皆可追溯到 sources，人工區（`<!-- human:* -->`）重產保留。\n\n")
    # 摘要
    bullets = [f"**結論：**十階段完成 {n_done} 個" + (f"；總 RTP **{pct(qt['total'])}**" + (f"（目標 {pct(qt['target'], 1)} ±{qt['tol'] * 100:.1f}，快測 {int(qt['spins'] or 0):,} 局）" if qt and qt.get("target") else "") + (f"，三向判定 {qt['verdict']}" if qt and qt.get("verdict") else "") if qt else "") + "。"]
    if par:
        bullets.append(f"**數學一致：**Go ⇄ JS 逐局對帳 **{par['spins']:,} 局 {par['mismatch']} 不一致**。")
    if dec:
        bullets.append(f"**待決定：**拍板書 {len(dec)} 件，{len(pend)} 件待拍板（{'、'.join(d['id'] + ' ' + d['item'] for d in pend) or '無'}）。")
    bullets.append("**⑩ 上線成效：**" + (f"D+{perf[-1]['stage']}：{perf[-1]['headline'].rstrip('。')}。" if perf else "尚未上線，上線後以 ark-game-report 產 D+7／D+14／D+30。"))
    L.append("## 摘要\n\n" + "".join(f"- {b}\n" for b in bullets) + "\n" + hblock("summary", human, HUMAN_KEYS[2][2]))
    # Verdict
    parts = [f"{verdict} — 十階段完成 {n_done} 個"]
    if qt and qt.get("total"):
        parts.append(f"快測 {int(qt['spins'] or 0):,} 局總 RTP {pct(qt['total'])}")
    if par:
        parts.append(f"逐局對帳 {par['spins']:,} 局不一致 {par['mismatch']}")
    if dec:
        parts.append(f"⑨ 拍板 {len(dec) - len(pend)}／{len(dec)} 件已決")
    parts.append(f"⑩ D+{perf[-1]['stage']}：{perf[-1]['headline'].rstrip('。')}" if perf else "⑩ 上線成效待上線後補")
    L.append("## Verdict\n\n" + "；".join(parts) + "。\n\n" + ("> 本款是還原局（已上線遊戲回頭補資料），①②⑥～⑨ 設計階段不適用。\n\n" if restore else ""))
    L.append("## 00 藍圖全貌\n\n" + hblock("blueprint", human, HUMAN_KEYS[3][2]))
    # 01
    L.append("## 01 十階段完成度\n\n| # | 段 | 階段 | 狀態 |\n|---|---|---|---|\n" + "".join(f"| {s['no']} | {s['seg']} | {s['name']} | {STATUS_TXT.get(s['status'], s['status'])} |\n" for s in stages) + "\n")
    # 02
    L.append("## 02 ①～③：從競品到機率規格\n\n")
    for no in ("①", "②", "③"):
        c = so.get(no, {})
        if st[no]["status"].startswith("n/a"):
            continue
        L.append(f"### {no} {st[no]['name']}（{STATUS_TXT.get(st[no]['status'], st[no]['status'])}）\n\n{c.get('desc', '')}\n\n" + "".join(f"- {o}\n" for o in c.get("out", [])) + f"\n`data/slot/{slug}/{c.get('dir', '')}`\n\n")
    L.append(hblock("s1-3", human, HUMAN_KEYS[4][2]))
    # 03
    L.append("## 03 ④～⑥：快測、報告、逐局對帳\n\n")
    if qt:
        L.append(f"### ④ 快測：{int(qt['spins'] or 0):,} 局" + (f"，三向 verdict {qt['verdict']}" if qt.get("verdict") else "") + "\n\n")
        if qt["feel"]:
            L.append("| 玩法 | 體感區間 | 實測 | 判定 |\n|---|---|---|---|\n" + "".join(
                f"| {c['id'].split(':', 1)[1]} | {one_in(c['band'][1])}～{one_in(c['band'][0])} | 1/{c.get('freq') or 0:,.0f} | {'✅' if c.get('status') == 'PASS' else '❌'} |\n" for c in qt["feel"] if c.get("band")))
            L.append(f"| **總 RTP** | {pct(qt.get('target'), 1)} ±{(qt.get('tol') or 0) * 100:.1f}% | **{pct(qt['total'])}** | {'✅' if qt.get('rtp_pass') else '❌'} |\n\n")
        elif qt["feats"]:
            L.append("| 玩法 | 多久來一次 | 平均倍數 | 佔 RTP |\n|---|---|---|---|\n" + "".join(f"| {k} | 每 {v['freq']:,.1f} 轉 | {v.get('multi') or 0:,.2f}× | {(v.get('rtp') or 0):.2%} |\n" for k, v in qt["feats"]) + "\n")
        if qt.get("ci"):
            L.append(f"95% 信賴區間 {pct(qt['ci'][0])}～{pct(qt['ci'][1])}" + (f"；主遊戲 {pct(qt['main'])}＋特色遊戲 {pct(qt['special'])}" if qt.get("main") and qt.get("special") else "") + "。\n\n")
    lay = so.get("⑤", {}).get("layout")
    L.append(f"### ⑤ 機率報告\n\n快測結果回填機率規格書（prob-spec §2）" + (f"；rtp-report verdict {qt['verdict']}" if qt and qt.get("verdict") else "") + (f"；佈局守門 ps_layout {lay}" if lay else "") + "。\n\n")
    if par:
        L.append(f"### ⑥ 可視化驗證：逐局對帳 {par['spins']:,} 局、不一致 {par['mismatch']}\n\n| 對帳 | 設定檔 | 局數 | 特色局 | 不一致 |\n|---|---|---|---|---|\n" + "".join(
            f"| {r['kind'] or '—'} seed {r['seed']} | {r['odds'] or '—'} | {r['rounds']:,} | {r['features'] if r['features'] is not None else '—'} | {r['mismatch']} |\n" for r in par["runs"]) + f"\n來源 `{par['source']}`。\n\n")
    L.append(hblock("s4-6", human, HUMAN_KEYS[5][2]))
    # 04
    L.append("## 04 ⑦⑧：試玩版與 Game Server\n\n")
    if not st["⑦"]["status"].startswith("n/a"):
        b7 = []
        if so["⑦"].get("play_mb"):
            b7.append(f"單檔 {so['⑦']['play_mb']} MB，雙擊即玩（`review/play.html`）")
        if sm:
            b7.append(f"真瀏覽器冒煙 {sm['n_ok']}/{sm['n']}" + (f"（FPS {sm['fps']}）" if sm.get("fps") else "") + f"；情境 {len(sm['scenes'])} 個")
        L.append(f"### ⑦ 遊戲試玩版（{STATUS_TXT.get(st['⑦']['status'], st['⑦']['status'])}）\n\n" + ("".join(f"- {x}\n" for x in b7) or "- （尚無驗收紀錄）\n") + "\n")
        b8 = [x for x in ("Server 原始碼 `game/go-server/`" if so["⑧"].get("server") else "", "工程交付單 `game/handoff.md`（設定檔 sha、rtp-report sha、K 卡 → Go 映射）" if so["⑧"].get("handoff") else "") if x]
        L.append(f"### ⑧ Game Server（{STATUS_TXT.get(st['⑧']['status'], st['⑧']['status'])}）\n\n" + ("".join(f"- {x}\n" for x in b8) or "- （尚無）\n") + "\n")
    L.append(hblock("s7-8", human, HUMAN_KEYS[6][2]))
    # 05
    L.append("## 05 ⑨ 送審拍板與 ⑩ 上線成效\n\n")
    if dec:
        L.append(f"### ⑨ 送審拍板（{STATUS_TXT.get(st['⑨']['status'], st['⑨']['status'])}）\n\n| # | 待拍板事項 | 建議 | 狀態 |\n|---|---|---|---|\n" + "".join(
            f"| {d['id']} | {d['item']} | {d['suggest'] or '—'} | {dec_state(d)} |\n" for d in dec) + "\n")
    if perf:
        L.append(f"### ⑩ 上線成效\n\n基準：{perf[-1].get('bench') or '—'}。上線日 {perf[-1].get('launch') or '—'}。\n\n")
        L.append("| 問題 | " + " | ".join(f"D+{p['stage']}" for p in perf) + " |\n|---|" + "---|" * len(perf) + "\n")
        for k in QNAME:
            L.append(f"| {QNAME[k]} | " + " | ".join(LIGHT.get(p["lights"].get(k, "na"), "—") for p in perf) + " |\n")
        L.append("\n報告：" + "、".join(f"[D+{p['stage']}]({p['html'].name})" for p in perf if p["html"].is_file()) + "\n\n")
        if perf[-1]["next"]:
            L.append("最新檢查點的下一步：\n\n" + "".join(f"- {x}\n" for x in perf[-1]["next"]) + "\n")
    elif not restore:
        L.append("### ⑩ 上線成效（上線後補）\n\n本款尚未上線。上線後以 ark-game-report 產 D+7／D+14／D+30：實際 RTP、觸發率對照設計目標，結論由人確認並回饋手法卡。"
                 "送審時一併交付線上設定檔 sha、目標 RTP 與 σ，⑩ 才能及早判讀。\n\n")
    L.append(hblock("s9-10", human, HUMAN_KEYS[7][2]))
    for key, head, hint in HUMAN_KEYS[8:12]:
        L.append(f"## {head}\n\n" + hblock(key, human, hint))
    # 10
    nxt = [(f"⑨ {d['id']}", f"{d['item']}（建議：{d['suggest'] or '—'}）") for d in pend]
    if not perf and not restore:
        nxt.append(("⑩ 上線成效", "上線後產 D+7／D+14／D+30；送審包補交線上設定檔 sha、目標 RTP、σ"))
    nxt += [(f"F-{i}", x["action"]) for i, x in enumerate(findings, 1) if not x["what"].startswith("⑨ 送審拍板")]
    L.append("## 10 結案後還要決定的事\n\n" + ("| 項目 | 需要決定或補齊 |\n|---|---|\n" + "".join(f"| {a} | {b} |\n" for a, b in nxt) + "\n" if nxt else "無。\n\n") + hblock("next", human, HUMAN_KEYS[12][2]))
    if filled(human, "notes"):                                    # 0.2.x 舊版人工區
        L.append("## 人工補充\n\n" + hblock("notes", human, ""))
    # Findings／Evidence／Actions／邊界
    L.append("## Findings\n\n")
    L.append(("| ID | 嚴重度 | 現象 | 位置 | 影響 |\n|----|--------|------|------|------|\n" + "".join(f"| F-{i} | {x['sev']} | {x['what']} | `{x['where']}` | {x['impact']} |\n" for i, x in enumerate(findings, 1)) + "\n") if findings else "規則檢查未發現問題。\n\n")
    L.append("## Evidence\n\n" + ("".join(f"### E-{i}（支持 F-{i}）\n\n{x['evidence']}\n\n" for i, x in enumerate(findings, 1)) if findings else "各階段判定依據見「01 十階段完成度」與 sources。\n\n"))
    L.append("## Actions\n\n" + (("| ID | 對應 Finding | 建議 | 負責 |\n|----|--------------|------|------|\n" + "".join(f"| A-{i} | F-{i} | {x['action']} | {x['owner']} |\n" for i, x in enumerate(findings, 1)) + "\n") if findings else "無待辦。\n\n"))
    L.append("## 邊界聲明\n\n"
             f"- 分析基準：{date} 的 `data/slot/{slug}/` 定版家檔案；之後的修改不在結論範圍\n"
             "- 快測 RTP 為模擬結果；上線後實際 RTP 以 ⑩ 成效報告為準\n"
             "- ⑩ 只列本款的成效報告，不引用其他遊戲的數字\n"
             "- verdict 與 Findings 由規則草擬，最終結論由人確認\n")
    view = {"title": title, "lede": lede, "bullets": bullets, "verdict": verdict, "n_done": n_done, "restore": restore}
    return "".join(L), verdict, view


# ───────────────────────── HTML（View 軌，樣板版型） ─────────────────────────

def md2h(txt: str) -> str:
    import markdown  # noqa: PLC0415
    h = markdown.markdown(txt, extensions=["tables", "fenced_code"])
    h = h.replace("<table>", '<div class="table-wrap"><table class="table">').replace("</table>", "</table></div>")
    return re.sub(r'<a href="([^"#][^"]*)"', r'<a target="_blank" rel="noopener" href="\1"', h)


def inline(t: str) -> str:
    t = html.escape(t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", t)


def badge(status: str) -> str:
    cls = {"done": "badge-ok", "review": "badge-warn", "not-started": "badge-danger"}.get(status, "")
    return f'<span class="badge {cls}">{html.escape(STATUS_TXT.get(status, status))}</span>'


def img(p: pathlib.Path, alt: str) -> str:
    mime = {".webp": "image/webp", ".png": "image/png", ".jpg": "image/jpeg"}.get(p.suffix.lower(), "image/png")
    return f'<img loading="lazy" src="data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}" alt="{html.escape(alt)}">'


def links_html(lks) -> str:
    return " ".join(f'<a class="badge badge-accent" target="_blank" rel="noopener" href="{html.escape(h)}">{html.escape(t)} ↗</a>' for t, h in lks)


def section(no: str, sid: str, head: str, body: str) -> str:
    return f'<section class="section" id="{sid}"><div class="section-head"><span class="section-no">{no}</span><h2>{html.escape(head)}</h2></div>{body}</section>'


def to_html(slug, game, date, view, stages, qt, par, dec, perf, sm, so, findings, human, data: pathlib.Path, md_rel: str) -> str:
    e = html.escape
    st = {s["no"]: s for s in stages}
    pend = [d for d in dec if d["pending"]]
    css = CSS_FILE.read_text(encoding="utf-8") if CSS_FILE.is_file() else ""
    H = []
    H.append(f'<header class="report-header"><div class="eyebrow">{e(game)} · 結案報告</div><h1>{e(view["title"])}</h1>'
             f'<p class="lede">{inline(view["lede"])}</p><div class="meta"><span>{e(date)}</span><span>·</span><span>ark-game-report gr_closeout</span>'
             f'<span>·</span><span class="badge badge-accent">內部文件</span><span>·</span><span>verdict {e(view["verdict"])}</span></div></header>')
    extra = md2h(human["summary"]) if filled(human, "summary") else ""
    H.append('<section class="summary"><h2>摘要</h2><ul>' + "".join(f"<li>{inline(b)}</li>" for b in view["bullets"]) + "</ul>" + extra + "</section>")
    # KPI
    k = [("十階段完成", f"{view['n_done']} / 10", " · ".join(x for x in ("⑨ 送審中" if st["⑨"]["status"] == "review" else "", "⑩ 上線後" if st["⑩"]["status"] == "pending-launch" else "") if x) or "—", "")]
    if qt and qt.get("total"):
        k.append((f"總 RTP（目標 {pct(qt.get('target'), 1)} ±{(qt.get('tol') or 0) * 100:.1f}）" if qt.get("target") else "總 RTP", pct(qt["total"]),
                  f"95% CI {pct(qt['ci'][0])}～{pct(qt['ci'][1])}" if qt.get("ci") else f"{int(qt['spins'] or 0):,} 局", "up" if qt.get("rtp_pass") else ""))
    if par:
        k.append(("Go ⇄ JS 逐局不一致", str(par["mismatch"]), f"{par['spins']:,} 局", "up" if not par["mismatch"] else "down"))
    if qt and qt["feel"]:
        ok = sum(1 for c in qt["feel"] if c.get("status") == "PASS")
        k.append(("玩法觸發率落在體感區間", f"{ok} / {len(qt['feel'])}", f"verdict {qt.get('verdict') or '—'}", "up" if ok == len(qt["feel"]) else "down"))
    elif dec:
        k.append(("⑨ 已拍板", f"{len(dec) - len(pend)} / {len(dec)}", "拍板欄", ""))
    H.append('<div class="kpi-grid">' + "".join(f'<div class="kpi"><div class="kpi-label">{e(a)}</div><div class="kpi-value">{e(b)}</div><div class="kpi-delta {c}">{e(d)}</div></div>' for a, b, d, c in k) + "</div>")
    if filled(human, "blueprint"):
        H.append(section("00", "blueprint", "藍圖全貌", md2h(human["blueprint"])))
    H.append('<div class="part"><span>第一部</span>案例結案</div>')
    rows = "".join(f"<tr><td>{s['no']}</td><td>{e(s['seg'])}</td><td>{e(s['name'])}</td><td>{badge(s['status'])}</td></tr>" for s in stages)
    H.append(section("01", "flow", "十階段工作流：這款遊戲走過每一站",
                     f'<div class="table-wrap"><table class="table"><thead><tr><th>#</th><th>段</th><th>階段</th><th>狀態</th></tr></thead><tbody>{rows}</tbody></table></div>'
                     '<div class="callout callout-info"><div class="callout-title">兩個設計重點</div><p>⑥ 給機器驗數學、⑦ 給人玩體驗，上線前就能親手玩到；⑨ 送審把 ①～⑧ 成品組成一本拍板書，主管逐章放行後才上線，⑩ 再用線上數據回頭對帳設計目標。</p></div>'))
    # 02
    cards = ""
    for no in ("①", "②", "③"):
        if st[no]["status"].startswith("n/a"):
            continue
        c = so.get(no, {})
        cards += (f'<div class="stage"><div class="stage-txt"><div class="stage-eyebrow">{e(st[no]["seg"])} · 階段 {no} {badge(st[no]["status"])}</div><h3>{e(st[no]["name"])}</h3>'
                  f'<p>{e(c.get("desc", ""))}</p><ul>' + "".join(f"<li>{e(o)}</li>" for o in c.get("out", [])) + "</ul>"
                  f'<p class="path"><code>data/slot/{e(slug)}/{e(c.get("dir", ""))}</code></p><p>{links_html(c.get("links", []))}</p></div></div>')
    if cards or filled(human, "s1-3"):
        H.append(section("02", "s1-3", "① ～ ③：從競品到機率規格", cards + (md2h(human["s1-3"]) if filled(human, "s1-3") else "")))
    # 03
    b3 = ""
    if qt:
        b3 += f'<h3 class="h3">④ 快測：{int(qt["spins"] or 0):,} 局' + (f'，三向 verdict {e(qt["verdict"])}' if qt.get("verdict") else "") + f'　{links_html(so.get("④", {}).get("links", []))}</h3>'
        if qt["feel"]:
            b3 += ('<div class="table-wrap"><table class="table"><thead><tr><th>玩法</th><th>體感區間</th><th class="num">實測</th><th>判定</th></tr></thead><tbody>'
                   + "".join(f'<tr><td>{e(c["id"].split(":", 1)[1])}</td><td>{one_in(c["band"][1])}～{one_in(c["band"][0])}</td><td class="num">1/{c.get("freq") or 0:,.0f}</td><td>{badge("done") if c.get("status") == "PASS" else "❌"}</td></tr>' for c in qt["feel"] if c.get("band"))
                   + f'<tr><td><strong>總 RTP</strong></td><td>{pct(qt.get("target"), 1)} ±{(qt.get("tol") or 0) * 100:.1f}%</td><td class="num"><strong>{pct(qt["total"])}</strong></td><td>{badge("done") if qt.get("rtp_pass") else "❌"}</td></tr></tbody></table></div>')
        if qt.get("ci"):
            b3 += f'<p class="note">95% 信賴區間 {pct(qt["ci"][0])}～{pct(qt["ci"][1])}' + (f'；主遊戲 {pct(qt["main"])}＋特色遊戲 {pct(qt["special"])}' if qt.get("main") and qt.get("special") else "") + "。</p>"
    lay = so.get("⑤", {}).get("layout")
    b3 += f'<h3 class="h3">⑤ 機率報告</h3><p>快測結果回填機率規格書（prob-spec §2）' + (f'；rtp-report verdict {e(qt["verdict"])}' if qt and qt.get("verdict") else "") + (f"；佈局守門 ps_layout {e(lay)}" if lay else "") + "。</p>"
    if par:
        b3 += (f'<h3 class="h3">⑥ 可視化驗證：兩套引擎、同一份機率，逐局 {par["mismatch"]} 不一致　{links_html(so.get("⑥", {}).get("links", []))}</h3><div class="table-wrap"><table class="table"><thead><tr><th>對帳</th><th>設定檔</th><th class="num">局數</th><th class="num">特色局</th><th class="num">不一致</th></tr></thead><tbody>'
               + "".join(f'<tr><td>{e(r["kind"] or "—")} seed {e(str(r["seed"]))}</td><td>{e(r["odds"] or "—")}</td><td class="num">{r["rounds"]:,}</td><td class="num">{r["features"] if r["features"] is not None else "—"}</td><td class="num">{r["mismatch"]}</td></tr>' for r in par["runs"])
               + f'</tbody></table></div><p class="note">來源 <code>{e(par["source"])}</code>。</p>')
    shots6 = [p for p in (data / "review" / "checks" / n for n in ("proto-00-load.webp", "proto-91-l2.webp")) if p.is_file()]
    if shots6:
        b3 += '<div class="two-col">' + "".join(f'<figure class="fig">{img(p, p.stem)}<figcaption>⑥ 驗證台：{e(p.stem.replace("proto-", ""))}</figcaption></figure>' for p in shots6) + "</div>"
    if filled(human, "s4-6"):
        b3 += md2h(human["s4-6"])
    if qt or par:
        H.append(section("03", "s4-6", "④ ～ ⑥：快測、報告、逐局對帳", b3))
    # 04
    if not st["⑦"]["status"].startswith("n/a"):
        b4 = f'<h3 class="h3">⑦ 遊戲試玩版 {badge(st["⑦"]["status"])}　{links_html(so["⑦"].get("links", []))}</h3><ul class="ul">'
        if so["⑦"].get("play_mb"):
            b4 += f"<li>單檔 {so['⑦']['play_mb']} MB，雙擊即玩</li>"
        if sm:
            b4 += f"<li>真瀏覽器冒煙 {sm['n_ok']}/{sm['n']}" + (f"（FPS {sm['fps']}）" if sm.get("fps") else "") + f"；強制情境 {len(sm['scenes'])} 個</li>"
        b4 += "</ul>"
        if sm and sm["shots"]:
            ends = [n for n in sm["shots"] if n.endswith("-end.webp")]
            pick = [ends[i] for i in sorted({round(j * (len(ends) - 1) / 3) for j in range(4)})] if len(ends) > 4 else ends
            figs = ""
            for n in pick:
                m = re.match(r"stage-(\d+)-end", n)
                sc = sm["scenes"][int(m.group(1)) - 1] if m and 0 < int(m.group(1)) <= len(sm["scenes"]) else {}
                lab = sc.get("scene", {}).get("label") if isinstance(sc.get("scene"), dict) else sc.get("group") or n
                cap = f"{lab}（贏分 {sc['totalWin']:,}）" if sc.get("totalWin") else str(lab)
                p = data / "review" / "checks" / n
                if p.is_file():
                    figs += f'<figure class="fig">{img(p, cap)}<figcaption>{e(cap)}</figcaption></figure>'
            b4 += f'<div class="shots">{figs}</div>' if figs else ""
        b4 += f'<h3 class="h3">⑧ Game Server {badge(st["⑧"]["status"])}　{links_html(so["⑧"].get("links", []))}</h3><ul class="ul">'
        b4 += ("<li>Server 原始碼 <code>game/go-server/</code></li>" if so["⑧"].get("server") else "") + ("<li>工程交付單 <code>game/handoff.md</code>（設定檔 sha、rtp-report sha、K 卡 → Go 映射）</li>" if so["⑧"].get("handoff") else "") + "</ul>"
        if filled(human, "s7-8"):
            b4 += md2h(human["s7-8"])
        H.append(section("04", "s7-8", "⑦ ⑧：可玩的試玩版與 Game Server", b4))
    # 05
    b5 = ""
    if dec:
        b5 += (f'<h3 class="h3">⑨ 送審拍板 {badge(st["⑨"]["status"])}　{links_html(so["⑨"].get("links", []))}</h3><div class="table-wrap"><table class="table"><thead><tr><th>#</th><th>待拍板事項</th><th>建議</th><th>狀態</th></tr></thead><tbody>'
               + "".join(f'<tr><td>{e(d["id"])}</td><td>{e(d["item"])}</td><td>{e(d["suggest"] or "—")}</td><td>{badge("review") if d["pending"] else badge("done")}</td></tr>' for d in dec) + "</tbody></table></div>")
    if perf:
        b5 += f'<h3 class="h3">⑩ 上線成效</h3><p class="note">基準：{e(perf[-1].get("bench") or "—")}；上線日 {e(perf[-1].get("launch") or "—")}。</p>'
        b5 += ('<div class="table-wrap"><table class="table"><thead><tr><th>問題</th>' + "".join(f"<th>D+{p['stage']}</th>" for p in perf) + "</tr></thead><tbody>"
               + "".join(f"<tr><td>{e(QNAME[q])}</td>" + "".join(f'<td>{e(LIGHT.get(p["lights"].get(q, "na"), "—"))}</td>' for p in perf) + "</tr>" for q in QNAME) + "</tbody></table></div>")
        b5 += "<p>" + links_html([(f"D+{p['stage']} 報告", p["html"].name) for p in perf if p["html"].is_file()]) + "</p>"
        if perf[-1]["next"]:
            b5 += '<div class="callout callout-warning"><div class="callout-title">最新檢查點的下一步</div><ul>' + "".join(f"<li>{e(x)}</li>" for x in perf[-1]["next"]) + "</ul></div>"
    elif not view["restore"]:
        b5 += ('<div class="callout callout-info"><div class="callout-title">⑩ 上線成效（上線後補）</div><p>本款尚未上線。上線後以 ark-game-report 產 D+7／D+14／D+30：實際 RTP、觸發率對照設計目標，結論由人確認並回饋手法卡。'
               "送審時一併交付線上設定檔 sha、目標 RTP 與 σ，⑩ 才能及早判讀。</p></div>")
    if filled(human, "s9-10"):
        b5 += md2h(human["s9-10"])
    H.append(section("05", "s9", "⑨ 送審拍板（上線前）與 ⑩ 上線成效", b5))
    first2 = True
    for (key, head, _), (no, sid) in zip(HUMAN_KEYS[8:12], (("06", "infra"), ("07", "ground"), ("08", "timeline"), ("09", "adopt"))):
        if filled(human, key):
            if first2 and key in ("infra", "ground"):
                H.append('<div class="part"><span>第二部</span>技術亮點</div>')
                first2 = False
            H.append(section(no, sid, head.split(" ", 1)[1], md2h(human[key])))
    # 10
    nxt = [(f"⑨ {d['id']}", f"{d['item']}（建議：{d['suggest'] or '—'}）") for d in pend]
    if not perf and not view["restore"]:
        nxt.append(("⑩ 上線成效", "上線後產 D+7／D+14／D+30；送審包補交線上設定檔 sha、目標 RTP、σ"))
    nxt += [(f"F-{i}", x["action"]) for i, x in enumerate(findings, 1) if not x["what"].startswith("⑨ 送審拍板")]
    b10 = ('<div class="table-wrap"><table class="table"><thead><tr><th>項目</th><th>需要決定或補齊</th></tr></thead><tbody>' + "".join(f"<tr><td>{e(a)}</td><td>{e(b)}</td></tr>" for a, b in nxt) + "</tbody></table></div>") if nxt else "<p>無。</p>"
    if filled(human, "next"):
        b10 += md2h(human["next"])
    H.append(section("10", "next", "結案後還要決定的事", b10))
    # Findings（契約）
    if findings:
        H.append(section("F", "findings", "發現與行動（規則判定）", '<div class="table-wrap"><table class="table"><thead><tr><th>ID</th><th>嚴重度</th><th>現象</th><th>行動</th><th>負責</th></tr></thead><tbody>'
                         + "".join(f'<tr><td>F-{i}</td><td><span class="badge {"badge-danger" if x["sev"] in ("P0", "P1") else "badge-warn"}">{x["sev"]}</span></td><td>{e(x["what"])}</td><td>{e(x["action"])}</td><td>{e(x["owner"])}</td></tr>' for i, x in enumerate(findings, 1)) + "</tbody></table></div>"))
    if filled(human, "notes"):
        H.append(section("＋", "notes", "人工補充", md2h(human["notes"])))
    H.append(f'<footer class="report-footer">{e(game)} 結案報告 · 產出於 {e(date)} · ark-game-report gr_closeout · 內部文件 · Content 軌：<code>{e(md_rel)}</code> · 邊界：⑩ 只列本款成效，不引用其他遊戲數字</footer>')
    return (f'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{e(game)} 結案報告</title><style>{css}</style></head><body><div class=\"page\">{''.join(H)}</div></body></html>\n")


def read_human(md_p: pathlib.Path) -> dict:
    if not md_p.is_file():
        return {}
    txt = md_p.read_text(encoding="utf-8")
    out = {}
    for k, v in re.findall(r"<!-- human:([\w-]+) -->\n(.*?)<!-- /human -->", txt, re.S):
        if v.strip() and not v.strip().startswith("（人工填寫"):
            out[k] = v.strip() + "\n"
    return out


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
    human = read_human(out)
    game = game_name(data, a.slug)
    dec = decisions(data)
    stages, qt, par, sm, so = stage_rows(data, dec), quicktest(data), parity(data), smoke(data), stage_outputs(data)
    perf = perf_reports(data, a.slug)
    findings = rules(stages, qt, dec, perf, par)
    md, verdict, view = compose(a.slug, game, a.date, stages, qt, par, dec, perf, sm, so, findings, human)
    out.write_text(md, encoding="utf-8")
    hp = out.with_suffix(".html")
    try:
        md_rel = out.resolve().relative_to(repo).as_posix()
    except ValueError:
        md_rel = out.name
    hp.write_text(to_html(a.slug, game, a.date, view, stages, qt, par, dec, perf, sm, so, findings, human, data, md_rel), encoding="utf-8")
    lint = pair = None
    if not a.no_lint and (MD_REPORT / "report_lint.py").is_file():
        r = subprocess.run([sys.executable, "-X", "utf8", str(MD_REPORT / "report_lint.py"), str(out)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        lint = {"rc": r.returncode, "tail": (r.stdout or r.stderr).strip().splitlines()[-1:]}
        r = subprocess.run([sys.executable, "-X", "utf8", str(MD_REPORT / "report_pair.py"), "stamp", str(out), str(hp)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        pair = {"rc": r.returncode}
    C.emit({"md": str(out), "html": str(hp), "verdict": verdict, "stages_done": sum(1 for s in stages if s["done"]),
            "stages": {s["no"]: s["status"] for s in stages}, "human_filled": sorted(k for k in human if filled(human, k)),
            "findings": [f"{x['sev']} {x['what']}" for x in findings], "perf_reports": [f"D+{p['stage']}" for p in perf],
            "decisions": f"{sum(1 for d in dec if not d['pending'])}/{len(dec)}", "report_lint": lint, "report_pair": pair}, {"stage": "closeout"})
    if lint and lint["rc"] != 0:
        sys.exit(3)


if __name__ == "__main__":
    main()
