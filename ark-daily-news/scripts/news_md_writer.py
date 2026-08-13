#!/usr/bin/env python3
"""news_md_writer — 結構化新聞 JSON → raw Markdown（Content 軌）。

MD 是 source of truth，HTML 只是渲染視圖。這支腳本負責前者。

## 落點與命名

```
knowledge/raw/digest/<issue>/<date>.md
```

與程式管線（ninja `digest/raw_writer.py`）**同一個目錄樹與 frontmatter 契約** ——
wiki ingest 與下游 agent 只需要認得一種形狀。舊版的 `raw/news-daily-{date}.md`
會讓同一種東西有兩個名字，ingest 端遲早漏掉其中一種。

## 不覆蓋既有檔

同一天同一刊可能已由排程管線寫過。預設**拒絕覆蓋**並回報，要蓋得明確給 `--force`
—— 靜默覆蓋會讓當天的收集素材無聲消失，而 raw 是唯一保留「被 max_items 砍掉的
條目」的地方。

## Guard 前置

素材來自外部網頁時，ingest 前必須過 `ark-wiki-engine` 的 `wiki_guard`
（提示注入／隱形字元／隱藏樣式）。本腳本在寫檔前呼叫它；找不到 guard 時
**在 frontmatter 標記 `guard: unavailable` 並警告**，不靜默跳過 ——
下游要看得出這份素材沒被檢查過。

## 用法

    news_md_writer.py --json items.json --issue tech
    news_md_writer.py --json items.json --issue market --date 2026-08-13 --dry-run

輸入 JSON 為 list[dict]，欄位見 SKILL.md 步驟一：
topic / title / source / url / news_date / what / why / summary / urgency / action / tags
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_TZ_TPE = timezone(timedelta(hours=8))

#: 與程式管線共用的刊別代碼。新增刊別時兩邊都要加，否則 wiki ingest 的
#: 路徑對照會漏。
ISSUES = ("tech", "market", "product")

_URGENCY = {"立即", "關注", "一般"}


def find_project_root(start: Path | None = None) -> Path:
    """以哨兵檔定位專案根（`team.yaml` 或 `knowledge/`）。

    不用固定層數的 `.parent` 鏈 —— 各 agent 的 working_directory 深度不同，
    寫死層數在某個 agent 下會對、在另一個下會靜默寫到別的地方。
    """
    cur = (start or Path.cwd()).resolve()
    for p in [cur, *cur.parents]:
        if (p / "team.yaml").exists() or (p / "knowledge").is_dir():
            return p
    return cur


def normalize(item: dict[str, Any], *, date: str) -> dict[str, Any]:
    """補齊欄位並正規化，讓下游不必到處做 `or ""`。

    `news_date` 缺漏時用出刊日填 —— 但**不覆寫模型給的值**：
    模型給的日期是它從內文讀到的事件日期，比出刊日精確。
    """
    urgency = str(item.get("urgency") or "一般").strip()
    if urgency not in _URGENCY:
        urgency = "一般"
    tags = []
    for t in item.get("tags") or []:
        if isinstance(t, dict):
            tags.append(f"{t.get('icon', '')} {t.get('text', '')}".strip())
        elif t:
            tags.append(str(t))
    return {
        "topic": str(item.get("topic") or "未分類").strip(),
        "title": str(item.get("title") or "").strip(),
        "source": str(item.get("source") or "").strip(),
        "url": str(item.get("url") or "").strip(),
        "news_date": str(item.get("news_date") or date).strip(),
        "what": str(item.get("what") or "").strip(),
        "why": str(item.get("why") or "").strip(),
        "summary": str(item.get("summary") or "").strip(),
        "urgency": urgency,
        "action": (str(item.get("action")).strip() if item.get("action") else None),
        "tags": tags,
    }


def validate(items: list[dict[str, Any]]) -> list[str]:
    """回傳問題清單（空 list 代表通過）。

    只擋「缺了就沒有意義」的欄位。缺 `why` 的新聞就只是轉述 ——
    日報的價值在影響分析，不在轉貼標題。
    """
    問題: list[str] = []
    for i, it in enumerate(items, 1):
        for 欄位 in ("title", "what", "why"):
            if not it.get(欄位):
                問題.append(f"第 {i} 則缺少必要欄位 `{欄位}`")
        if it.get("url") and not str(it["url"]).startswith(("http://", "https://")):
            問題.append(f"第 {i} 則的 url 不是 http(s)：{it['url']}")
    return 問題


def render_md(items: list[dict[str, Any]], *, issue: str, date: str, guard: str) -> str:
    """渲染 raw MD 全文（frontmatter 契約與程式管線一致）。"""
    now = datetime.now(_TZ_TPE).isoformat()
    來源 = sorted({i["source"] for i in items if i["source"]})

    lines = [
        "---",
        f"title: {issue} 日報原始素材 · {date}",
        "type: digest-raw",
        f"issue_type: {issue}",
        f"date: {date}",
        f"collected: {len(items)}",
        f"sources: [{', '.join(來源)}]",
        f"generated_at: {now}",
        "generated_by: ark-news-daily",   # 與排程管線的產出區分，兩者形狀相同但來路不同
        f"guard: {guard}",
        f"tags: [digest, raw, {issue}]",
        "---",
        "",
        f"# {issue} 日報原始素材 · {date}",
        "",
        "> 由 `ark-news-daily`（kiro-cli 臨機路徑）產出。"
        f"蒸餾後的精華見 `knowledge/wiki/digest/{issue}/{date}.md`。",
        "",
        f"共 {len(items)} 則。",
        "",
    ]
    if guard != "pass":
        lines += [
            f"> ⚠️ **本檔未經 wiki_guard 檢查**（`guard: {guard}`）。"
            "素材若來自外部網頁，ingest 前請先手動跑 guard sweep。",
            "",
        ]

    for n, it in enumerate(items, 1):
        標題 = f"## {n}. {it['title']}"
        lines += [標題, ""]
        meta = [f"**分類**：{it['topic']}", f"**緊急度**：{it['urgency']}"]
        if it["source"]:
            meta.append(f"**來源**：{it['source']}")
        if it["news_date"]:
            meta.append(f"**日期**：{it['news_date']}")
        if it["url"]:
            meta.append(f"**連結**：{it['url']}")
        lines += meta + [""]
        lines += ["### 📋 發生了什麼", "", it["what"], ""]
        lines += ["### ⭐ 為什麼重要", "", it["why"], ""]
        if it["summary"]:
            lines += ["### 💡 一句話總結", "", it["summary"], ""]
        if it["action"]:
            lines += ["### 🎯 行動建議", "", it["action"], ""]
        if it["tags"]:
            lines += ["**標籤**：" + " ".join(f"`{t}`" for t in it["tags"]), ""]
        lines += ["---", ""]

    return "\n".join(lines)


def run_guard(path: Path, *, skill_root: Path | None = None) -> str:
    """對內容跑 `wiki_guard`。回傳 `pass` / `fail:…` / `unavailable`。

    找不到 guard 腳本時回 `unavailable` 而不是當作通過 ——
    「沒檢查」與「檢查過了」在下游是兩件事。
    """
    根 = skill_root or Path(__file__).resolve().parents[2]
    guard = 根 / "ark-wiki-engine" / "scripts" / "wiki_guard.py"
    if not guard.exists():
        return "unavailable"
    try:
        # 用 `scan <file>` 而非 `sweep --raw_dir <dir>`：
        # sweep 會把違規檔搬進 raw/_quarantine/，但我們是在**寫入前**檢查暫存檔，
        # 讓它去搬一個還不該存在的檔案只會製造垃圾。scan 只回報，由本腳本決定處置。
        r = subprocess.run(
            [sys.executable, str(guard), "scan", str(path)],
            capture_output=True, text=True, timeout=60,
        )
    except Exception as e:
        return f"unavailable:{type(e).__name__}"
    if r.returncode == 0:
        return "pass"
    訊息 = (r.stdout + r.stderr).strip().splitlines()
    return "fail:" + (訊息[-1][:120] if 訊息 else f"exit {r.returncode}")


def write(
    items: list[dict[str, Any]],
    *,
    issue: str,
    date: str | None = None,
    root: Path | None = None,
    force: bool = False,
    guard: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """主流程。一律回傳 result dict，不拋例外。"""
    if issue not in ISSUES:
        return {"status": "error", "message": f"未知刊別 '{issue}'，可用: {list(ISSUES)}"}

    today = date or datetime.now(_TZ_TPE).strftime("%Y-%m-%d")
    正規化 = [normalize(i, date=today) for i in items]
    問題 = validate(正規化)
    if 問題:
        return {"status": "error", "message": "輸入未通過檢查", "issues": 問題}

    專案根 = root or find_project_root()
    out = 專案根 / "knowledge" / "raw" / "digest" / issue / f"{today}.md"

    if out.exists() and not force:
        return {
            "status": "error",
            "message": f"{out} 已存在（可能是排程管線今天已寫過）。確定要覆蓋請加 --force",
            "path": str(out),
        }

    # guard 先對「內容」跑：寫進去才檢查等於已經污染了目標目錄
    狀態 = "skipped"
    if guard:
        暫存 = out.parent / f".{today}.guardcheck.md"
        try:
            暫存.parent.mkdir(parents=True, exist_ok=True)
            暫存.write_text(render_md(正規化, issue=issue, date=today, guard="pending"), encoding="utf-8")
            狀態 = run_guard(暫存)
        finally:
            暫存.unlink(missing_ok=True)
        if 狀態.startswith("fail"):
            return {"status": "error", "message": f"wiki_guard 未通過：{狀態}", "path": str(out)}

    md = render_md(正規化, issue=issue, date=today, guard=狀態)
    if dry_run:
        return {
            "status": "dry_run", "path": str(out), "count": len(正規化),
            "guard": 狀態, "bytes": len(md.encode()), "preview": md[:400],
        }

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    return {"status": "success", "path": str(out), "count": len(正規化), "guard": 狀態}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="news_md_writer.py", description="結構化新聞 → raw MD")
    p.add_argument("--json", type=Path, help="結構化新聞 JSON（list[dict]）；省略則讀 stdin")
    p.add_argument("--issue", default="tech", choices=list(ISSUES))
    p.add_argument("--date", help="出刊日 yyyy-mm-dd（預設今天，台北時區）")
    p.add_argument("--root", type=Path, help="專案根（預設以 team.yaml / knowledge 哨兵搜尋）")
    p.add_argument("--force", action="store_true", help="覆蓋既有檔案")
    p.add_argument("--no-guard", action="store_true", help="跳過 wiki_guard（僅限除錯）")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    try:
        原始 = json.loads(args.json.read_text(encoding="utf-8")) if args.json else json.load(sys.stdin)
    except Exception as e:
        print(json.dumps({"status": "error", "message": f"JSON 讀取失敗: {e}"}, ensure_ascii=False))
        return 1

    if isinstance(原始, dict):
        原始 = 原始.get("articles") or 原始.get("items") or []

    result = write(
        原始, issue=args.issue, date=args.date, root=args.root,
        force=args.force, guard=not args.no_guard, dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main())
