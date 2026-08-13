#!/usr/bin/env python3
"""render_news_html — raw MD（或結構化 JSON）→ 日報 HTML 卡片牆（View 軌）。

套 `assets/news-daily.html` 樣板，不自己寫 CSS —— 兩份 CSS 必然漂移。

## 為何預設吃 MD 而不是 JSON

MD 是 source of truth。從 MD 渲染代表「HTML 是 MD 的視圖」這件事在流程上成立：
MD 改了、重新渲染就會反映；反過來若各自從 JSON 生成，兩軌會各自演化，
最後沒人知道哪個是對的。JSON 入口保留給「還沒落檔就想先看看」的情況。

## 硬性條件：零外部請求

產出走 TG 檔案附件，讀者常在手機上離線開啟。樣板本身已無 CDN 與網路字體，
本腳本**在輸出前檢查**，發現外部資源直接報錯 —— 破圖的附件比沒有附件更糟，
因為讀者會以為是自己網路的問題。

## 用法

    render_news_html.py --md knowledge/raw/digest/tech/2026-08-13.md
    render_news_html.py --json items.json --issue tech --out /tmp/tech.html
"""
from __future__ import annotations

import argparse
import html as _html
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_TZ_TPE = timezone(timedelta(hours=8))

#: 三刊書脊色。與 ninja `digest/renderer.py` 一致 —— 兩條路徑產出的日報
#: 應該長得一樣，讀者不該從顏色看出它是排程跑的還是手動跑的。
SPINE = {"tech": "#0E7C7B", "market": "#C0392B", "product": "#1F3A5F"}
LABEL = {"tech": "科技日報", "market": "競品日報", "product": "競品日報"}
LABEL["product"] = "專案日報"

#: 緊急度 → chip class / 文字。「一般」不標：每張卡都掛一個灰標籤等於沒有標籤。
URGENCY_CHIP = {"立即": ("now", "立即"), "關注": ("week", "關注")}


def esc(s: Any) -> str:
    """逸出後才可放進 HTML。一個沒逸出的 `<` 會吃掉後面整段內容。"""
    return _html.escape(str(s or ""), quote=True)


def weekday_zh(date_str: str) -> str:
    """`2026-08-13` → `週四`；解析失敗回空字串（報頭少一項，不該讓渲染失敗）。"""
    try:
        y, m, d = (int(x) for x in date_str.split("-"))
        from datetime import date as D
        return "週" + "一二三四五六日"[D(y, m, d).weekday()]
    except (ValueError, IndexError):
        return ""


# ── MD 解析 ────────────────────────────────────────────────────────────────

def parse_md(text: str) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """解析 `news_md_writer.py` 產出的 raw MD。

    只解析本專案自己寫出的格式（章節標題固定），不做通用 Markdown 解析 ——
    通用解析器對這種結構化 MD 反而更容易靜默失敗。
    """
    fm: dict[str, str] = {}
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            for line in text[3:end].strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    fm[k.strip()] = v.strip()
            body = text[end + 4:]

    items: list[dict[str, Any]] = []
    # 以 `## N. 標題` 切則
    區塊 = re.split(r"\n##\s+\d+\.\s+", "\n" + body)
    for 塊 in 區塊[1:]:
        行 = 塊.splitlines()
        it: dict[str, Any] = {"title": 行[0].strip(), "tags": []}
        for key, 欄 in (("分類", "topic"), ("來源", "source"), ("緊急度", "urgency"),
                        ("日期", "news_date"), ("連結", "url")):
            m = re.search(rf"\*\*{key}\*\*：(.+)", 塊)
            if m:
                it[欄] = m.group(1).strip()
        for 標題, 欄 in (("📋 發生了什麼", "what"), ("⭐ 為什麼重要", "why"),
                        ("💡 一句話總結", "summary"), ("🎯 行動建議", "action")):
            m = re.search(rf"###\s+{標題}\n+(.+?)(?=\n###|\n\*\*標籤|\n---|\Z)", 塊, re.S)
            if m:
                it[欄] = m.group(1).strip()
        m = re.search(r"\*\*標籤\*\*：(.+)", 塊)
        if m:
            it["tags"] = re.findall(r"`([^`]+)`", m.group(1))
        items.append(it)
    return fm, items


