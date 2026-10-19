#!/usr/bin/env python3
"""review_build — 發布拍板包 data/<domain>/<slug>/review/（佈局契約 v3.3；給人拍板、可 demo 的研發產物）。

彙整工作檯 output/<domain>/<slug>/ 的成品進定版家（送審前跑一次，不是每次 build）：
  play.html            ⑦ 試玩版單檔（output/…/game/pixi-client/single/index.html，雙擊可玩）
  gdd-overview.html    ② 素材總覽自足版（output/…/gdd/*.html 外連圖 → ark-html-report html_images 縮圖 WebP 內嵌）
  checks/              ⑥ browser-check.json、⑦ stage-smoke.json ＋ 每種玩法 / 情境的代表截圖（WebP）
  index.html           導覽頁：九階段狀態、成品連結＋大小＋sha16、驗收結果與截圖牆（自足、離線可開）
  REVIEW.md            送審說明（首次產骨架；之後只更新 <!-- auto --> 區段，人工區保留）
  review-manifest.json 每個檔的來源＋sha16＋大小（ps_layout L-REVIEW 據此判拍板包是否過期）
⑤ prob/prob-spec.html、⑥ proto/index.html 留原位（受 ps_lint／proto_build 綁定），導覽頁用相對連結。

用法：py scripts/review_build.py --slug <slug> [--repo .] [--domain slot] [--quality auto|standard|lite] [--run-checks]
  --run-checks：先跑 tests/browser_check.js（⑥）與 stage/tests/smoke.js --scenes all（⑦）再收集
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
    ("⑨", "上線成效", ["docs/reports/*perf-review*.md"]),
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


def stage_rows(data: pathlib.Path) -> list[tuple[str, str, bool]]:
    rows = []
    for no, name, pats in STAGES:
        rows.append((no, name, any(list(data.glob(p)) for p in pats)))
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
    st = "".join(f"<tr><td>{no}</td><td>{e(n)}</td><td class=\"{'ok' if ok else 'na'}\">{'✓ 有產出' if ok else '— 尚無'}</td></tr>" for no, n, ok in rows)
    cards = "".join(f"<div class=\"card\"><a href=\"{e(a['href'])}\">{e(a['title'])}</a><div>{e(a['desc'])}</div><div class=\"m\">{e(a['meta'])}</div></div>" for a in arts)
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
<h1>{e(game)}　拍板包</h1><div class="sub">{e(slug)} · 發布 {e(when)} · 佈局契約 v3.3 review/ · 本包可整個資料夾傳給人離線開</div>
{f'<section class="card review">{review_html}</section>' if review_html else ''}
<h2>可以直接打開的成品</h2><div class="grid">{cards}</div>
<h2>定版家其他成品（相對連結）</h2><div class="grid">{lk}</div>
{('<h2>報告（定版家 docs/reports/）</h2><div class="grid">' + "".join(f'<div class="card"><a href="{e(h)}">{e(t)}</a><div class="m">{e(d)}</div></div>' for t, h, d in reports) + '</div>') if reports else ''}
<h2>九階段狀態</h2><table><tr><th>#</th><th>階段</th><th>定版家</th></tr>{st}</table>
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

1. 打開 `index.html`：成品入口、九階段狀態、驗收結果。
2. `play.html` 雙擊可玩（右上「除錯」→ 強制情境可直接看各特色遊戲）。

## 未決議

- （人工填寫）
"""


def write_review_md(p: pathlib.Path, game: str, auto: str) -> None:
    txt = p.read_text(encoding="utf-8") if p.is_file() else REVIEW_SKELETON.format(game=game)
    block = f"<!-- auto -->\n{auto.rstrip()}\n<!-- /auto -->"
    txt = re.sub(r"<!-- auto -->.*?<!-- /auto -->", lambda _: block, txt, flags=re.S) if "<!-- auto -->" in txt else block + "\n\n" + txt
    p.write_text(txt, encoding="utf-8")


