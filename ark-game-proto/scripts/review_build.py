#!/usr/bin/env python3
"""review_build — 發布拍板包 data/<domain>/<slug>/review/（佈局契約 v3.5 ⑨ 送審拍板；給人拍板、可 demo 的研發產物）。

彙整工作檯 output/<domain>/<slug>/ 的成品進定版家（送審前跑一次，不是每次 build）：
  play.html            ⑦ 試玩版單檔（output/…/game/pixi-client/single/index.html，雙擊可玩）
  gdd-overview.html    ② 素材總覽自足版（output/…/gdd/*.html 外連圖 → ark-html-report html_images 縮圖 WebP 內嵌）
  checks/              ⑥ browser-check.json、⑦ stage-smoke.json ＋ 每種玩法 / 情境的代表截圖（WebP）
  index.html           導覽頁／拍板書：十階段狀態、成品連結＋大小＋sha16、驗收結果與截圖牆
v3.5 不重疊原則：定版家擁有每份文件的 md＋html（publish_docs 在 md 旁產同名 html，帶 content-src 戳記）；
  review/ 只放拍板書、checks/、定版家放不下的自足單檔（play.html、gdd-overview.html），其餘成品用相對連結
  ../<stage>/…，不複製；白名單外的舊檔組包時清掉。要整包傳給人：--export <資料夾>（複製 review/＋被連到的檔）。
  REVIEW.md            送審說明（首次產骨架；之後只更新 <!-- auto --> 區段，人工區保留）
  review-manifest.json 每個檔的來源＋sha16＋大小（ps_layout L-REVIEW 據此判拍板包是否過期）
⑤ prob/prob-spec.html、⑥ proto/index.html 留原位（受 ps_lint／proto_build 綁定），導覽頁用相對連結。

用法：py scripts/review_build.py --slug <slug> [--repo .] [--domain slot] [--quality auto|standard|lite] [--run-checks]
  --run-checks：先跑 tests/browser_check.js（⑥）與 stage/tests/smoke.js --scenes all（⑦）再收集
  --export DIR：另產可帶走的完整拍板包（不得寫進 data/）
exit：0 成功 / 1 超過 5 MB 或含禁止檔 / 2 BAD_INPUT
規格：專案 docs/specs/2026-10-19-review-pack-spec.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import io
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REVIEW_KB = 5120
BAN = (".exe", ".dll", ".bin", ".so", ".mp4", ".mov", ".webm", ".zip", ".7z")
STAGES = [  # (編號, 名稱, 定版家判定檔（任一存在即有）)
    ("①", "競品分析", ["analysis/game-analysis.yaml"]),
    ("②", "遊戲規格書", ["spec/game-spec.v1.md", "spec/dev-spec/game-spec.md"]),
    ("③⑤", "機率規格書", ["prob/prob-spec.md"]),
    ("④", "Go 快測", ["quicktest/qt-report/rtp-report.json"]),
    ("⑥", "機率可視化驗證", ["proto/index.html"]),
    ("⑦", "遊戲試玩版", ["game/pixi-client/game.js"]),
    ("⑧", "Game Server", ["game/handoff.md", "game/go-server/go.mod"]),
    ("⑨", "送審拍板", None),  # 特判：拍板書各章拍板欄全部填完才算完成（_review_state）
    ("⑩", "上線成效", ["docs/reports/*-d[0-9]*.html", "docs/reports/*-d[0-9]*.json", "docs/reports/*perf-review*.md"]),
]


def emit(ok: bool, data=None, error=None) -> None:
    print(json.dumps({"success": ok, "data": data, "error": error}, ensure_ascii=False))


def sha16(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def kb(n: int) -> str:
    return f"{n / 1024:,.0f} KB" if n < 1024 * 1024 else f"{n / 1024 / 1024:,.2f} MB"


def to_webp(src: pathlib.Path, dst: pathlib.Path, width: int = 720, q: int = 70) -> None:
    from PIL import Image
    im = Image.open(src)
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.convert("RGB").save(dst, "WEBP", quality=q, method=6)


def gdd_selfcontained(src: pathlib.Path, quality: str) -> str:
    """素材總覽外連圖 → html_images 縮圖（icon 角色）內嵌。"""
    hi = HERE.parents[1] / "ark-html-report" / "scripts"
    sys.path.insert(0, str(hi))
    import html_images as H  # noqa: PLC0415
    out, _ = H.embed(src.read_text(encoding="utf-8"), src.parent, quality=quality, budget_mb=REVIEW_KB / 1024,
                     role_rules={"*": "icon", "**/*": "icon"})
    return out


def pick_shots(names: list[str], kind: str) -> list[str]:
    """⑥：每場最後一張 + 載入 / L1 / L2；⑦：底圖 + 每情境 end。"""
    if kind == "proto":
        last: dict[str, str] = {}
        for n in sorted(names):
            m = re.match(r"play-(.+)-\d+\.png$", n)
            if m:
                last[m.group(1)] = n
        return [n for n in ("00-load.png", "01-l1.png") if n in names] + list(last.values()) + [n for n in ("91-l2.png",) if n in names]
    return [n for n in sorted(names) if n == "00-base.png" or n.endswith("-end.png")]


def collect_check(rep_p: pathlib.Path, kind: str, rv: pathlib.Path, files: list) -> dict | None:
    if not rep_p.is_file():
        return None
    rep = json.loads(rep_p.read_text(encoding="utf-8"))
    for k in ("url", "html"):                                    # 去掉本機絕對路徑
        if isinstance(rep.get(k), str):
            rep[k] = pathlib.Path(rep[k]).name
    shots_src = [p.name for p in rep_p.parent.glob("*.png")]
    picked, seen = [], set()
    for n in pick_shots(shots_src, kind):
        h = sha16(rep_p.parent / n)
        if h in seen:                                            # 同一畫面（例：載入即 L1 分頁）只留一張
            continue
        seen.add(h)
        dst = rv / "checks" / f"{kind}-{pathlib.Path(n).stem}.webp"
        to_webp(rep_p.parent / n, dst, width=720 if kind == "proto" else 480)   # ⑦ 直式畫面縮到寬 480
        picked.append(dst.name)
        files.append((dst, (rep_p.parent / n).as_posix()))
    rep["review_shots"] = picked
    name = "proto-browser-check.json" if kind == "proto" else "stage-smoke.json"
    (rv / "checks" / name).write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    files.append((rv / "checks" / name, rep_p.as_posix()))
    return rep


def collect_client(src: pathlib.Path, rv: pathlib.Path, files: list) -> dict | None:
    """⑧-C 正式 Client 驗收（S-4）：e2e 報告（pgp-e2e/1 的 *.json）合併成 checks/client-e2e.json，截圖（*.png，最多 8 張）轉 WebP。"""
    reps = sorted(src.glob("e2e-*.json")) if src.is_dir() else []
    if not reps:
        return None
    results, metrics, assets = [], {}, {}
    for rp in reps:
        r = json.loads(rp.read_text(encoding="utf-8"))
        tag = rp.stem.replace("e2e-", "")
        results += [{"name": f"[{tag}] {x.get('name')}", "ok": bool(x.get("ok"))} for x in r.get("results", [])]
        metrics = r.get("metrics") or metrics
        assets = r.get("assets") or assets
    picked = []
    for n in sorted(src.glob("*.png"))[:8]:
        dst = rv / "checks" / f"client-{n.stem}.webp"
        to_webp(n, dst, width=480)
        picked.append(dst.name)
        files.append((dst, n.as_posix()))
    rep = {"schema": "client-e2e/1", "pass": bool(results) and all(x["ok"] for x in results), "results": results,
           "metrics": metrics, "assets": assets, "reports": [p.name for p in reps], "review_shots": picked}
    (rv / "checks" / "client-e2e.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    files.append((rv / "checks" / "client-e2e.json", src.as_posix()))
    return rep


def run_checks(repo: pathlib.Path, out: pathlib.Path) -> list[str]:
    log = []
    proto = out / "proto"
    if (proto / "index.html").is_file():
        r = subprocess.run(["node", str(HERE / "tests" / "browser_check.js"), str(proto), "--turbo", "--l2", "200000"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        log.append(f"browser_check exit {r.returncode}: " + (r.stdout.strip().splitlines() or [""])[-1][:200])
    single = out / "game" / "pixi-client" / "single"
    if (single / "index.html").is_file():
        r = subprocess.run(["node", str(HERE / "stage" / "tests" / "smoke.js"), "--html", str(single), "--scenes", "all",
                            "--out", str(out / "game" / "pixi-client" / "smoke-shots")], capture_output=True, text=True, encoding="utf-8", errors="replace")
        log.append(f"smoke exit {r.returncode}: " + (r.stdout.strip().splitlines() or [""])[-1][:200])
    return log


def md_inline(t: str) -> str:
    t = html.escape(t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)


def md_to_html(md: str) -> str:
    """REVIEW.md 的小型渲染（標題 / 清單 / 表格 / 段落 / 行內 code、粗體）；略過 HTML 註解。"""
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    out, rows, lst = [], [], None
    def flush():
        nonlocal rows, lst
        if rows:
            hdr, body = rows[0], [r for r in rows[1:] if not re.fullmatch(r"[\s|:-]+", "|".join(r))]
            out.append("<table><tr>" + "".join(f"<th>{md_inline(c)}</th>" for c in hdr) + "</tr>" + "".join("<tr>" + "".join(f"<td>{md_inline(c)}</td>" for c in r) + "</tr>" for r in body) + "</table>")
            rows = []
        if lst:
            out.append(f"<{lst[0]}>" + "".join(f"<li>{md_inline(x)}</li>" for x in lst[1]) + f"</{lst[0]}>")
            lst = None
    for line in md.splitlines():
        s_ = line.strip()
        if s_.startswith("|"):
            if lst: flush()
            rows.append([c.strip() for c in s_.strip("|").split("|")]); continue
        m_ul, m_ol = re.match(r"[-*] (.*)", s_), re.match(r"\d+\. (.*)", s_)
        if m_ul or m_ol:
            kind = "ul" if m_ul else "ol"
            if rows or (lst and lst[0] != kind): flush()
            lst = lst or (kind, []); lst[1].append((m_ul or m_ol).group(1)); continue
        flush()
        m = re.match(r"(#{1,4}) (.*)", s_)
        if m:
            lv = min(len(m.group(1)) + 1, 4)
            out.append(f"<h{lv}>{md_inline(m.group(2))}</h{lv}>")
        elif s_.startswith(">"):
            out.append(f"<blockquote>{md_inline(s_.lstrip('> '))}</blockquote>")
        elif s_:
            out.append(f"<p>{md_inline(s_)}</p>")
    flush()
    return "\n".join(out)


def report_links(data: pathlib.Path) -> list[tuple[str, str, str]]:
    """data/<slug>/docs/reports/*.md：HTML 戳記吻合連 HTML，否則連 md 正本（標明）。"""
    out = []
    rd = data / "docs" / "reports"
    for md in sorted(rd.glob("*.md"), reverse=True) if rd.is_dir() else []:
        if "closeout" in md.stem:                                  # 結案報告在 ⑩ 之後，不屬於送審
            continue
        txt = md.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'^title:\s*"?(.+?)"?\s*$', txt, re.M)
        title = m.group(1) if m else md.stem
        verdict = re.search(r"^verdict:\s*(\S+)", txt, re.M)
        hp = md.with_suffix(".html")
        ok = hp.is_file() and f"sha256:{sha16(md)}" in hp.read_text(encoding="utf-8", errors="replace")
        target = hp if ok else md
        note = ("HTML" if ok else ("md 正本（HTML 未隨 md 更新）" if hp.is_file() else "md")) + (f" · verdict {verdict.group(1)}" if verdict else "") + " · 時點快照"
        out.append((title, "../" + target.relative_to(data).as_posix(), note))
    return out


def _review_state(data: pathlib.Path):
    """⑨ 送審拍板：無拍板書 → False；有拍板書但仍有待拍板 → "pending"；全部拍板 → True。"""
    for b in sorted(data.glob("review/*-decision/book.yaml")):
        dec = decision_rows(b.parent)
        return True if dec and not any(d["pending"] for d in dec) else "pending"
    return False


def stage_label(ok, md: bool = False) -> str:
    if ok == "pending":
        return "⏳ 送審中"
    return ("✅ 有產出" if md else "✓ 有產出") if ok else "— 尚無"


def stage_rows(data: pathlib.Path) -> list[tuple[str, str, object]]:
    rows = []
    for no, name, pats in STAGES:
        rows.append((no, name, _review_state(data) if pats is None else any(list(data.glob(p)) for p in pats)))
    return rows


INDEX_CSS = """
:root{--bg:#f7f6f3;--card:#fff;--ink:#1f1d1a;--ink2:#5c574f;--line:#e4e0d8;--ok:#1f8a4c;--bad:#c0392b;--acc:#b5651d}
@media (prefers-color-scheme:dark){:root{--bg:#16130f;--card:#211d18;--ink:#f1ece4;--ink2:#b3aa9c;--line:#3a332b;--ok:#4cc27e;--bad:#ff7b6b;--acc:#f0a35e}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 "Noto Sans TC","Microsoft JhengHei",sans-serif}
main{max-width:1080px;margin:0 auto;padding:24px 16px 64px}h1{margin:0 0 4px;font-size:26px}h2{margin:32px 0 10px;font-size:18px}
.sub{color:var(--ink2);font-size:13px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}.card a{color:var(--acc);font-weight:700;text-decoration:none}
.card .m{color:var(--ink2);font-size:12px;word-break:break-all}table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}
td,th{padding:7px 10px;border-bottom:1px solid var(--line);text-align:left;font-size:14px}th{color:var(--ink2);font-weight:600}
.ok{color:var(--ok);font-weight:700}.bad{color:var(--bad);font-weight:700}.na{color:var(--ink2)}
.review{margin-top:18px;border-left:5px solid var(--acc)}.review h2{margin:4px 0 8px}.review h3{margin:14px 0 6px;font-size:16px}
.review table{margin:6px 0}code{font-size:13px;background:var(--line);padding:0 4px;border-radius:4px}blockquote{margin:6px 0;padding:4px 10px;border-left:3px solid var(--line);color:var(--ink2)}
.shots{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px}.shots figure{margin:0;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.shots img{width:100%;display:block}.shots figcaption{font-size:12px;color:var(--ink2);padding:4px 8px}
"""


def build_index(game: str, slug: str, when: str, rows, arts: list[dict], checks: dict, links: list[tuple[str, str, str]],
                review_html: str = "", reports: list[tuple[str, str, str]] | None = None) -> str:
    e = html.escape
    st = "".join(f"<tr><td>{no}</td><td>{e(n)}</td><td class=\"{'ok' if ok is True else 'na'}\">{stage_label(ok)}</td></tr>" for no, n, ok in rows)
    cards = "".join(f"<div class=\"card\"><a href=\"{e(a['href'])}\">{e(a['title'])}</a><div>{e(a['desc'])}</div><div class=\"m\">{e(a['meta'])}</div></div>" for a in arts if a.get("kind") != "report")
    lk = "".join(f"<div class=\"card\"><a href=\"{e(h)}\">{e(t)}</a><div class=\"m\">{e(d)}</div></div>" for t, h, d in links)
    ck = ""
    for label, rep in checks.items():
        if not rep:
            ck += f"<h3>{e(label)}</h3><p class=\"na\">尚未驗收（送審前跑 review_build --run-checks）</p>"
            continue
        res = rep.get("results") or rep.get("checks") or []
        npass = sum(1 for r in res if r.get("ok"))
        ok = rep.get("pass", npass == len(res))
        ck += (f"<h3>{e(label)}：<span class=\"{'ok' if ok else 'bad'}\">{npass}/{len(res)} PASS</span></h3>"
               f"<p class=\"sub\">{e(str(rep.get('browser', '')))}　{e(str(rep.get('at', '')))}{('　FPS ' + str(rep['fps'])) if rep.get('fps') else ''}</p>"
               "<table>" + "".join(f"<tr><td class=\"{'ok' if r.get('ok') else 'bad'}\">{'✓' if r.get('ok') else '✗'}</td><td>{e(r.get('name', ''))}</td></tr>" for r in res) + "</table>"
               "<div class=\"shots\" style=\"margin-top:10px\">" + "".join(
                   f"<figure><a href=\"checks/{e(s)}\"><img loading=\"lazy\" src=\"checks/{e(s)}\" alt=\"{e(s)}\"></a><figcaption>{e(s)}</figcaption></figure>" for s in rep.get("review_shots", [])) + "</div>")
    return f"""<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(game)} 拍板包</title><style>{INDEX_CSS}</style></head><body><main>
<h1>{e(game)}　拍板包</h1><div class="sub">{e(slug)} · 發布 {e(when)} · 佈局契約 v3.5 ⑨ review/ · 成品連到定版家；要傳給人請用 review_build --export</div>
{f'<section class="card review">{review_html}</section>' if review_html else ''}
<h2>可以直接打開的成品</h2><div class="grid">{cards}</div>
<h2>定版家其他成品（相對連結）</h2><div class="grid">{lk}</div>
{('<h2>報告（定版家 docs/reports/）</h2><div class="grid">' + "".join(f'<div class="card"><a href="{e(h)}">{e(t)}</a><div class="m">{e(d)}</div></div>' for t, h, d in reports) + '</div>') if reports else ''}
<h2>十階段狀態</h2><table><tr><th>#</th><th>階段</th><th>定版家</th></tr>{st}</table>
<h2>真瀏覽器驗收</h2>{ck}
<p class="sub" style="margin-top:32px">由 ark-game-proto review_build.py 產生；要拍板的事項見 REVIEW.md。</p>
</main></body></html>
"""


REVIEW_SKELETON = """# {game} 拍板包說明

<!-- auto -->
<!-- /auto -->

## 這次要拍板什麼

- （人工填寫：例如「⑦ 試玩體感是否可進 ⑧ 正式 Server」）

## 怎麼看

1. 打開 `index.html`：成品入口、十階段狀態、驗收結果。
2. `play.html` 雙擊可玩（右上「除錯」→ 強制情境可直接看各特色遊戲）。

## 未決議

- （人工填寫）
"""


def write_review_md(p: pathlib.Path, game: str, auto: str) -> None:
    txt = p.read_text(encoding="utf-8") if p.is_file() else REVIEW_SKELETON.format(game=game)
    block = f"<!-- auto -->\n{auto.rstrip()}\n<!-- /auto -->"
    txt = re.sub(r"<!-- auto -->.*?<!-- /auto -->", lambda _: block, txt, flags=re.S) if "<!-- auto -->" in txt else block + "\n\n" + txt
    p.write_text(txt, encoding="utf-8")


DOC_CSS = """body{margin:0;background:#F6EEDC;color:#3B2A1A;font:16px/1.75 "Noto Sans TC","Microsoft JhengHei",sans-serif}
.bar{position:sticky;top:0;background:#6B4423;color:#F6D77A;padding:10px 18px;display:flex;gap:14px;align-items:center;border-bottom:3px solid #4A2E16;z-index:2}
.bar a{color:#FFF6E0;font-weight:900;text-decoration:none;background:#C8543A;border:2px solid #4A2E16;border-radius:10px;padding:4px 12px}
.bar span{font-size:13px;opacity:.9}main{max-width:860px;margin:24px auto;padding:24px 28px;background:#FFFBF2;border:2.5px solid #4A3018;border-radius:18px}
table{border-collapse:collapse;width:100%;margin:10px 0}th,td{border:1px solid #D9C8A6;padding:6px 9px;text-align:left;font-size:14px;vertical-align:top}th{background:#C8543A;color:#FFFBF2}
pre{background:#3B2A1A;color:#F6EEDC;padding:12px;border-radius:10px;overflow:auto}code{background:#F7E3D8;color:#8E3A24;padding:0 4px;border-radius:4px}pre code{background:none;color:inherit}
h1,h2,h3{font-family:"Zen Maru Gothic","Noto Sans TC",sans-serif}h2{border-bottom:3px dashed #E3B33E;padding-bottom:4px}blockquote{border-left:6px solid #A0703A;margin:8px 0;padding:4px 12px;background:#FBF2DE}"""
BACK_JS = "if(window.opener){window.close();return false}"   # 從拍板書開的新分頁 → 關掉分頁即回到書；直接開檔 → 連回 index.html


BACK_FAB = ('<a href="{href}" onclick="' + BACK_JS + '" style="position:fixed;right:18px;bottom:18px;z-index:2147483647;background:#C8543A;color:#FFFBF2;'
            "font:900 15px/1 'Noto Sans TC','Microsoft JhengHei',sans-serif;padding:11px 16px;border:2.5px solid #4A2E16;border-radius:12px;"
            'box-shadow:3px 4px 0 #4A2E16;text-decoration:none">← 回拍板書</a>')


def add_back(p: pathlib.Path, href: str = "index.html") -> None:
    """複製進拍板包的 HTML（試玩版除外）加浮動「← 回拍板書」：新分頁開的 → 關分頁；直接開檔 → 回 index.html。"""
    t = p.read_text(encoding="utf-8", errors="replace")
    fab = BACK_FAB.replace("{href}", href)
    t = t.replace("</body>", fab + "</body>", 1) if "</body>" in t else t + fab
    p.write_text(t, encoding="utf-8")


GEN_META = '<meta name="generator" content="review_build">'
DOC_GLOBS = (  # (定版家 md 樣式, 標籤, kind)；md 旁產同名 html（契約 v3.5：定版家擁有 md＋html，拍板書只連結）
    ("analysis/report/*.md", "① 競品分析報告", "doc"),
    ("spec/game-spec.v1.md", "② 遊戲規格書", "doc"),
    ("docs/decisions/*.md", "② 決議紀錄", "doc"),
    ("docs/designs/*.md", "設計文件", "doc"),
    ("quicktest/qt-report/*.md", "④ 快測報告", "doc"),
    ("game/handoff.md", "⑧ 工程交付單", "doc"),
    ("docs/reports/*.md", "報告", "report"),
)
REVIEW_KEEP = {"index.html", "review-manifest.json", "play.html", "gdd-overview.html", "REVIEW.md"}
SINGLE_FILE_KB = 500


def md_title(md: pathlib.Path) -> str:
    txt = md.read_text(encoding="utf-8", errors="replace")
    m = re.search(r'^title:\s*"?(.+?)"?\s*$', txt, re.M) or re.search(r"^#\s+(.+)$", txt, re.M)
    return m.group(1).strip() if m else md.stem


def stage_doc_page(title: str, body: str, src: str, stamp: str) -> str:
    """定版家文件頁（md 旁的 View 軌）：不依賴拍板書；尾端 content-src 戳記供 ps_layout L-STAMP 驗。"""
    e = html.escape
    return (f'<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f"{GEN_META}<title>{e(title)}</title><style>{DOC_CSS}</style></head><body>"
            f'<div class="bar"><span><b>{e(title)}</b></span><span style="margin-left:auto">來源 {e(src)}（md 為正本）</span></div>'
            f"<main>{body}</main></body></html>\n<!-- content-src: {stamp} -->\n")


def md_file_to_html(md_p: pathlib.Path) -> str:
    import markdown  # noqa: PLC0415
    txt = md_p.read_text(encoding="utf-8", errors="replace")
    txt = re.sub(r"\A---\n.*?\n---\n", "", txt, flags=re.S)
    return markdown.markdown(txt, extensions=["tables", "fenced_code"])


def publish_docs(data: pathlib.Path) -> dict:
    """定版家 md → 同目錄同名 html（帶戳記）。戳記相符或不是本工具產的 html 一律不動（冪等、不蓋別人的成對檔）。"""
    res: dict[str, list[str]] = {"published": [], "skipped": [], "failed": []}
    for pat, _, _ in DOC_GLOBS:
        for md in sorted(data.glob(pat)):
            hp, rel = md.with_suffix(".html"), md.relative_to(data).as_posix()
            stamp = f"{md.name} sha256:{sha16(md)}"
            if hp.is_file():
                t = hp.read_text(encoding="utf-8", errors="replace")
                if stamp in t:
                    res["skipped"].append(rel)
                    continue
                if GEN_META not in t:
                    res["skipped"].append(f"{rel}（他工具產的 html，不覆寫）")
                    continue
            try:
                page = stage_doc_page(md_title(md), md_file_to_html(md), rel, stamp)
            except ImportError:
                res["failed"].append(f"{rel}：缺 markdown 套件")
                continue
            if len(page.encode("utf-8")) > SINGLE_FILE_KB * 1024:
                res["failed"].append(f"{rel}：html 超過單檔 {SINGLE_FILE_KB} KB")
                continue
            hp.write_text(page, encoding="utf-8")
            res["published"].append(rel)
    return res


def clean_review(rv: pathlib.Path) -> list[str]:
    """拍板包白名單外的檔一律清掉（v0.3 的複製品 docs/、prob-spec.html、proto.html 與孤兒檔）；保留 checks/ 與拍板書原稿。"""
    removed = []
    for p in sorted(rv.iterdir()) if rv.is_dir() else []:
        if p.is_dir():
            if p.name == "checks" or (p / "book.yaml").is_file():
                continue
            shutil.rmtree(p)
            removed.append(p.name + "/")
        elif p.name not in REVIEW_KEEP:
            p.unlink()
            removed.append(p.name)
    return removed


def linked_items(data: pathlib.Path, rv: pathlib.Path, skip_proto: bool = False, excludes: tuple[str, ...] = ()) -> tuple[list[dict], list[dict]]:
    """拍板書要連的定版家成品：相對連結（../<stage>/…），不複製。回傳（卡片清單, 清冊 links）。
    skip_proto：還原局（R-3）⑥ 驗證台內嵌線上機率等級參數，不連；excludes：相對定版家的 glob，符合者不連（例 docs/reports/*live*）。"""
    items: list[dict] = []
    links: list[dict] = []

    def add(p: pathlib.Path, title: str, desc: str, kind: str) -> None:
        if (data / "ref") in p.parents:                       # 契約 v3.6：ref/ 參考資源層（含 🔒 live）永不進拍板包
            return
        rel = p.relative_to(data).as_posix()
        if any(pathlib.PurePosixPath(rel).match(g) or pathlib.PurePosixPath(rel).with_suffix(".md").match(g) for g in excludes):
            return
        href = pathlib.Path(os.path.relpath(p, rv)).as_posix()
        items.append({"href": href, "title": title, "desc": desc, "kind": kind, "meta": f"{kb(p.stat().st_size)} · sha {sha16(p)}"})
        links.append({"path": href, "sha256_16": sha16(p), "bytes": p.stat().st_size, "source": p.relative_to(data).as_posix()})

    for p, title, desc in ((data / "prob" / "prob-spec.html", "⑤ 機率規格書", "參數表、§2 快測數據、流程圖"),
                           (data / "proto" / "index.html", "⑥ 機率驗證台", "L1 精算 / L2 蒙地卡羅 / Go 逐局對照 / 演出（演出需網路載入 PixiJS）")):
        if p.is_file() and not (skip_proto and p.parent.name == "proto"):
            add(p, title, desc, "app")
    for pat, label, kind in DOC_GLOBS:
        for md in sorted(data.glob(pat), reverse=kind == "report"):
            if kind == "report" and "closeout" in md.stem:          # 結案報告在 ⑩ 之後，不屬於送審
                continue
            hp = md.with_suffix(".html")
            target = hp if hp.is_file() and f"{md.name} sha256:{sha16(md)}" in hp.read_text(encoding="utf-8", errors="replace") else md
            if kind == "report":
                vd = re.search(r"^verdict:\s*(\S+)", md.read_text(encoding="utf-8", errors="replace"), re.M)
                add(target, md_title(md), "報告（時點快照）" + (f" · verdict {vd.group(1)}" if vd else ""), "report")
            else:
                add(target, label if "*" not in pat else f"{label}：{md_title(md)}", f"定版家 {md.relative_to(data).as_posix()}", "doc")
    return items, links


def rel_src(s: str, repo: pathlib.Path) -> str:
    """清冊來源一律寫相對 repo 的路徑；別環境的絕對路徑（如 /sessions/…）退成 output/ 以下的相對段。"""
    pth = pathlib.Path(s)
    if not pth.is_absolute():
        return s
    try:
        return pth.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        parts = pth.as_posix().split("/output/", 1)
        return "output/" + parts[1] if len(parts) == 2 else pth.name


def export_pack(repo: pathlib.Path, data: pathlib.Path, rv: pathlib.Path, links: list[dict], dest: pathlib.Path) -> dict:
    """可帶走的拍板包：review/ ＋ 被連到的定版家檔案，保留 <slug>/ 底下的相對結構，連結照樣能開。不准寫回 data/。"""
    dest = dest.resolve()
    droot = (repo / "data").resolve()
    if dest == droot or droot in dest.parents:
        raise ValueError(f"--export 不可寫進 data/（{dest}）：複製品不該回到定版家")
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(rv, dest / "review", ignore=shutil.ignore_patterns(".book-build.html"))
    n = 0
    for lk in links:
        if str(lk.get("source", "")).startswith("ref/"):    # 契約 v3.6：ref/ 不隨拍板包帶走
            raise ValueError(f"--export 不可帶出 ref/：{lk.get('source')}")
        src = (rv / lk["path"]).resolve()
        dst = dest / src.relative_to(data.resolve())
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        n += 1
    return {"dir": dest.as_posix(), "linked_files": n, "total_kb": sum(f.stat().st_size for f in dest.rglob("*") if f.is_file()) // 1024}


def decision_rows(book_dir: pathlib.Path) -> list[dict]:
    """讀各 R-x 章的「拍板欄」表：| R-x 項目 | 決議 | 拍板人 | 日期 |。決議以「（待拍板」開頭 → 待拍板。"""
    out = []
    for md in sorted(book_dir.glob("[0-8][0-9]-*.md")):
        txt = md.read_text(encoding="utf-8")
        ch = re.search(r"^chapter:\s*(\d+)", txt, re.M)
        title = re.search(r'^title:\s*"?(.+?)"?\s*$', txt, re.M)
        sec = txt.split("### 拍板欄", 1)
        if len(sec) < 2 or not ch:
            continue
        row = next((r for r in sec[1].splitlines() if re.match(r"\|\s*R-\d", r)), None)
        if not row:
            continue
        c = [x.strip() for x in row.strip().strip("|").split("|")] + ["", "", ""]
        pending = c[1].startswith("（待拍板") or not c[1]
        sug = re.search(r"建議([^）]*)", c[1])
        out.append({"id": c[0].split()[0], "item": c[0], "title": title.group(1) if title else md.stem, "chapter": int(ch.group(1)),
                    "pending": pending, "decision": c[1], "suggest": sug.group(1).lstrip("：") if sug else "", "by": c[2], "date": c[3]})
    return out


def write_status(book_dir: pathlib.Path, game: str, when: str, arts: list[dict], checks: dict, rows, data: pathlib.Path) -> None:
    """拍板書第 1 章「現況：一頁看完」（每次發布重產）：結論、四件拍板事項狀態、成品（新分頁）、驗收、十階段。"""
    import yaml  # noqa: PLC0415
    slug = yaml.safe_load((book_dir / "book.yaml").read_text(encoding="utf-8"))["slug"]
    rr = data / "quicktest" / "qt-report" / "rtp-report.json"
    g = json.loads(rr.read_text(encoding="utf-8")).get("games", {}) if rr.is_file() else {}
    rep = json.loads(rr.read_text(encoding="utf-8")) if rr.is_file() else {}
    lr = data / "layout-report.json"
    verdict = (json.loads(lr.read_text(encoding="utf-8")).get("facts", {}).get("rtp_report", {}) or {}).get("verdict") if lr.is_file() else None
    pc = lambda k: f"{100 * g[k]['rtp']:.2f}%" if g.get(k, {}).get("rtp") is not None else "—"  # noqa: E731
    done = sum(len(no) for no, _, ok in rows if ok is True)          # ③⑤ 同一列 = 兩個階段
    dec = decision_rows(book_dir)
    npend = sum(1 for d in dec if d["pending"])
    L = [f"""---
book: {slug}
chapter: 1
slug: status
title: "現況：一頁看完 {game} 走到哪裡"
type: chapter
level: intermediate
est_minutes: 5
punchline: "研發全綠，只剩 {len(dec)} 件事要人拍板。"
objectives:
  - 一頁看懂十階段進度、驗收結果與待拍板事項
  - 從本章直接打開每一個成品
prerequisites: [preface]
key_terms: [拍板包, 真瀏覽器驗收]
tags: [slot, pipeline]
sources:
  - ../review-manifest.json
  - ../../quicktest/qt-report/rtp-report.json
trust: deterministic
confidence: high
status: review
---

# 現況：一頁看完 {game} 走到哪裡

> 本章由 ark-game-proto review_build 於 {when} 依實際檔案產生，重新發布會覆寫；成品連結都會開新分頁，看完關掉分頁就回到這本書。

## 這章要解決的問題

送審時第一個問題總是：現在到底做到哪了？哪些已經驗證、哪些還要人決定？成品在哪裡打開？

## 路線圖

1. 一句話結論與關鍵數字
2. 要拍板的 {len(dec)} 件事與目前狀態
3. 可以直接打開的成品與驗收結果

## 內文

### 一句話結論

十階段完成 {done} 個（{'⑩ 上線成效要上線後才有' if npend == 0 else '⑨ 送審拍板等本書拍板、⑩ 上線成效要上線後才有'}）。Go 快測 {int(rep.get('spins') or 0):,} 局總 RTP {pc('Total')}（主遊戲 {pc('MainGame')}、特色遊戲 {pc('SpecialGameTotal')}），三向判定 **{verdict or '—'}**；目前 **{npend} 件待拍板**。

### 要拍板的 {len(dec)} 件事

| # | 要決定的事 | 建議 | 狀態 | 詳見 |
|---|---|---|---|---|
"""]
    for d in dec:
        st = "⏳ 待拍板" if d["pending"] else f"✅ {d['decision']}（{d['by']} {d['date']}）"
        L.append(f"| {d['id']} | {d['item'].split(' ', 1)[-1]} | {d['suggest'] or '—'} | {st} | 第 {d['chapter']} 章 |\n")
    L.append("\n> [!ASK] 你可能會想說\n> 這麼多成品，先看哪一個？\n> 先玩 **⑦ 試玩版**（第 2 章 R-1 的依據）；數學細節再看 ⑥ 驗證台。每個成品都開新分頁，不會把這本書蓋掉。\n\n")
    L.append("### 可以直接打開的成品（↗ 新分頁）\n\nreview/ 資料夾連同驗收紀錄，叫做 **拍板包**；成品都連到定版家各階段目錄（不複製，看到的永遠是現行版）。要整包傳給人，用 `review_build --export <資料夾>`。\n\n| 成品 | 用途 | 大小 |\n|---|---|---|\n")
    for x in arts:
        if x.get("kind") == "report":
            continue
        L.append(f"| [{x['title']} ↗](../{x['href']}) | {x['desc']} | {x['meta'].split(' · ')[0]} |\n")
    L.append("\n### 驗收結果（**真瀏覽器驗收**：系統 Chrome 無頭模式實跑）\n\n| 驗收 | 結果 | 瀏覽器 |\n|---|---|---|\n")
    for label, r in checks.items():
        if not r:
            L.append(f"| {label} | 尚未驗收 | — |\n")
            continue
        res = r.get("results") or r.get("checks") or []
        L.append(f"| {label} | {'✅' if r.get('pass') else '❌'} {sum(1 for x in res if x.get('ok'))}/{len(res)} PASS{(' · FPS ' + str(r['fps'])) if r.get('fps') else ''} | {r.get('browser', '')} |\n")
    L.append("\n截圖與逐項檢查見附錄。\n\n### 十階段\n\n| 階段 | 名稱 | 定版家 |\n|---|---|---|\n" + "".join(f"| {no} | {n} | {stage_label(ok, md=True)} |\n" for no, n, ok in rows))
    L.append(f"""
## 常見誤解

> [!MYTH] 大家通常會以為
> 驗收全部 PASS 就代表可以上線。但其實 PASS 證明的是「規則一致、數字達標、畫面跑得完」；好不好玩、要不要定版、要不要加功能、美術怎麼換，是本書後面 {len(dec)} 章要人拍板的事。

## 動手做

1. 在「可以直接打開的成品」點 ⑦ 試玩版，玩 30 轉後關掉分頁回到本書
2. 依「要拍板的事」表格，從第 2 章開始逐章閱讀並在拍板欄填寫決議
3. 填完重新發布：`py -X utf8 .kiro/skills/ark-game-proto/scripts/review_build.py --slug <slug>`

你應該看到：重新發布後，本章表格的「狀態」欄從「⏳ 待拍板」變成你填的決議。

## 重點回顧

- 研發全綠，只剩 {len(dec)} 件事要人拍板。
- 成品都開新分頁，關掉分頁就回到書。
- 拍板欄填完重新發布，本章狀態自動更新。

## 下一章

下一章從最需要親手體驗的 R-1 體感開始。
""")
    (book_dir / "01-status.md").write_text("".join(L), encoding="utf-8")


def write_appendix(book_dir: pathlib.Path, game: str, when: str, arts: list[dict], checks: dict, links, reports, rows) -> None:
    """拍板書附錄（每次發布重產）：網頁地圖、驗收逐項與截圖、報告。路徑相對於書原稿目錄。"""
    import yaml  # noqa: PLC0415
    slug = yaml.safe_load((book_dir / "book.yaml").read_text(encoding="utf-8"))["slug"]
    KIND = {"app": "↗ 新分頁（應用）", "doc": "↗ 新分頁（定版家文件）", "report": "↗ 新分頁（定版家報告）"}
    tree = ["review/index.html   拍板書（本書；章節在同一分頁切換）"]
    for x in arts:
        tree.append(f"├─↗ {x['href']:<28s} {x['title']}")
    tree.append("└── checks/                      驗收截圖（書內嵌圖）")
    L = [f"""---
book: {slug}
chapter: 99
slug: appendix-artifacts
title: "附錄：網頁地圖、驗收紀錄與報告"
type: appendix
level: intermediate
est_minutes: 5
punchline: "每個拍板依據都能點開、能重跑、能追到來源。"
objectives:
  - 找到拍板包裡每個成品、驗收紀錄與報告
prerequisites: []
key_terms: [網頁地圖, 真瀏覽器驗收]
tags: [slot, pipeline]
sources:
  - ../review-manifest.json
trust: deterministic
confidence: high
status: review
---

# 附錄：網頁地圖、驗收紀錄與報告

> 本附錄由 ark-game-proto review_build 於 {when} 產生，重新發布會覆寫；人工內容請寫在前面各章。

## 這章要解決的問題

拍板時常被問：這個結論的依據在哪？打開之後怎麼回來？能不能自己重跑一次？

## 路線圖

1. 網頁地圖：拍板包裡每一頁在哪、怎麼開、怎麼回來
2. 真瀏覽器驗收的逐項結果與截圖
3. 定版家報告

## 內文

### 網頁地圖

拍板包所有頁面與它們的開法，整理成 **網頁地圖**。`../` 開頭的是定版家各階段目錄的成品（相對連結，不複製）；要傳給人請用 `review_build --export`。

```
""" + "\n".join(tree) + """
```

| 頁面 | 開法 | 怎麼回到書 |
|---|---|---|
| 本書章節 | 同分頁（左側目錄） | 左側目錄、上一章／下一章 |
"""]
    for x in arts:
        back = "關掉分頁"
        L.append(f"| [{x['title']}](../{x['href']}) | {KIND.get(x.get('kind'), '↗ 新分頁')} | {back} |\n")
    L.append("\n> [!ASK] 你可能會想說\n> 截圖跟我自己打開看到的不一樣怎麼辦？\n> 截圖是發布當下的 **真瀏覽器驗收** 結果；以自己打開看到的為準，有差異就重跑 `review_build --run-checks`。\n\n")
    L.append("### 真瀏覽器驗收（逐項）\n\n")
    for label, rep in checks.items():
        if not rep:
            L.append(f"**{label}**：尚未驗收（`review_build --run-checks`）\n\n")
            continue
        res = rep.get("results") or rep.get("checks") or []
        L.append(f"**{label}**：{sum(1 for r in res if r.get('ok'))}/{len(res)} PASS · {rep.get('browser', '')}" + (f" · FPS {rep['fps']}" if rep.get("fps") else "") + "\n\n")
        L.append("| 結果 | 檢查項 |\n|---|---|\n" + "".join(f"| {'✓' if r.get('ok') else '✗'} | {r.get('name', '')} |\n" for r in res) + "\n")
        for s in rep.get("review_shots", []):
            L.append(f"![{s}](../checks/{s})\n\n")
    reps = [x for x in arts if x.get("kind") == "report"]
    if reps:
        L.append("### 定版家報告（時點快照）\n\n" + "".join(f"- [{x['title']} ↗](../{x['href']})（{x['desc']}）\n" for x in reps) + "\n")
    L.append("""## 常見誤解

> [!MYTH] 大家通常會以為
> 拍板包是每次建置都會更新的工作目錄。但其實拍板包只在送審前發布一次；工作中的中間檔在 output/，拍板包反映的是送審當下的狀態。

## 重點回顧

- 每個拍板依據都能點開、能重跑、能追到來源。
- 成品開新分頁，關掉就回到書；成品都在定版家，拍板包不複製。
- 拍板包只在送審前發布。
""")
    (book_dir / "99-appendix-artifacts.md").write_text("".join(L), encoding="utf-8")


def build_book(book_dir: pathlib.Path, out_html: pathlib.Path) -> dict:
    """ark-book：book_lint（記錄）→ book_build → 路徑從書原稿目錄改成 review/ 根（index.html 在上一層）。"""
    bs = HERE.parents[1] / "ark-book" / "scripts"
    lint = subprocess.run([sys.executable, "-X", "utf8", str(bs / "book_lint.py"), str(book_dir)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    tmp = book_dir.parent / ".book-build.html"
    b = subprocess.run([sys.executable, "-X", "utf8", str(bs / "book_build.py"), str(book_dir), "--out", str(tmp)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if b.returncode != 0 or not tmp.is_file():
        raise SystemExit(f"book_build 失敗：{(b.stderr or b.stdout)[-400:]}")
    h = tmp.read_text(encoding="utf-8")
    h = re.sub(r'((?:href|src)=")\.\./', r"\1", h)            # 書原稿在 review/<book>/，index.html 在 review/
    # 成品一律開新分頁：書留在原分頁，關掉分頁即返回（章節內 #hash 跳轉維持同分頁）
    h = re.sub(r'<a (?![^>]*\btarget=)([^>]*\bhref="(?!#)[^"]+")', r'<a target="_blank" rel="noopener" \1', h)
    out_html.write_text(h, encoding="utf-8")
    tmp.unlink()
    tail = [ln for ln in lint.stdout.strip().splitlines() if ln.strip()][-1:] or [""]
    return {"dir": book_dir.name, "lint_exit": lint.returncode, "lint": tail[0][:200]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--slug", required=True)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--domain", default="slot")
    ap.add_argument("--quality", default="auto", choices=["auto", "standard", "lite"])
    ap.add_argument("--run-checks", action="store_true")
    ap.add_argument("--export", default=None, help="另產可帶走的完整拍板包到此資料夾（不得在 data/ 內）")
    ap.add_argument("--no-play", action="store_true", help="還原局（R-3）：不收 ⑦ 單檔、不連 ⑥ 驗證台（兩者內嵌線上機率等級參數）")
    ap.add_argument("--exclude-link", action="append", default=[], help="不連的定版家文件 glob（相對定版家，可多次；例 docs/reports/*live*）")
    ap.add_argument("--client-checks", default=None, help="⑧-C 正式 Client e2e 報告資料夾（e2e-*.json＋截圖 *.png）")
    ap.add_argument("--play-url", default=None, help="⑧-C 正式 Client 試玩網址（測試環境）；寫進拍板書成品清單")
    a = ap.parse_args()
    repo = pathlib.Path(a.repo).resolve()
    data, out = repo / "data" / a.domain / a.slug, repo / "output" / a.domain / a.slug
    if not data.is_dir():
        emit(False, error={"code": "BAD_INPUT", "message": f"找不到定版家 {data}"})
        return 2
    log = run_checks(repo, out) if a.run_checks else []
    rv = data / "review"
    docs_res = publish_docs(data)                              # v3.5：文件 html 寫回定版家（md 旁）
    removed = clean_review(rv)                                 # v3.5：白名單外舊檔（含 v0.3 複製品）清掉
    (rv / "checks").mkdir(parents=True, exist_ok=True)
    for old in (rv / "checks").glob("*"):
        old.unlink()
    files: list[tuple[pathlib.Path, str]] = []
    gc = data / "proto" / "game-config.json"
    game = json.loads(gc.read_text(encoding="utf-8")).get("game") if gc.is_file() else a.slug
    arts = []
    # ⑦ 試玩單檔
    single = out / "game" / "pixi-client" / "single" / "index.html"
    if single.is_file() and not a.no_play:
        shutil.copyfile(single, rv / "play.html")
        files.append((rv / "play.html", single.relative_to(repo).as_posix()))
        sb = single.parent / "stage-build.json"
        meta = json.loads(sb.read_text(encoding="utf-8")) if sb.is_file() else {}
        arts.append({"href": "play.html", "title": "⑦ 試玩版（雙擊可玩）", "desc": "Stage 正式演出版型單檔；右上「除錯」可強制情境",
                     "meta": f"{kb(single.stat().st_size)} · sha {sha16(single)}" + (f" · 玩法 {meta.get('feature')}" if meta.get("feature") else "")})
    elif (rv / "play.html").exists():
        (rv / "play.html").unlink()
    # ② 素材總覽自足版
    gdd_src = next(iter(sorted((out / "gdd").glob("*.html"))), None) if (out / "gdd").is_dir() else None
    quality = "standard" if a.quality in ("auto", "standard") else "lite"
    if gdd_src:
        (rv / "gdd-overview.html").write_text(gdd_selfcontained(gdd_src, quality), encoding="utf-8")
        add_back(rv / "gdd-overview.html")
        files.append((rv / "gdd-overview.html", gdd_src.relative_to(repo).as_posix()))
    # ⑥⑦ 驗收
    if a.no_play:                                              # 還原局（R-3）：⑥⑦ 建置內嵌線上機率等級參數，驗收截圖也不收
        checks = {}
    else:
        checks = {"⑥ 驗證台（browser_check）": collect_check(out / "proto" / "browser-check" / "browser-check.json", "proto", rv, files),
                  "⑦ 試玩版（smoke）": collect_check(out / "game" / "pixi-client" / "smoke-shots" / "smoke.json", "stage", rv, files)}
    if a.client_checks:
        checks["⑧-C 正式 Client（e2e）"] = collect_client(pathlib.Path(a.client_checks).resolve(), rv, files)
    if a.play_url:
        arts.append({"href": a.play_url, "title": "⑧-C 正式 Client 試玩（測試環境）", "desc": "Go Server＋正式 Client；網址只在測試期間開放",
                     "meta": "外部網址"})
    # 超額且 auto → gdd 降 lite
    total = lambda: sum(f.stat().st_size for f, _ in files)  # noqa: E731
    if total() > REVIEW_KB * 1024 and gdd_src and a.quality == "auto" and quality == "standard":
        quality = "lite"
        (rv / "gdd-overview.html").write_text(gdd_selfcontained(gdd_src, quality), encoding="utf-8")
        add_back(rv / "gdd-overview.html")
    if gdd_src:
        g = rv / "gdd-overview.html"
        arts.insert(0, {"href": "gdd-overview.html", "title": "② 素材總覽（圖文規格）", "desc": f"縮圖內嵌自足版（{quality}）",
                        "meta": f"{kb(g.stat().st_size)} · sha {sha16(g)}"})
    for x in arts:
        x["kind"] = "app"
    linked, link_rows = linked_items(data, rv, skip_proto=a.no_play, excludes=tuple(a.exclude_link))   # v3.5：定版家成品走相對連結，不複製
    arts += linked
    links = []
    when = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    (rv / "index.html").write_text(build_index(game, a.slug, when, stage_rows(data), arts, checks, links), encoding="utf-8")
    files.append((rv / "index.html", "review_build"))
    auto = (f"- 發布：{when}（review_build；契約 v3.5）\n"
            + "".join(f"- {x['title']}：`{x['href']}`（{x['meta']}）\n" for x in arts)
            + "".join(f"- {k}：" + (f"{sum(1 for r in (v.get('results') or v.get('checks') or []) if r.get('ok'))}/{len(v.get('results') or v.get('checks') or [])} PASS\n" if v else "尚未驗收\n") for k, v in checks.items()))
    book_dir = next((p.parent for p in sorted(rv.glob("*/book.yaml"))), None)
    book_info = None
    if book_dir and (HERE.parents[1] / "ark-book" / "scripts" / "book_build.py").is_file():
        # 拍板書（ark-book 架構）：人寫的序與 R-x 章保留；附錄每次重產；index.html = book_build 輸出
        write_status(book_dir, game, when, arts, checks, stage_rows(data), data)
        write_appendix(book_dir, game, when, arts, checks, links, [], stage_rows(data))
        book_info = build_book(book_dir, rv / "index.html")
        for f in sorted(book_dir.glob("*")):
            if f.is_file():
                files.append((f, "拍板書原稿（附錄由 review_build 產生）" if f.name.startswith("99-") else "拍板書原稿（人工）"))
        if (rv / "REVIEW.md").is_file():                       # 舊版送審說明已併入拍板書
            (rv / "REVIEW.md").unlink()
    else:
        write_review_md(rv / "REVIEW.md", game, auto)
        files.append((rv / "REVIEW.md", "review_build（人工區保留）"))
        # 導覽頁最後寫：內嵌 REVIEW.md（要拍板的事放最上面）＋ 定版家報告連結
        (rv / "index.html").write_text(build_index(game, a.slug, when, stage_rows(data), arts, checks, links,
                                                   md_to_html((rv / "REVIEW.md").read_text(encoding="utf-8")), report_links(data)), encoding="utf-8")
    idx_txt = (rv / "index.html").read_text(encoding="utf-8", errors="replace")
    broken = sorted({h for h in re.findall(r'(?:href|src)="([^"#:?]+)"', idx_txt) if not (rv / h).resolve().is_file()})   # 人工章節寫死舊路徑也抓得到
    bad = [f.name for f in rv.rglob("*") if f.is_file() and f.suffix.lower() in BAN]
    tot = sum(f.stat().st_size for f in rv.rglob("*") if f.is_file())
    if bad or tot > REVIEW_KB * 1024:
        emit(False, {"total_kb": tot // 1024, "banned": bad}, {"code": "GATE_BLOCKED", "message": f"拍板包 {tot // 1024} KB（上限 {REVIEW_KB}）或含禁止檔 {bad}"})
        return 1
    man = {"schema": "review-manifest/1", "contract": "3.5", "slug": a.slug, "game": game, "generated_at": when, "gdd_quality": quality if gdd_src else None,
           "files": [{"path": f.relative_to(rv).as_posix(), "sha256_16": sha16(f), "bytes": f.stat().st_size, "source": rel_src(s, repo)} for f, s in files if f.name != "REVIEW.md"],
           "links": link_rows, "total_bytes": tot}
    (rv / "review-manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    exported = None
    if a.export:
        try:
            exported = export_pack(repo, data, rv, link_rows, pathlib.Path(a.export))
        except ValueError as ex:
            emit(False, error={"code": "BAD_INPUT", "message": str(ex)})
            return 2
    emit(True, {"review": rv.relative_to(repo).as_posix(), "total_kb": tot // 1024, "files": len(man["files"]) + 2, "gdd_quality": man["gdd_quality"],
                "links": len(link_rows), "docs_published": docs_res["published"], "docs_skipped": len(docs_res["skipped"]),
                "docs_failed": docs_res["failed"], "removed": removed, "export": exported, "broken_links": broken,
                "checks": {k: (bool(v) and bool(v.get("pass"))) for k, v in checks.items()}, "run_checks": log, "book": book_info,
                "delivery": f"review_build {a.slug}｜{kb(tot)} / {REVIEW_KB // 1024} MB｜開 {rv.relative_to(repo).as_posix()}/index.html"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
