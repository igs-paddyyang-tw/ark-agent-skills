"""aiqa playtest 報告：run 目錄（session.json + events.jsonl + narrative.md + shots/）→ 單檔 HTML + summary.json。

版面沿用「金猴爺 AI 試玩筆記 / 新手體驗報告」：摘要 KPI → 基本測試結果 → 發現的問題（依嚴重度）→ 自我探索 →
Agent 寫的敘事段（流程 / 規則 / 功能）→ 數據總覽（時間、點擊、對帳、彈窗、遊戲）→ 優化建議 → 做法與限制 → 待辦。
自動段只從事件算，不憑空寫；敘事段只來自 narrative.md。圖片縮成 JPEG 內嵌，單檔可直接轉寄。
"""
from __future__ import annotations

import base64
import html
import io
import json
import pathlib
import re
from collections import Counter, OrderedDict

import aiqa_common as C

E = html.escape
SEV_ORDER = {"高": 0, "中": 1, "低": 2}
VERDICT_TAG = {"PASS": ("good", "通過"), "FAIL": ("bad", "不通過"), "FLAKY": ("mid", "不穩定"), "NEEDS_HUMAN": ("mid", "需人工"),
               "BLOCK": ("na", "無法執行"), "NA": ("na", "不適用"), None: ("na", "未執行")}
SEV_TAG = {"高": "bad", "中": "mid", "低": "na"}
EXPLORE_TAG = {"issue": ("bad", "找到問題"), "ok": ("good", "正常"), "inconclusive": ("mid", "無法定論"),
               "skipped": ("na", "略過"), "planned": ("na", "未完成")}
POPUP_TAG = {"free": ("free", "免費"), "paid": ("paid", "付費"), "info": ("note", "資訊"), "external": ("note", "對外")}
HEURISTICS = {
    "E1": "規則頁 vs 實際", "E2": "對帳", "E3": "每顆按鈕都有回應", "E4": "彈窗分類與密度", "E5": "跨畫面數字一致",
    "E6": "預設值與勾選", "E7": "返回鍵 / 離開", "E8": "穩定性 / 閃退", "E9": "網路與錯誤碼", "E10": "新手引導鎖定",
    "E11": "外部跳轉", "E12": "命名 / 語系 / 圖示一致", "E13": "自動續行陷阱", "E14": "門檻與表演", "E15": "貨幣不足與解鎖提示",
    "E16": "清單探索重點",
}
NARR_IDS = {"流程": "flow", "規則": "rules", "玩法": "rules", "功能": "features", "大廳": "lobby", "做法": "method", "限制": "method", "待辦": "next"}

CSS = """
:root{--bg:#f6f5f2;--card:#fff;--ink:#1d1d1f;--muted:#5d5d63;--line:#e3e1dc;--accent:#b8322a;--accent-soft:#f6e3e1;--ok:#1f7a4d;--ok-soft:#e1f2e8;--warn:#9a6200;--warn-soft:#fbefd9;--na-soft:#ecebe7}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#141416;--card:#1e1e22;--ink:#ececf0;--muted:#a3a3ad;--line:#2f2f36;--accent:#ff7b6e;--accent-soft:#3a2220;--ok:#6fd39d;--ok-soft:#183126;--warn:#f2bb5b;--warn-soft:#352a14;--na-soft:#2a2a30}}
:root[data-theme="dark"]{--bg:#141416;--card:#1e1e22;--ink:#ececf0;--muted:#a3a3ad;--line:#2f2f36;--accent:#ff7b6e;--accent-soft:#3a2220;--ok:#6fd39d;--ok-soft:#183126;--warn:#f2bb5b;--warn-soft:#352a14;--na-soft:#2a2a30}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.7 -apple-system,"PingFang TC","Noto Sans TC","Microsoft JhengHei",sans-serif}
main{max-width:1000px;margin:0 auto;padding:32px 16px 80px}
h1{font-size:30px;line-height:1.3;margin:0 0 6px}
h2{font-size:22px;margin:48px 0 12px;padding-top:8px;border-top:2px solid var(--line)}
h3{font-size:18px;margin:24px 0 8px}
p{margin:8px 0}.sub{color:var(--muted);margin:0 0 20px}
nav{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0 8px}
nav a{font-size:14px;padding:4px 10px;border:1px solid var(--line);border-radius:999px;color:var(--ink);text-decoration:none;background:var(--card)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:12px 0}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:16px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}
.kpi b{display:block;font-size:24px;line-height:1.2}.kpi span{color:var(--muted);font-size:14px}
table{width:100%;border-collapse:collapse;font-size:15px}
th,td{border-bottom:1px solid var(--line);padding:8px 6px;text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:14px;white-space:nowrap}
.tbl{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:4px 10px;margin:12px 0}
.tag{display:inline-block;font-size:13px;padding:1px 8px;border-radius:999px;white-space:nowrap}
.good,.free{background:var(--ok-soft);color:var(--ok)}.bad,.paid{background:var(--accent-soft);color:var(--accent)}
.mid,.note{background:var(--warn-soft);color:var(--warn)}.na{background:var(--na-soft);color:var(--muted)}
.flow{list-style:none;padding:0;margin:12px 0;counter-reset:s}
.flow li{counter-increment:s;position:relative;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px 12px 52px;margin:0 0 10px}
.flow li::before{content:counter(s);position:absolute;left:14px;top:12px;width:26px;height:26px;border-radius:50%;background:var(--accent);color:#fff;font-weight:700;font-size:14px;display:flex;align-items:center;justify-content:center}
.flow li b{display:block}
.gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px;margin:12px 0}
.gallery.tall{grid-template-columns:repeat(auto-fill,minmax(180px,1fr))}
figure{margin:0;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}
figure img{display:block;width:100%;height:auto}
figcaption{font-size:13.5px;color:var(--muted);padding:8px 10px;line-height:1.5}
.warn-box{border-left:4px solid var(--warn);background:var(--warn-soft);border-radius:8px;padding:12px 14px;margin:12px 0}
.warn-box b{color:var(--warn)}
.bad-box{border-left:4px solid var(--accent);background:var(--accent-soft);border-radius:8px;padding:12px 14px;margin:12px 0}
.bad-box b{color:var(--accent)}
code{font-size:13.5px;background:var(--line);padding:1px 5px;border-radius:4px;word-break:break-all}
ul,ol{padding-left:22px;margin:8px 0}
details{margin:24px 0;color:var(--muted);font-size:14px}
.muted{color:var(--muted)}
.ids{font-size:13px;color:var(--muted);white-space:nowrap}
@media (max-width:640px){.tbl table{min-width:620px}h1{font-size:24px}}
"""