# ── 渲染 ────────────────────────────────────────────────────────────────────

def render_card(it: dict[str, Any]) -> str:
    """單則 → 一張卡片。結構與樣板註解中的範例一致。"""
    chips = [f'<span class="chip kind">{esc(it.get("topic") or "事實")}</span>']
    緊急 = URGENCY_CHIP.get(str(it.get("urgency") or "").strip())
    if 緊急:
        chips.append(f'<span class="chip {緊急[0]}">{緊急[1]}</span>')

    url = str(it.get("url") or "")
    標題 = (
        f'<a href="{esc(url)}">{esc(it.get("title"))}</a>'
        if url.startswith(("http://", "https://"))
        else esc(it.get("title"))
    )

    行動 = f'<div class="action">{esc(it["action"])}</div>' if it.get("action") else ""
    來源 = esc(it.get("source") or "")
    日期 = esc(it.get("news_date") or "")
    出處 = f'<div class="relevance">→ {來源}{" · " + 日期 if 日期 else ""}</div>' if 來源 else ""
    tags = "".join(f'<span class="chip">{esc(t)}</span>' for t in it.get("tags") or [])
    摘要 = f'<p class="insight">{esc(it["summary"])}</p>' if it.get("summary") else ""

    return (
        f'<article class="card{" urgent" if 緊急 and 緊急[0] == "now" else ""}">'
        f'<div class="meta">{"".join(chips)}</div>'
        f'<h3>{標題}</h3>'
        f'<p class="summary">{esc(it.get("what"))}</p>'
        f'<p class="insight">{esc(it.get("why"))}</p>'
        f'{摘要}'
        f'<div class="foot">{行動}{出處}<div class="tags">{tags}</div></div>'
        f'</article>'
    )


def render_sections(items: list[dict[str, Any]]) -> tuple[str, int]:
    """依 `topic` 分欄目。回傳 `(html, 欄目數)`。

    空欄目整段不輸出 —— 留一個沒有卡片的標題會讓讀者以為內容漏了。
    """
    分組: dict[str, list[dict[str, Any]]] = {}
    for it in items:
        分組.setdefault(str(it.get("topic") or "未分類"), []).append(it)

    out = []
    for 名稱, 群 in 分組.items():
        cards = "".join(render_card(i) for i in 群)
        if not cards:
            continue
        out.append(
            f'<section class="section">'
            f'<h2 class="section-title">{esc(名稱)}'
            f'<span class="count">{len(群)} 則</span></h2>'
            f'<div class="cards">{cards}</div></section>'
        )
    return "\n".join(out), len(out)


def render(
    items: list[dict[str, Any]],
    *,
    issue: str,
    date: str,
    headline: str | None = None,
    collected: int | None = None,
    template: Path | None = None,
) -> str:
    """套樣板產出完整 HTML。"""
    tpl_path = template or Path(__file__).resolve().parents[1] / "assets" / "news-daily.html"
    tpl = tpl_path.read_text(encoding="utf-8")

    sections, 欄目數 = render_sections(items)
    行動 = [i["action"] for i in items if i.get("action")]
    actions = (
        '<section class="actions"><h2>今日行動彙總</h2><ol>'
        + "".join(f"<li>{esc(a)}</li>" for a in 行動)
        + "</ol></section>"
    ) if 行動 else ""

    # 沒給頭條就用第一則的一句話總結／標題 —— 空的報頭比較糟，
    # 但**不要編造**，只從既有內容取。
    頭條 = headline or next(
        (i.get("summary") or i.get("title") for i in items if i.get("summary") or i.get("title")),
        f"{date} 日報",
    )

    值 = {
        "LABEL": LABEL.get(issue, issue), "DATE": date, "WEEKDAY": weekday_zh(date),
        "ISSUE_ID": f"{issue}/{date}", "HEADLINE": esc(頭條),
        "SPINE": SPINE.get(issue, "#333"),
        "N_COLLECTED": str(collected if collected is not None else len(items)),
        "N_SELECTED": str(len(items)), "N_PUBLISHED": str(len(items)),
        "N_SECTIONS": str(欄目數), "SECTIONS": sections, "ACTIONS": actions,
    }
    out = tpl
    for k, v in 值.items():
        out = out.replace("{{%s}}" % k, v)

    # 樣板帶著給維護者看的說明與結構範例（約 3 KB）。那是給寫程式的人看的，
    # 不該跟著每一份日報送到讀者手上 —— 而且範例裡的示範卡片會被誤讀成當日內容。
    return strip_html_comments(out)