def write_appendix(book_dir: pathlib.Path, game: str, when: str, arts: list[dict], checks: dict, links, reports, rows) -> None:
    """拍板書附錄（ark-book 章節契約；每次發布重產）：成品、驗收、九階段、報告。路徑相對於書原稿目錄。"""
    import yaml  # noqa: PLC0415
    slug = yaml.safe_load((book_dir / "book.yaml").read_text(encoding="utf-8"))["slug"]
    L = [f"""---
book: {slug}
chapter: 99
slug: appendix-artifacts
title: "附錄：拍板包成品、驗收紀錄與九階段狀態"
type: appendix
level: intermediate
est_minutes: 5
punchline: "每個拍板依據都能點開、能重跑、能追到來源。"
objectives:
  - 找到拍板包裡每個成品與驗收紀錄
prerequisites: []
key_terms: [拍板包, 真瀏覽器驗收]
tags: [slot, pipeline]
sources:
  - ../review-manifest.json
trust: deterministic
confidence: high
status: review
---

# 附錄：拍板包成品、驗收紀錄與九階段狀態

> 本附錄由 ark-game-proto review_build 於 {when} 產生，重新發布會覆寫；人工內容請寫在前面各章。

## 這章要解決的問題

拍板時常被問：這個結論的依據在哪？是哪一版？能不能自己重跑一次？

## 路線圖

1. 可以直接打開的成品
2. 真瀏覽器驗收紀錄與截圖
3. 九階段狀態與定版家報告

## 內文

### 可以直接打開的成品

這個資料夾連同成品與驗收紀錄，叫做 **拍板包**；整包可以離線打開。

| 成品 | 說明 | 大小與指紋 |
|---|---|---|
"""]
    for x in arts:
        L.append(f"| [{x['title']}](../{x['href']}) | {x['desc']} | {x['meta']} |\n")
    for t, h, d in links:
        L.append(f"| [{t}](../{h}) | 定版家成品 | {d} |\n")
    L.append("\n> [!ASK] 你可能會想說\n> 截圖跟我自己打開看到的不一樣怎麼辦？\n> 截圖是發布當下的 **真瀏覽器驗收** 結果；以自己打開 `play.html` 看到的為準，有差異就重跑 `review_build --run-checks`。\n\n")
    L.append("### 真瀏覽器驗收\n\n")
    for label, rep in checks.items():
        if not rep:
            L.append(f"**{label}**：尚未驗收（`review_build --run-checks`）\n\n")
            continue
        res = rep.get("results") or rep.get("checks") or []
        L.append(f"**{label}**：{sum(1 for r in res if r.get('ok'))}/{len(res)} PASS · {rep.get('browser', '')}" + (f" · FPS {rep['fps']}" if rep.get("fps") else "") + "\n\n")
        L.append("| 結果 | 檢查項 |\n|---|---|\n" + "".join(f"| {'✓' if r.get('ok') else '✗'} | {r.get('name', '')} |\n" for r in res) + "\n")
        for s in rep.get("review_shots", []):
            L.append(f"![{s}](../checks/{s})\n\n")
    L.append("### 九階段狀態\n\n| 階段 | 名稱 | 定版家 |\n|---|---|---|\n" + "".join(f"| {no} | {n} | {'✓ 有產出' if ok else '— 尚無'} |\n" for no, n, ok in rows) + "\n")
    if reports:
        L.append("### 定版家報告（時點快照）\n\n" + "".join(f"- [{t}](../{h})（{d}）\n" for t, h, d in reports) + "\n")
    L.append("""## 常見誤解

> [!MYTH] 大家通常會以為
> 拍板包是每次建置都會更新的工作目錄。但其實拍板包只在送審前發布一次；工作中的中間檔在 output/，拍板包反映的是送審當下的狀態。

## 重點回顧

- 每個拍板依據都能點開、能重跑、能追到來源。
- 截圖是發布當下的真瀏覽器驗收結果。
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
    a = ap.parse_args()
    repo = pathlib.Path(a.repo).resolve()
    data, out = repo / "data" / a.domain / a.slug, repo / "output" / a.domain / a.slug
    if not data.is_dir():
        emit(False, error={"code": "BAD_INPUT", "message": f"找不到定版家 {data}"})
        return 2
    log = run_checks(repo, out) if a.run_checks else []
    rv = data / "review"
    (rv / "checks").mkdir(parents=True, exist_ok=True)
    for old in (rv / "checks").glob("*"):
        old.unlink()
    files: list[tuple[pathlib.Path, str]] = []
    gc = data / "proto" / "game-config.json"
    game = json.loads(gc.read_text(encoding="utf-8")).get("game") if gc.is_file() else a.slug
    arts = []
    # ⑦ 試玩單檔
    single = out / "game" / "pixi-client" / "single" / "index.html"
    if single.is_file():
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
        files.append((rv / "gdd-overview.html", gdd_src.relative_to(repo).as_posix()))
    # ⑥⑦ 驗收
    checks = {"⑥ 驗證台（browser_check）": collect_check(out / "proto" / "browser-check" / "browser-check.json", "proto", rv, files),
              "⑦ 試玩版（smoke）": collect_check(out / "game" / "pixi-client" / "smoke-shots" / "smoke.json", "stage", rv, files)}
    # 超額且 auto → gdd 降 lite
    total = lambda: sum(f.stat().st_size for f, _ in files)  # noqa: E731
    if total() > REVIEW_KB * 1024 and gdd_src and a.quality == "auto" and quality == "standard":
        quality = "lite"
        (rv / "gdd-overview.html").write_text(gdd_selfcontained(gdd_src, quality), encoding="utf-8")
    if gdd_src:
        g = rv / "gdd-overview.html"
        arts.insert(0, {"href": "gdd-overview.html", "title": "② 素材總覽（圖文規格）", "desc": f"縮圖內嵌自足版（{quality}）",
                        "meta": f"{kb(g.stat().st_size)} · sha {sha16(g)}"})
    links = []
    for t, rel_, d in (("⑤ 機率規格書", "prob/prob-spec.html", "prob-spec.html（ps_lint 戳記）"), ("⑥ 機率驗證台", "proto/index.html", "L1 精算 / L2 蒙地卡羅 / Go 對照 / 演出"),
                       ("④ 快測報告", None, "quicktest/qt-report/"), ("⑧ 工程交付單", "game/handoff.md", "handoff.md")):
        if rel_ is None:
            hit = next(iter(sorted((data / "quicktest" / "qt-report").glob("*.md"))), None) if (data / "quicktest" / "qt-report").is_dir() else None
            rel_ = hit.relative_to(data).as_posix() if hit else None
        if rel_ and (data / rel_).is_file():
            links.append((t, "../" + rel_, f"{d} · {kb((data / rel_).stat().st_size)}"))
    when = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    (rv / "index.html").write_text(build_index(game, a.slug, when, stage_rows(data), arts, checks, links), encoding="utf-8")
    files.append((rv / "index.html", "review_build"))
    auto = (f"- 發布：{when}（review_build；契約 v3.3）\n"
            + "".join(f"- {x['title']}：`{x['href']}`（{x['meta']}）\n" for x in arts)
            + "".join(f"- {k}：" + (f"{sum(1 for r in (v.get('results') or v.get('checks') or []) if r.get('ok'))}/{len(v.get('results') or v.get('checks') or [])} PASS\n" if v else "尚未驗收\n") for k, v in checks.items()))
    book_dir = next((p.parent for p in sorted(rv.glob("*/book.yaml"))), None)
    book_info = None
    if book_dir and (HERE.parents[1] / "ark-book" / "scripts" / "book_build.py").is_file():
        # 拍板書（ark-book 架構）：人寫的序與 R-x 章保留；附錄每次重產；index.html = book_build 輸出
        write_appendix(book_dir, game, when, arts, checks, links, report_links(data), stage_rows(data))
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
    bad = [f.name for f in rv.rglob("*") if f.is_file() and f.suffix.lower() in BAN]
    tot = sum(f.stat().st_size for f in rv.rglob("*") if f.is_file())
    if bad or tot > REVIEW_KB * 1024:
        emit(False, {"total_kb": tot // 1024, "banned": bad}, {"code": "GATE_BLOCKED", "message": f"拍板包 {tot // 1024} KB（上限 {REVIEW_KB}）或含禁止檔 {bad}"})
        return 1
    man = {"schema": "review-manifest/1", "contract": "3.3", "slug": a.slug, "game": game, "generated_at": when, "gdd_quality": quality if gdd_src else None,
           "files": [{"path": f.relative_to(rv).as_posix(), "sha256_16": sha16(f), "bytes": f.stat().st_size, "source": s} for f, s in files if f.name != "REVIEW.md"],
           "total_bytes": tot}
    (rv / "review-manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    emit(True, {"review": rv.relative_to(repo).as_posix(), "total_kb": tot // 1024, "files": len(man["files"]) + 2, "gdd_quality": man["gdd_quality"],
                "checks": {k: (bool(v) and bool(v.get("pass"))) for k, v in checks.items()}, "run_checks": log, "book": book_info,
                "delivery": f"review_build {a.slug}｜{kb(tot)} / {REVIEW_KB // 1024} MB｜開 {rv.relative_to(repo).as_posix()}/index.html"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