# ----------------------------------------------------------------- 圖片


class Images:
    def __init__(self, run, width: int, limit: int):
        self.run, self.width, self.limit = run, width, limit
        self.cache: dict[str, tuple[str, bool]] = {}
        self.skipped = 0
        self.shots = {}
        for e in run.events("shot"):
            self.shots[e["id"]] = {**self.shots.get(e["id"], {}), **e}

    def resolve(self, ref: str) -> pathlib.Path | None:
        ref = ref.strip()
        if ref in self.shots:
            return self.run.path / self.shots[ref]["file"]
        p = pathlib.Path(ref)
        p = p if p.is_absolute() else self.run.path / p
        return p if p.exists() else None

    def caption(self, ref: str) -> str:
        return (self.shots.get(ref) or {}).get("caption") or ""

    def data(self, ref: str) -> tuple[str, bool] | None:
        p = self.resolve(ref)
        if p is None or not p.exists():
            return None
        key = str(p)
        if key in self.cache:
            return self.cache[key]
        if len(self.cache) >= self.limit:
            self.skipped += 1
            return None
        try:
            from PIL import Image
            with Image.open(p) as im:
                im = im.convert("RGB")
                w, h = im.size
                tall = h > w
                tw = min(self.width if not tall else int(self.width * 0.6), w)
                if w > tw:
                    im = im.resize((tw, max(1, int(h * tw / w))), Image.LANCZOS)
                buf = io.BytesIO()
                im.save(buf, "JPEG", quality=72, optimize=True)
            uri = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
        except Exception:  # noqa: BLE001
            return None
        self.cache[key] = (uri, tall)
        return self.cache[key]

    def gallery(self, pairs: list[tuple[str, str]]) -> str:
        figs, talls = [], 0
        for ref, cap in pairs:
            d = self.data(ref)
            if not d:
                continue
            uri, tall = d
            talls += tall
            figs.append(f'<figure><img src="{uri}" alt=""><figcaption>{inline(cap or self.caption(ref))}</figcaption></figure>')
        if not figs:
            return ""
        cls = "gallery tall" if talls * 2 > len(figs) else "gallery"
        return f'<div class="{cls}">' + "".join(figs) + "</div>"


# ----------------------------------------------------------------- 迷你 markdown


def inline(s: str) -> str:
    s = E(str(s or ""))
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\{(高|中|低)\}", lambda m: f'<span class="tag {SEV_TAG[m.group(1)]}">{m.group(1)}</span>', s)
    return s


IMG_LINE = re.compile(r"^\s*!\[([^\]]*)\]\(([^)]+)\)\s*$")