def strip_html_comments(text: str) -> str:
    """移除 HTML 註解。CSS 內的 `/* */` 不受影響（不同語法）。"""
    return re.sub(r"[ \t]*<!--.*?-->[ \t]*\n?", "", text, flags=re.S)


def check_offline(html_text: str) -> list[str]:
    """檢查零外部請求。回傳違規清單（空 list 代表通過）。

    只允許卡片標題的來源連結（`<a href>`）；`src=`、`@import`、`<script src>`
    一律不允許 —— 附件常在離線環境開啟，破圖比沒有附件更糟。
    """
    違規 = []
    if "@import" in re.sub(r"<!--.*?-->", "", html_text, flags=re.S):
        違規.append("含 @import（網路字體）")
    if re.search(r"<script[^>]+src=", html_text):
        違規.append("含 <script src>（外部腳本）")
    for m in re.finditer(r'\bsrc\s*=\s*"(https?://[^"]+)"', html_text):
        違規.append(f"含遠端資源 src={m.group(1)}")
    return 違規


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="render_news_html.py", description="raw MD → 日報 HTML")
    來源 = p.add_mutually_exclusive_group(required=True)
    來源.add_argument("--md", type=Path, help="news_md_writer.py 產出的 raw MD")
    來源.add_argument("--json", type=Path, help="結構化新聞 JSON")
    p.add_argument("--issue", choices=list(SPINE), help="刊別（MD 可從 frontmatter 讀）")
    p.add_argument("--date", help="出刊日（MD 可從 frontmatter 讀）")
    p.add_argument("--headline", help="頭條；省略則取第一則的一句話總結")
    p.add_argument("--template", type=Path, help="樣板路徑（預設 assets/news-daily.html）")
    p.add_argument("--out", type=Path, help="輸出路徑（預設 data/output/<date>/<issue>.html）")
    args = p.parse_args(argv)

    try:
        if args.md:
            fm, items = parse_md(args.md.read_text(encoding="utf-8"))
            issue = args.issue or fm.get("issue_type") or "tech"
            date = args.date or fm.get("date") or datetime.now(_TZ_TPE).strftime("%Y-%m-%d")
            collected = int(fm.get("collected") or len(items))
        else:
            raw = json.loads(args.json.read_text(encoding="utf-8"))
            items = raw.get("articles") or raw.get("items") or [] if isinstance(raw, dict) else raw
            issue = args.issue or "tech"
            date = args.date or datetime.now(_TZ_TPE).strftime("%Y-%m-%d")
            collected = len(items)
    except Exception as e:
        print(json.dumps({"status": "error", "message": f"讀取失敗: {e}"}, ensure_ascii=False))
        return 1

    if not items:
        print(json.dumps({"status": "error", "message": "沒有可渲染的項目"}, ensure_ascii=False))
        return 1

    out_html = render(items, issue=issue, date=date, headline=args.headline,
                      collected=collected, template=args.template)

    違規 = check_offline(out_html)
    if 違規:
        print(json.dumps(
            {"status": "error", "message": "產出含外部資源，附件離線開啟會破版", "violations": 違規},
            ensure_ascii=False, indent=2))
        return 1

    out = args.out or Path("data") / "output" / date / f"{issue}-{date}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(out_html, encoding="utf-8")
    print(json.dumps(
        {"status": "success", "path": str(out), "items": len(items),
         "bytes": len(out_html.encode()), "offline": True},
        ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