def md(text: str, imgs: Images, missing: list[str]) -> str:
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    out, lines, i = [], text.splitlines(), 0
    para: list[str] = []

    def flush():
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>"); para.clear()

    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            flush(); i += 1; continue
        h = re.match(r"^(#{3,6})\s+(.*)", ln)
        if h:
            flush(); out.append(f"<h3>{inline(h.group(2))}</h3>"); i += 1; continue
        if ln.strip().startswith("|"):
            flush(); rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            if rows:
                th = "".join(f"<th>{inline(c)}</th>" for c in rows[0])
                trs = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows[1:])
                out.append(f'<div class="tbl"><table><tr>{th}</tr>{trs}</table></div>')
            continue
        if IMG_LINE.match(ln):
            flush(); pairs = []
            while i < len(lines) and (IMG_LINE.match(lines[i]) or not lines[i].strip()):
                m = IMG_LINE.match(lines[i])
                if m:
                    if imgs.resolve(m.group(2)) is None:
                        missing.append(m.group(2))
                    pairs.append((m.group(2), m.group(1)))
                i += 1
            out.append(imgs.gallery(pairs)); continue
        if re.match(r"^\s*\d+[.)]\s+", ln):
            flush(); lis, flow = [], True
            while i < len(lines) and re.match(r"^\s*\d+[.)]\s+", lines[i]):
                body = re.sub(r"^\s*\d+[.)]\s+", "", lines[i]); i += 1
                while i < len(lines) and lines[i].startswith("   ") and lines[i].strip() and not re.match(r"^\s*\d+[.)]\s+", lines[i]):
                    body += " " + lines[i].strip(); i += 1
                m = re.match(r"^\*\*(.+?)\*\*\s*(.*)", body)
                if m:
                    lis.append(f"<li><b>{inline(m.group(1))}</b>{inline(m.group(2))}</li>")
                else:
                    flow = False; lis.append(f"<li>{inline(body)}</li>")
            out.append(('<ol class="flow">' if flow else "<ol>") + "".join(lis) + "</ol>"); continue
        if re.match(r"^\s*[-*+]\s+", ln):
            flush(); lis = []
            while i < len(lines) and re.match(r"^\s*[-*+]\s+", lines[i]):
                lis.append("<li>" + inline(re.sub(r"^\s*[-*+]\s+(\[[ xX]\]\s+)?", "", lines[i])) + "</li>"); i += 1
            out.append("<ul>" + "".join(lis) + "</ul>"); continue
        if ln.startswith(">"):
            flush(); q = []
            while i < len(lines) and lines[i].startswith(">"):
                q.append(lines[i].lstrip("> ").rstrip()); i += 1
            out.append('<div class="warn-box">' + inline(" ".join(q)) + "</div>"); continue
        para.append(ln.strip()); i += 1
    flush()
    return "\n".join(x for x in out if x)


def split_narrative(text: str) -> "OrderedDict[str, str]":
    secs: "OrderedDict[str, str]" = OrderedDict()
    cur = None
    for ln in text.splitlines():
        m = re.match(r"^##\s+(.*?)\s*$", ln)
        if m:
            cur = m.group(1); secs[cur] = ""; continue
        if cur is not None:
            secs[cur] += ln + "\n"
    return OrderedDict((k, v) for k, v in secs.items() if re.sub(r"<!--.*?-->", "", v, flags=re.S).strip())


# ----------------------------------------------------------------- 資料彙整


def _num(v) -> str:
    if v is None or v == "":
        return "—"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return E(str(v))
    return f"{f:,.0f}" if abs(f - round(f)) < 1e-9 else f"{f:,.2f}"


def _signed(v) -> str:
    return ("+" if float(v) > 0 else "") + _num(v)


def _hm(iso: str | None) -> str:
    return iso[5:16].replace("T", " ").replace("-", "/") if iso else "—"


def tag(cls: str, text: str) -> str:
    return f'<span class="tag {cls}">{E(text)}</span>'


def table(head: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return ""
    th = "".join(f"<th>{h}</th>" for h in head)
    trs = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tbl"><table><tr>{th}</tr>{trs}</table></div>'


def collect(run) -> dict:
    from aiqa_playtest import merged, active_minutes, CATEGORIES
    cl = json.loads((run.path / "checklist.json").read_text(encoding="utf-8"))
    items = merged(run, "item")
    findings = sorted(merged(run, "finding").values(), key=lambda f: (SEV_ORDER.get(f.get("severity"), 9), f["id"]))
    explores = list(merged(run, "explore").values())
    taps = merged(run, "tap")
    ledger = run.events("ledger")
    popups: "OrderedDict[str, dict]" = OrderedDict()
    for p in run.events("popup"):
        d = popups.setdefault(p["name"], {"name": p["name"], "kind": p.get("ptype"), "count": 0, "actions": [], "price": p.get("price"), "shots": []})
        d["count"] += 1
        if p.get("action") and p["action"] not in d["actions"]:
            d["actions"].append(p["action"])
        d["shots"] += p.get("shots") or []
    games: "OrderedDict[str, dict]" = OrderedDict()
    for e in run.events("game"):
        g = games.setdefault(e["name"], {"name": e["name"], "type": e.get("gtype"), "spins": 0, "features": [], "rules_read": False, "notes": []})
        g["rules_read"] |= bool(e.get("rules_read"))
        if e.get("feature"):
            g["features"].append((e["feature"], e.get("win")))
        if e.get("note"):
            g["notes"].append(e["note"])
    for e in run.events("spin"):
        if e.get("machine"):
            g = games.setdefault(e["machine"], {"name": e["machine"], "type": "slot", "spins": 0, "features": [], "rules_read": False, "notes": []})
            g["spins"] += e.get("n", 0)
    segs, open_seg = [], None
    for e in run.events("segment"):
        if e.get("action") == "start":
            open_seg = {"name": e.get("name") or f"第 {len(segs) + 1} 段", "start": e["ts"], "end": None, "note": e.get("note")}
            segs.append(open_seg)
        elif open_seg:
            open_seg["end"] = e["ts"]; open_seg = None
    evs = run.events()
    last_ts = evs[-1]["ts"] if evs else run.session["started"]
    outcomes = Counter(t.get("outcome", "ok") for t in taps.values())
    return {"cl": cl, "items": items, "findings": findings, "explores": explores, "taps": taps, "outcomes": outcomes,
            "ledger": ledger, "popups": popups, "games": games, "segments": segs, "last_ts": last_ts,
            "spins": int(sum(e.get("n", 0) for e in run.events("spin"))), "shots_n": len(run.events("shot")),
            "crash": run.events("crash_suspect") + [e for e in run.events("logcat") if e.get("crash")],
            "active_min": active_minutes(run), "categories": CATEGORIES}


def lint(run, d: dict, narr: "OrderedDict[str, str]", missing_imgs: list[str]) -> dict:
    errors, warnings = [], []
    for it in d["cl"]["items"]:
        r = d["items"].get(it["id"])
        if not r:
            errors.append(f"{it['id']} 未執行（做不到請判 BLOCK 並寫 --block-reason）")
        elif r["verdict"] in ("PASS", "FAIL") and not r.get("shots"):
            errors.append(f"{it['id']} {r['verdict']} 沒有證據截圖")
        elif r["verdict"] == "FAIL" and not r.get("finding") and not any(f.get("item") == it["id"] for f in d["findings"]):
            warnings.append(f"{it['id']} FAIL 但沒有對應的 finding（優化建議會缺這一條）")
        elif r["verdict"] == "BLOCK" and not (r.get("block_reason") or r.get("note")):
            errors.append(f"{it['id']} BLOCK 沒寫原因")
    for f in d["findings"]:
        if not f.get("shots"):
            errors.append(f"{f['id']} 發現沒有證據截圖")
        if not f.get("suggest"):
            warnings.append(f"{f['id']} 沒有建議（--suggest）")
        if not f.get("category"):
            warnings.append(f"{f['id']} 沒有分類（--category）")
    if run.session.get("explore", True) and not d["explores"]:
        errors.append("沒有做自我探索（explore 為 0 項）")
    for x in d["explores"]:
        if x.get("status") == "planned":
            errors.append(f"{x['id']} 探索還沒回填結果")
        if x.get("status") == "issue" and not x.get("finding"):
            errors.append(f"{x['id']} 標為找到問題但沒連到 finding")
    for l in d["ledger"]:
        if not l.get("match") and not l.get("note") and not any((f.get("detail") or "").find(l["id"]) >= 0 for f in d["findings"]):
            warnings.append(f"{l['id']} 對帳不符且沒有說明（--note 或在 finding 內提到 {l['id']}）")
    if d["crash"] and not any(f.get("category") in ("stability", "穩定性") for f in d["findings"]):
        warnings.append("有閃退 / App 離開前景的紀錄，但沒有穩定性 finding")
    if not any(k.startswith("摘要") or k.lower().startswith("summary") for k in narr):
        warnings.append("narrative.md 的「摘要」沒寫（報告會用自動摘要）")
    for m in missing_imgs:
        errors.append(f"narrative 引用的圖不存在：{m}")
    return {"errors": errors, "warnings": warnings}


# ----------------------------------------------------------------- 渲染


def build(run, out: pathlib.Path | None = None, img_width: int = 720, max_images: int = 80) -> dict:
    d = collect(run)
    s = run.session
    imgs = Images(run, img_width, max_images)
    narr_path = run.path / "narrative.md"
    narr = split_narrative(narr_path.read_text(encoding="utf-8")) if narr_path.exists() else OrderedDict()
    missing: list[str] = []
    cl_items = d["cl"]["items"]
    vcount = Counter(d["items"].get(i["id"], {}).get("verdict") for i in cl_items)
    sev = Counter(f.get("severity") for f in d["findings"])
    ex_issue = sum(1 for x in d["explores"] if x.get("status") == "issue")
    taps_n = len(d["taps"])
    valid = d["outcomes"].get("ok", 0) + d["outcomes"].get("noresp", 0)
    rate = f"{valid * 100 // taps_n}%" if taps_n else "—"
    led_ok = sum(1 for l in d["ledger"] if l.get("match"))
    paid = [p for p in d["popups"].values() if p["kind"] == "paid"]
    features = sum(len(g["features"]) for g in d["games"].values())
    finished = s.get("finished") or d["last_ts"]

    nav, body = [], []

    def section(sid: str, title: str, content: str):
        if content.strip():
            nav.append(f'<a href="#{sid}">{E(re.sub(r"（.*?）", "", title))}</a>')
            body.append(f'<h2 id="{sid}">{E(title)}</h2>\n{content}')

    # 摘要
    kpis = [
        (f"{vcount.get('PASS', 0)} / {len(cl_items)}", f"基本測試通過（不通過 {vcount.get('FAIL', 0)}、無法執行 {vcount.get('BLOCK', 0)}、未執行 {vcount.get(None, 0)}）"),
        (f"{len(d['findings'])} 項", f"發現的問題（高 {sev.get('高', 0)}／中 {sev.get('中', 0)}／低 {sev.get('低', 0)}）"),
        (f"{len(d['explores'])} 項", f"自我探索測試（{ex_issue} 項找到問題）"),
        (f"約 {d['active_min']:.0f} 分", f"實際操作時間（{_hm(s['started'])} – {_hm(finished)}）"),
        (f"{taps_n:,} 次", f"點擊（有效 {rate}）＋ 連續旋轉 {d['spins']:,} 把"),
    ]
    if d["games"]:
        kpis.append((f"{len(d['games'])} 款", f"玩過的遊戲（觸發特色玩法 {features} 次）"))
    if d["ledger"]:
        kpis.append((f"{led_ok} / {len(d['ledger'])}", "對帳相符"))
    kpis.append((f"{sum(p['count'] for p in paid)} 次", "看到付費視窗（一律不購買）"))
    kpis.append((f"{d['shots_n']:,} 張", "截圖（證據）"))
    summary_key = next((k for k in narr if k.startswith("摘要") or k.lower().startswith("summary")), None)
    if summary_key:
        summ = md(narr.pop(summary_key), imgs, missing)
    else:
        summ = (f"<p>依清單執行 {len(cl_items)} 項基本測試，另外自我探索 {len(d['explores'])} 項，"
                f"共記錄 {len(d['findings'])} 個問題（高 {sev.get('高', 0)}）。</p>")
    section("summary", "摘要", summ + '<div class="kpis">' + "".join(f'<div class="kpi"><b>{E(a)}</b><span>{E(b)}</span></div>' for a, b in kpis) + "</div>"
            + ('<p class="muted">贏輸數字只是這次的結果，樣本太小，看不出回收率或機率是否正確。</p>' if d["games"] else ""))

    # 基本測試
    groups: "OrderedDict[str, list]" = OrderedDict()
    for it in cl_items:
        groups.setdefault(it.get("group") or "", []).append(it)
    parts, gal = [], []
    for g, its in groups.items():
        rows = []
        for it in its:
            r = d["items"].get(it["id"], {})
            cls, label = VERDICT_TAG.get(r.get("verdict"), VERDICT_TAG[None])
            if r.get("verdict") in ("PASS", "FAIL") and not r.get("shots"):
                label += "（無證據）"
            note = r.get("actual") or r.get("note") or r.get("block_reason") or ""
            if r.get("actual") and r.get("note"):
                note = f"{r['actual']}；{r['note']}"
            links = [x for x in [r.get("finding")] + [f["id"] for f in d["findings"] if f.get("item") == it["id"]] if x]
            rows.append([f'<span class="ids">{E(it["id"])}</span>', inline(it["title"]), inline(it.get("expect") or "—"), tag(cls, label),
                         inline(note) + (f' <span class="ids">→ {E(", ".join(dict.fromkeys(links)))}</span>' if links else ""),
                         f'<span class="ids">{E(", ".join(r.get("shots") or []))}</span>'])
            if r.get("verdict") in ("FAIL", "NEEDS_HUMAN", "FLAKY"):
                gal += [(sid, f"{it['id']} {it['title']}：{imgs.caption(sid)}") for sid in (r.get("shots") or [])[:2]]
        parts.append((f"<h3>{inline(g)}</h3>" if g and len(groups) > 1 else "") + table(["編號", "項目", "預期", "結果", "實際／說明", "證據"], rows))
    feat_items = [(e["id"], f"{e.get('item')}：{e.get('caption')}") for e in imgs.shots.values() if e.get("feature") and e.get("item")]
    section("base", "基本測試結果（清單固定項）", "".join(parts) + imgs.gallery(gal + feat_items))

    # 發現的問題
    if d["findings"]:
        boxes = "".join(f'<div class="bad-box"><b>{E(f["id"])} {inline(f.get("title", ""))}</b> {inline(f.get("detail", ""))}</div>'
                        for f in d["findings"] if f.get("severity") == "高")
        rows = []
        for f in d["findings"]:
            src = f"探索 {f['explore']}" if f.get("explore") else (f"基本 {f['item']}" if f.get("item") else "")
            meta = "；".join(x for x in [f.get("where"), f"重現 {f['repro']}" if f.get("repro") else "", src] if x)
            rows.append([tag(SEV_TAG.get(f.get("severity"), "na"), f.get("severity", "—")) + (" " + tag("note", "需確認") if f.get("confirm") else "")
                         + (" " + tag("na", "設計如此") if f.get("status") == "wontfix" else ""),
                         f'<b>{inline(f.get("title", ""))}</b> <span class="ids">{E(f["id"])}</span>', inline(f.get("detail", "")), inline(meta),
                         f'<span class="ids">{E(", ".join(f.get("shots") or []))}</span>'])
        gal = [(sid, f"{f['id']} {f.get('title', '')}") for f in d["findings"] for sid in (f.get("shots") or [])[:2]]
        section("issues", "發現的問題（依嚴重度）", boxes + table(["嚴重度", "問題", "說明", "位置／來源", "證據"], rows) + imgs.gallery(gal))

    # 自我探索
    if d["explores"]:
        rows = []
        for x in d["explores"]:
            cls, label = EXPLORE_TAG.get(x.get("status"), ("na", x.get("status") or "—"))
            h = x.get("heuristic") or ""
            rows.append([f'<span class="ids">{E(x["id"])}</span>', inline(f"{h} {HEURISTICS.get(h, '')}".strip()) + (f'<br><span class="muted">{inline(x["area"])}</span>' if x.get("area") else ""),
                         inline(x.get("hypothesis", "")), inline(x.get("method", "")), inline(x.get("result", "")),
                         tag(cls, label) + (f' <span class="ids">→ {E(x["finding"])}</span>' if x.get("finding") else "")])
        intro = ('<p class="muted">清單以外、由 AI 依畫面與探索準則自己提出的假設。每一項都先寫「想驗證什麼」再動手，做完回填結果；'
                 '找到問題的會連到上面的問題清單。</p>')
        gal = [(sid, f"{x['id']}：{imgs.caption(sid)}") for x in d["explores"] for sid in (x.get("shots") or [])[:1]]
        section("explore", "自我探索測試", intro + table(["編號", "方向", "想驗證什麼", "做法", "結果", "狀態"], rows) + imgs.gallery(gal))

    # 敘事段（流程 / 規則 / 功能…）
    method_n = next_n = None
    for k in list(narr):
        if "做法" in k or "限制" in k:
            method_n = narr.pop(k)
        elif "待辦" in k:
            next_n = narr.pop(k)
    for n, (k, v) in enumerate(narr.items()):
        sid = next((i for w, i in NARR_IDS.items() if w in k), f"n{n}")
        section(sid if sid not in [x.split('"')[1][1:] for x in nav] else f"n{n}", k, md(v, imgs, missing))
    feat_free = [(e["id"], e.get("caption")) for e in imgs.shots.values() if e.get("feature") and not e.get("item")]
    if feat_free:
        section("gallery", "畫面紀錄", imgs.gallery(feat_free))

    # 數據總覽
    parts = []
    if d["segments"]:
        parts.append("<h3>時間</h3>" + table(["段落", "開始", "結束", "備註"], [[inline(g["name"]), _hm(g["start"]), _hm(g["end"]), inline(g.get("note") or "")] for g in d["segments"]]))
    oc = d["outcomes"]
    parts.append("<h3>點擊</h3>" + table(["項目", "次數", "說明"], [
        ["全部點擊／滑動／按鍵", f"{taps_n:,}", "每一次都有寫原因（decision-log.md）"],
        ["有效（達到目的）", f"{oc.get('ok', 0):,}", ""],
        ["點了遊戲沒反應", f"{oc.get('noresp', 0):,}", "不是點偏；算有效測試，原因寫在問題清單"],
        ["我點偏", f"{oc.get('miss', 0):,}", "座標偏移／判斷錯誤"],
        ["點太早（動畫未停）", f"{oc.get('early', 0):,}", ""],
        ["連續旋轉（腳本）", f"{d['spins']:,}", "不計入點擊；每 N 把截圖回看"],
    ]))
    if d["ledger"]:
        parts.append("<h3>對帳</h3>" + table(["編號", "項目", "前", "後", "預期變化", "實際變化", "結果"], [
            [f'<span class="ids">{E(l["id"])}</span>', inline(l.get("label", "")) + (f'<br><span class="muted">{inline(l["note"])}</span>' if l.get("note") else ""),
             _num(l["before"]), _num(l["after"]), _signed(l["expect_delta"]), _signed(l["delta"]),
             tag("good", "相符") if l.get("match") else tag("bad", f"差 {_signed(l['diff'])}")] for l in d["ledger"]]))
    if d["popups"]:
        order = {"free": 0, "paid": 1, "info": 2, "external": 3}
        parts.append("<h3>彈窗整理（免費 vs 付費）</h3>" + table(["彈窗", "類型", "次數", "處理"], [
            [inline(p["name"]) + (f' <span class="muted">{E(p["price"])}</span>' if p.get("price") and p["price"] not in p["name"] else ""), tag(*POPUP_TAG.get(p["kind"], ("na", p["kind"] or "—"))),
             str(p["count"]), inline("；".join(p["actions"]))] for p in sorted(d["popups"].values(), key=lambda p: order.get(p["kind"], 9))]))
    if d["games"]:
        parts.append("<h3>玩過的遊戲</h3>" + table(["遊戲", "類型", "規則頁", "旋轉", "特色玩法 / 結果", "備註"], [
            [inline(g["name"]), E(g.get("type") or ""), "已讀" if g["rules_read"] else "—", f"{g['spins']:,}" if g["spins"] else "—",
             inline("；".join(f"{a}" + (f" {_num(w)}" if w else "") for a, w in g["features"]) or "—"), inline("；".join(g["notes"]))]
            for g in d["games"].values()]))
    if d["crash"]:
        parts.append("<h3>閃退 / App 離開前景</h3>" + table(["時間", "位置", "紀錄"], [
            [_hm(c["ts"]), inline(c.get("where") or c.get("label") or ""), f"<code>{E(c.get('logcat') or c.get('file') or '')}</code>"] for c in d["crash"]]))
    section("data", "數據總覽", "".join(parts))

    # 優化建議
    sug = [f for f in d["findings"] if f.get("suggest") and f.get("status") != "wontfix"]
    if sug:
        cats: "OrderedDict[str, list]" = OrderedDict()
        for key in list(d["categories"]) + ["_"]:
            for f in sug:
                c = f.get("category") or "other"
                c = next((k for k, v in d["categories"].items() if v == c), c)
                if (c if c in d["categories"] else "_") == key:
                    cats.setdefault(key, []).append(f)
        parts = ['<p class="muted">每一條都對應實際看過的畫面；「優先度」是 AI 的建議排序，不是正式評估。標「需確認」的，是看不出是刻意設計還是錯誤。</p>']
        for n, (c, fs) in enumerate(cats.items(), 1):
            parts.append(f"<h3>{n}. {E(d['categories'].get(c, '其他'))}</h3>" + table(["優先度", "現況", "建議"], [
                [tag(SEV_TAG.get(f.get("severity"), "na"), f.get("severity", "—")), inline(f.get("title", "")) + (f'<br><span class="muted">{inline(f.get("detail", ""))}</span>' if f.get("detail") else "")
                 + (" " + tag("note", "需確認") if f.get("confirm") else ""), inline(f["suggest"])] for f in fs]))
        section("improve", "優化建議", "".join(parts))

    # 做法與限制
    plat = "、".join(x for x in [s.get("platform"), s.get("device_model") if s.get("device_model") not in ("", "fake") else "",
                              "fake 裝置（演練，不是真機）" if s.get("backend") == "fake" else s.get("device")] if x)
    auto = f"""<div class="card"><ul>
<li><b>做法</b>：用 <code>adb</code>（Android 開發者工具，讓電腦能截圖、點擊裝置）連 {E(plat or '裝置')}。每一步：截圖 → AI 看畫面判斷 → 點擊座標，並寫下原因（決策紀錄）。重複性的旋轉交給小腳本，每隔幾把截圖回看。</li>
<li><b>兩段式</b>：先照清單跑 {len(cl_items)} 項基本測試（固定、可比較），再依探索準則自己找問題（{len(d['explores'])} 項，見「自我探索測試」）。</li>
<li><b>不用訓練</b>：規則都是當場打開遊戲內規則頁讀出來的；判斷靠「看懂畫面」，不是「學會怎麼贏」。</li>
<li><b>能驗證的</b>：畫面看得到的金額、流程、彈窗、規則文字、按鈕反應、閃退（logcat）。<b>不能驗證的</b>：伺服器算得對不對、機率是否正確、沒顯示在畫面上的狀態。</li>
<li><b>安全邊界</b>：沒有儲值／購買／評分／綁定／登出／加好友／送意見；付費視窗一律關閉。</li>
</ul></div>"""
    section("method", "做法與限制", auto + (md(method_n, imgs, missing) if method_n else ""))

    # 待辦
    todo = []
    for it in cl_items:
        r = d["items"].get(it["id"], {})
        if not r:
            todo.append(f"<li>{E(it['id'])} {inline(it['title'])}：<b>未執行</b></li>")
        elif r["verdict"] in ("BLOCK", "NEEDS_HUMAN", "FLAKY"):
            todo.append(f"<li>{E(it['id'])} {inline(it['title'])}：{VERDICT_TAG[r['verdict']][1]}—{inline(r.get('block_reason') or r.get('note') or '')}</li>")
    for f in d["findings"]:
        if f.get("confirm"):
            todo.append(f"<li>確認 {E(f['id'])}「{inline(f.get('title', ''))}」是設計如此還是錯誤</li>")
    for x in d["explores"]:
        if x.get("status") in ("inconclusive", "planned"):
            todo.append(f"<li>{E(x['id'])} 探索沒有定論：{inline(x.get('hypothesis', ''))}</li>")
    section("next", "待辦", (f"<ul>{''.join(todo)}</ul>" if todo else "") + (md(next_n, imgs, missing) if next_n else ""))

    lint_res = lint(run, d, OrderedDict([("摘要", "x")]) if summary_key else OrderedDict(), missing)
    if imgs.skipped:
        lint_res["warnings"].append(f"圖片超過上限 {max_images} 張，{imgs.skipped} 張沒放進報告（--max-images 調整）")
    lint_html = ""
    if lint_res["errors"] or lint_res["warnings"]:
        lint_html = ("<details><summary>報告完整度檢查（" + f"{len(lint_res['errors'])} 錯誤／{len(lint_res['warnings'])} 提醒）</summary><ul>"
                     + "".join(f"<li>錯誤：{E(x)}</li>" for x in lint_res["errors"]) + "".join(f"<li>提醒：{E(x)}</li>" for x in lint_res["warnings"]) + "</ul></details>")

    sub = " · ".join(x for x in [
        f"{_hm(s['started'])} – {_hm(finished)}", E(plat) if plat else "",
        f"{E(s.get('game') or '')} <code>{E(s.get('package') or '')}</code> {E(s.get('app_version') or '')}".strip() if s.get("package") or s.get("game") else "",
        E(s.get("account") or ""), "事前沒有任何訓練，全靠「截圖 → 看畫面判斷 → 點擊」"] if x)
    title = s.get("title") or "AI 試玩測試報告"
    doc = f"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<meta name="generator" content="ark-mobile-adb {C.SKILL_VERSION} aiqa_playtest_report">
<meta name="aiqa-run" content="{E(run.path.name)}"><meta name="aiqa-checklist-sha256" content="{E(s.get('checklist_sha256', ''))}">
<style>{CSS}</style></head>
<body><main>
<h1>{E(title)}</h1>
<p class="sub">{sub}</p>
<nav>{''.join(nav)}</nav>
{chr(10).join(body)}
<p class="sub" style="margin-top:32px">原始資料：<code>{E(s.get('source_dir') or str(run.path))}</code>（decision-log.md、events.jsonl、shots/、logs/）· 清單 <code>checklist.md</code> sha256 {E((s.get('checklist_sha256') or '')[:12])}</p>
{lint_html}
</main></body></html>
"""
    out = out or run.path / "report.html"
    out.write_text(doc, encoding="utf-8")
    summary = {"run": run.path.name, "title": title, "base_total": len(cl_items), "verdicts": {str(k): v for k, v in vcount.items()},
               "findings": [{k: f.get(k) for k in ("id", "severity", "category", "title", "suggest", "confirm", "item", "explore")} for f in d["findings"]],
               "explores": [{k: x.get(k) for k in ("id", "heuristic", "hypothesis", "status", "finding")} for x in d["explores"]],
               "taps": taps_n, "valid_tap_rate": rate, "spins": d["spins"], "ledger": {"total": len(d["ledger"]), "match": led_ok},
               "active_min": d["active_min"], "shots": d["shots_n"], "lint": lint_res}
    C.atomic_write(run.path / "summary.json", json.dumps(summary, ensure_ascii=False, indent=2))
    return {"html": str(out), "bytes": out.stat().st_size, "images": len(imgs.cache), "summary": str(run.path / "summary.json"), "lint": lint_res}
