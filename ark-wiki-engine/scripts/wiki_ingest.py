"""wiki_ingest.py — 本地 Wiki Ingest 腳本（增強版）

用途：從 raw/ 讀取原始文件，產出 wiki/ 頁面骨架（含 frontmatter）。
支援單檔、batch（整個目錄）、auto-detect category。
不依賴 team MCP，ark-agent 可直接呼叫。

使用方式：
    # 單檔 ingest
    python scripts/wiki_ingest.py \\
        --source knowledge/raw/architecture.md \\
        --wiki_dir knowledge/wiki

    # 整個目錄 batch ingest
    python scripts/wiki_ingest.py \\
        --source knowledge/raw/ \\
        --wiki_dir knowledge/wiki \\
        --batch

    # 指定 category + page_name
    python scripts/wiki_ingest.py \\
        --source knowledge/raw/api-design.md \\
        --wiki_dir knowledge/wiki \\
        --category dev-guide \\
        --page_name api-design-patterns

    # 預覽模式
    python scripts/wiki_ingest.py \\
        --source knowledge/raw/notes.md \\
        --wiki_dir knowledge/wiki \\
        --dry_run
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _wikilib import ErrorCode, emit_json, parse_frontmatter, strip_frontmatter  # noqa: E402
import wiki_guard  # noqa: E402
import wiki_taxonomy  # noqa: E402

# ── stdout／stderr 分工 ────────────────────────────────────────
# **stdout 只放機器契約（--json 的 JSON）**，人看的進度一律 stderr。
# 實測踩過：update_index/update_log 的 `[index]`/`[log]` 進度行印在 stdout，
# 讓 `--json` 的輸出前面多兩行 → agent 端 json.loads 直接炸。
#
# ── v3 硬規則管線（順序寫死在 ingest_file，任何參數都不能調換）──────
#
#   guard scan ──違規→ quarantine + GUARD_BLOCKED（不落盤）
#      → 骨架產出（trust 依 raw frontmatter，預設 llm-distilled / approved=false / seedling）
#      → taxonomy check（--schema 給時；未知 tag → TAG_NOT_IN_WHITELIST，不落盤）
#      → 落盤 wiki/{category}/{page}.md
#      → index.md + log.md（`date | op | page | trust | by | note`）
#      → wiki_index.py build（--no-index 可關，僅 batch 中間步驟用）
#
# v2 的 SKILL.md 宣告「guard-first ingest 不可跳過」，但 wiki_ingest.py 對
# wiki_guard / wiki_taxonomy 是**零呼叫**（F-6）—— 那條規則只存在於 SOP 文字，
# 靠 LLM 記得執行。deterministic 的守門必須寫在腳本裡。


# ── Category 自動偵測 ────────────────────────────────────────

CATEGORY_KEYWORDS = {
    "architecture": ["架構", "architecture", "系統設計", "system design", "模組", "module"],
    "dev-guide": ["開發", "coding", "api", "實作", "implementation", "規範", "standard"],
    "operations": ["維運", "ops", "deploy", "部署", "監控", "monitor", "SOP"],
    "decisions": ["決策", "decision", "ADR", "選型", "trade-off"],
    "learnings": ["學習", "踩坑", "bug", "修復", "lesson", "pitfall"],
    "meetings": ["會議", "meeting", "摘要", "紀錄", "minutes"],
}


def detect_category(content: str, filename: str) -> str:
    """根據內容和檔名自動偵測 category。"""
    text = (content[:500] + filename).lower()
    scores = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > 0:
            scores[cat] = score
    if scores:
        return max(scores, key=scores.get)
    return ""


# ── Frontmatter 建立 ─────────────────────────────────────────

def extract_title_from_content(content: str, filename: str) -> str:
    """從內容第一個 # 標題或檔名取得 title。"""
    match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return filename.replace("-", " ").replace("_", " ").title()


def detect_type(content: str) -> str:
    """依內容偵測 page type。"""
    lower = content[:1000].lower()
    if any(w in lower for w in ["api", "endpoint", "request", "response"]):
        return "source"
    if any(w in lower for w in ["架構", "architecture", "設計", "design"]):
        return "concept"
    if any(w in lower for w in ["比較", "vs", "comparison", "trade-off"]):
        return "comparison"
    if any(w in lower for w in ["總覽", "overview", "簡介"]):
        return "overview"
    return "source"


def warn_if_not_bucketed(rel: str) -> str | None:
    """素材沒放在 `raw/{source-id}/` 底下 → 回一句警告（不擋）。

    ## 契約來源

    **ADR-009（accepted）**：`knowledge/{domain}/raw/{source-id}/`，
    與 `sources.yaml` 的 `id` 恆等；**`local/` 為保留 id**（agent 自產，
    不出現在註冊表）。見 `kb-unified-sync-design-doc.md`。

    ## 為什麼是警告而不是拒絕

    拒絕會擋住 agent 的正常工作，而它當下沒有辦法自己修（素材已經寫好了）。
    警告讓「放錯層」在 ingest 當下就看得見，而不是等下游的 provenance
    守門在**別人的 repo** 裡紅。

    ## 為什麼需要它（實證，不是預防性設計）

    2026-09-15~16 **一天之內發生兩次**：agent 蒸餾完把素材寫在
    `raw/` 直接底下（`package-dev` 一次、`shared` 一次），
    而 `shared/raw/local/` 本來就存在 —— 不是沒有 bucket，是不知道要用。
    兩次都讓消費端 repo 的守門紅、擋住發版。

    > 💡 判準：**契約寫在 ADR 裡，而產出端沒有任何提示** ——
    > 那個契約就只存在於「讀過那份 ADR 的人」腦中。
    """
    if not rel.startswith("raw/"):
        return None
    rest = rel[len("raw/"):]
    if "/" in rest:
        return None
    return (f"[ingest] ⚠️ 素材沒放在 bucket 底下：sources 會寫成 {rel!r}。"
            f" 依 ADR-009 應為 raw/{{source-id}}/…（agent 自產請用 raw/local/）。"
            f" 下游的 provenance 守門會擋。")


def relative_source(source_path: Path, domain_root: Path) -> str:
    """`sources:` 要寫的路徑 —— **相對 domain root**，不是呼叫端給的原字串。

    🔴 在此之前是 `str(source_path)`：呼叫端給什麼就寫什麼。
    於是同一份素材，用不同的呼叫方式 ingest 會得到不同的 `sources:`：

    | 呼叫端給 | 舊寫出 | 正確 |
    |---|---|---|
    | `knowledge/pkg/raw/local/a.md` | `knowledge/pkg/raw/local/a.md` | `raw/local/a.md` |
    | `/abs/path/knowledge/pkg/raw/local/a.md` | `/abs/path/…`（綁死某台機器） | 同上 |

    後果不只是難看：下游用 `sources:` 的上游路徑**取交集**判斷「互補型重複」
    （兩頁講同一主題但內容互補時相似度反而極低，只有共同上游抓得到）——
    形狀不一致的值永遠交集不到。而絕對路徑還會綁死某台機器。

    > 💡 這與 `ark_team_agent.team_mcp` 在 **1.7.26** 修過的是同一個病
    > （當時修了 203 頁的 `raw//home/…` 黏合）。修法也一樣：
    > **接受多種輸入形狀的入口，輸出必須正規化成一種。**

    ⚠️ 素材不在 domain root 底下時**不靜默** —— 回檔名並在 stderr 警告，
    因為那通常代表呼叫端傳錯了 `--wiki_dir`。

    ⚠️ 本函式**只負責正規化，不出聲** —— 沒放進 source-id bucket 的提醒
    由 `warn_if_not_bucketed()` 單一實作（ADR-009）。
    """
    try:
        rel = source_path.resolve().relative_to(domain_root.resolve()).as_posix()
    except ValueError:
        print(f"[ingest] ⚠️ 素材不在 domain root 底下，sources 退回檔名："
              f"source={source_path} domain_root={domain_root}", file=sys.stderr)
        return source_path.name

    # ⚠️ bucket 提醒**不在這裡** —— 由 warn_if_not_bucketed() 單一實作，
    #    在 build_wiki_page 呼叫。2026-09-16 一度兩處各寫一份，
    #    同一次 ingest 印了兩則重複警告（兩個 session 各自做了同一件事）。
    return rel


def _extract_fallback_tags(content: str, limit: int = 3) -> list[str]:
    """raw 無 frontmatter tags 時的 fallback：從 CATEGORY_KEYWORDS 詞邊界比對抽候選。

    🔴 F-2（aidev-agent 回報）：舊版 `kw.lower() in content.lower()` 是**子字串命中**，
    會把檔名引用（`-sop.md` 的 "sop"）、說明文字（"摘要"）誤抽成 tag →
    撞白名單讓 ingest 被擋。改法：

    1. **只掃正文**（strip frontmatter 後的 body），不掃檔名 → 消檔名污染。
    2. **英文/數字詞用 `\\b` 詞邊界** → 'api' 不再命中 'rapid'/'apiary'。
    3. **CJK 詞需出現在標題行**（`#` 開頭或首行）才算 —— CJK 無詞邊界概念，
       限定在標題（主題性最強）可擋掉說明語境裡的 "摘要"/"踩坑" 誤抽。

    取捨：寧可少抽也別誤抽（回報明確：誤抽直接撞白名單擋 ingest，比漏抽更糟）。
    漏抽時 raw 可自帶 frontmatter tags（F-1 路徑）或人工 propose 補。
    """
    body = strip_frontmatter(content)
    body_lower = body.lower()
    # 標題行集合（# 開頭 或 第一行）供 CJK 關鍵字判定主題性
    title_lines = "\n".join(
        ln for ln in body.splitlines()
        if ln.lstrip().startswith("#")
    ) or (body.splitlines()[0] if body.splitlines() else "")

    tags: list[str] = []
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in tags:
                continue
            kw_lower = kw.lower()
            is_ascii = kw.isascii()
            if is_ascii:
                # 英文/數字：詞邊界比對（kw 可能含空白如 "system design"，用 re.escape）
                if re.search(rf"\b{re.escape(kw_lower)}\b", body_lower):
                    tags.append(kw)
            else:
                # CJK：需在標題行出現才算（擋說明語境誤抽）
                if kw in title_lines:
                    tags.append(kw)
            if len(tags) >= limit:
                return tags
    return tags


def build_wiki_page(source_path: Path, page_name: str, category: str, content: str,
                    domain_root: Path) -> str:
    """產出含 frontmatter 的 wiki 頁面骨架。"""
    today = date.today().isoformat()
    title = extract_title_from_content(content, page_name)
    rel_source = relative_source(source_path, domain_root)
    _bucket_warn = warn_if_not_bucketed(rel_source)
    if _bucket_warn:
        print(_bucket_warn, file=sys.stderr)

    # 🔴 先讀 raw 自己的 frontmatter —— raw 有宣告就沿用，不自行推測改寫（aibi-agent 回報 P1）。
    raw_fm = parse_frontmatter(content) or {}

    # type：raw 有就沿用，無才用 detect_type 推測
    page_type = raw_fm.get("type") or detect_type(content)

    # tags：raw 有就沿用（含 CJK，不截斷）；無才用 CATEGORY_KEYWORDS fallback（詞邊界比對）
    raw_tags = raw_fm.get("tags")
    if isinstance(raw_tags, str):
        raw_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
    if raw_tags:
        tags = list(raw_tags)
    else:
        tags = _extract_fallback_tags(content)

    tags_str = ", ".join(tags) if tags else page_type

    # 🔴 trust/approved/status：ingest 產出是「骨架待填」的 LLM 蒸餾素材，
    # 一律 llm-distilled / approved false / seedling（對齊 BRAIN.md；aibi-agent 回報 P0）。
    # raw 若自帶更高信任（deterministic）也沿用其宣告，但預設保守。
    trust = raw_fm.get("trust") or "llm-distilled"
    approved = str(raw_fm.get("approved", "false")).lower()
    status = raw_fm.get("status") or "seedling"

    return f"""---
title: "{title}"
type: {page_type}
tags: [{tags_str}]
sources: [{rel_source}]
related: [overview]
created: {today}
updated: {today}
status: {status}
trust: {trust}
approved: {approved}
---

# {title}

> 萃取自 `{rel_source}`

<!-- LLM: 請依 source 內容填充以下章節 -->

## 概述

## 主要內容

## 相關頁面

"""


# ── Index / Log 更新 ─────────────────────────────────────────

def update_index(wiki_dir: Path, category: str, page_name: str, title: str) -> None:
    """將新頁面加入 index.md。"""
    # index.md 在 knowledge root（wiki_dir 的上層）
    index_path = wiki_dir.parent / "index.md"
    if not index_path.exists():
        # wiki_dir 本身也可能就是 knowledge root
        index_path = wiki_dir / ".." / "index.md"
        index_path = index_path.resolve()
    if not index_path.exists():
        return

    content = index_path.read_text(encoding="utf-8")
    link = f"- [[{page_name}]]"
    if page_name not in content:
        if category:
            section = f"### {category}"
            if section in content:
                content = content.replace(section, f"{section}\n{link} — {title}")
            else:
                content = content.rstrip() + f"\n\n{section}\n{link} — {title}\n"
        else:
            content = content.rstrip() + f"\n{link} — {title}\n"
        index_path.write_text(content, encoding="utf-8")
        print(f"  [index] 更新 {index_path}", file=sys.stderr)


def update_log(wiki_dir: Path, page_name: str, source_path: Path,
               trust: str = "deterministic", by: str = "unknown", note: str = "") -> None:
    """append log.md（append-only）。

    欄位固定為 `date | op | page | trust | by | note` —— `trust` 與 `by` 是 v3 新增：
    出了問題要能回答「這頁是誰、用什麼信任等級寫進來的」。
    """
    log_path = wiki_dir.parent / "log.md"
    if not log_path.exists():
        log_path = (wiki_dir / ".." / "log.md").resolve()
    today = date.today().isoformat()
    entry = (f"- **{today}** | ingest | `wiki/{page_name}.md` | {trust} | {by} | "
             f"{note or f'source={source_path}'}\n")

    if log_path.exists():
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)
    else:
        log_path.write_text(f"# Wiki 操作日誌\n\n{entry}", encoding="utf-8")
    print(f"  [log] 記錄 {log_path}", file=sys.stderr)


# ── 核心邏輯 ─────────────────────────────────────────────────

def _quarantine_source(source_path: Path, findings: list[dict]) -> Path:
    """把違規來源移到 raw/_quarantine/（raw 目錄推定為 source 的所在目錄）。"""
    return wiki_guard.quarantine(source_path, findings, source_path.parent)


def ingest_file(source_path: Path, wiki_dir: Path, category: str, page_name: str,
                dry_run: bool, *, no_guard: bool = False, schema: Path | None = None,
                by: str = "unknown") -> dict:
    """Ingest 單一檔案。回傳結果 dict（步驟順序寫死，不可由參數調換）。"""
    if not source_path.exists():
        return {"file": str(source_path), "status": "skip", "reason": "not_found"}
    if source_path.suffix not in (".md", ".txt", ".rst", ".yaml", ".yml", ".json"):
        return {"file": str(source_path), "status": "skip",
                "reason": f"unsupported_suffix:{source_path.suffix}"}

    content = source_path.read_text(encoding="utf-8", errors="replace")

    # ── 步驟 1：guard（第一道，永遠先跑）
    findings = wiki_guard.scan_text(content)
    if findings and not no_guard:
        dest = None if dry_run else _quarantine_source(source_path, findings)
        return {"file": str(source_path), "status": "blocked",
                "code": ErrorCode.GUARD_BLOCKED, "findings": findings,
                "quarantined_to": str(dest) if dest else None}
    guard_note = "no-guard" if (findings and no_guard) else ""

    if not page_name:
        page_name = source_path.stem.lower().replace("_", "-").replace(" ", "-")
    if not category:
        category = detect_category(content, source_path.name)
    out_dir = wiki_dir / category if category else wiki_dir
    out_path = out_dir / f"{page_name}.md"
    if out_path.exists():
        return {"file": str(source_path), "status": "skip", "reason": "already_exists",
                "page": str(out_path)}

    # ── 步驟 2：骨架
    # domain root = wiki_dir 的上層（`index.md` 與 `raw/` 都在那一層）
    wiki_content = build_wiki_page(source_path, page_name, category, content,
                                   wiki_dir.parent)

    # ── 步驟 3：taxonomy（在落盤之前 —— 擋下來的頁面不能留在 wiki/）
    if schema is not None:
        whitelist = wiki_taxonomy.load_whitelist(schema)
        tags = parse_frontmatter(wiki_content).get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        unknown = sorted(t for t in tags if t not in whitelist)
        if unknown:
            return {"file": str(source_path), "status": "blocked",
                    "code": ErrorCode.TAG_NOT_IN_WHITELIST, "unknown_tags": unknown,
                    "hint": "用 wiki_taxonomy.py propose 提案，不要自創 tag"}

    if dry_run:
        return {"file": str(source_path), "status": "dry_run", "page": str(out_path),
                "category": category}

    # ── 步驟 4：落盤
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_text(wiki_content, encoding="utf-8")

    # ── 步驟 5：index.md + log.md
    title = extract_title_from_content(content, page_name)
    # trust 對齊頁面實際值（build_wiki_page 依 raw frontmatter 決定；預設 llm-distilled）
    page_trust = parse_frontmatter(wiki_content).get("trust", "llm-distilled")
    update_index(wiki_dir, category, page_name, title)
    update_log(wiki_dir, page_name, source_path, trust=page_trust, by=by,
               note=guard_note)
    if guard_note:
        print(f"  ⚠️  --no-guard：{source_path} 有 {len(findings)} 項 guard 違規仍被寫入"
              f"（已在 log.md 記 no-guard 以供稽核）", file=sys.stderr)
    return {"file": str(source_path), "status": "ok", "page": str(out_path),
            "category": category, "trust": page_trust, "by": by,
            "guard_bypassed": bool(guard_note)}


def run_index_build(wiki_dir: Path, tokenizer: str | None = None) -> tuple[bool, str | None]:
    """跑 wiki_index.py build 子進程。回傳 (成功, 失敗原因)。

    🔴 F-3（aidev-agent 回報）：舊版只記 `index_built = returncode==0`，
    失敗時原因被 `capture_output` 吞掉、payload 仍 ok:true、exit 0 → 索引靜默沒建，
    下游無從判斷。改：失敗時接住 stderr 當 index_error，交 main 決定 partial 狀態。
    """
    cmd = [sys.executable, str(Path(__file__).parent / "wiki_index.py"),
           "build", "--wiki_dir", str(wiki_dir)]
    if tokenizer:
        cmd += ["--tokenizer", tokenizer]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode == 0:
        return True, None
    err = (proc.stderr or proc.stdout or "").strip()
    return False, err[-500:] or f"wiki_index build 失敗（exit={proc.returncode}）"


def main() -> None:
    p = argparse.ArgumentParser(description="Wiki Ingest v3 — guard-first 骨架產出")
    p.add_argument("--source", required=True, help="來源檔案或目錄")
    p.add_argument("--wiki_dir", required=True, help="目標 wiki/ 目錄")
    p.add_argument("--category", default="", help="子目錄分類（空=自動偵測）")
    p.add_argument("--page_name", default="", help="輸出頁面名稱（僅單檔模式）")
    p.add_argument("--batch", action="store_true", help="目錄 batch 模式")
    p.add_argument("--dry_run", action="store_true", help="預覽，不寫入")
    p.add_argument("--schema", default="", help="schema.md 路徑（給了才做 tags 白名單守門）")
    p.add_argument("--by", default="unknown", help="寫入 log.md 的執行者")
    p.add_argument("--tokenizer", default="", choices=["", "auto", "jieba", "bigram"],
                   help="索引分詞器（鎖定給 wiki_index build，確保 build/query 一致；空=用 build 預設 auto）")
    p.add_argument("--no-guard", dest="no_guard", action="store_true",
                   help="繞過 guard（會在 stderr 警告並在 log.md 記 no-guard）")
    p.add_argument("--no-index", dest="no_index", action="store_true",
                   help="不在結束時重建 .index/（batch 中間步驟用）")
    p.add_argument("--json", action="store_true", help="機器可讀輸出")
    args = p.parse_args()

    source = Path(args.source)
    wiki_dir = Path(args.wiki_dir)
    if not wiki_dir.exists():
        emit_json({"ok": False,
                   "error": {"code": ErrorCode.WIKI_DIR_NOT_FOUND,
                             "msg": f"目錄不存在：{wiki_dir}"}}, 2)
    schema = Path(args.schema) if args.schema else None
    if schema is not None and not schema.exists():
        emit_json({"ok": False,
                   "error": {"code": ErrorCode.SCHEMA_NOT_FOUND,
                             "msg": f"schema 不存在：{schema}"}}, 2)

    if args.batch or source.is_dir():
        if not source.is_dir():
            emit_json({"ok": False, "error": {"code": ErrorCode.BAD_ARGUMENTS,
                                              "msg": f"--batch 需要目錄：{source}"}}, 2)
        files = sorted(f for f in source.rglob("*") if f.is_file())
    else:
        files = [source]

    results = [ingest_file(f, wiki_dir, args.category,
                           args.page_name if len(files) == 1 else "",
                           args.dry_run, no_guard=args.no_guard, schema=schema,
                           by=args.by)
               for f in files]

    blocked = [r for r in results if r["status"] == "blocked"]
    created = [r for r in results if r["status"] == "ok"]

    # ── 步驟 6：索引（有實際落盤才重建）
    index_built = False
    index_error = None
    if created and not args.no_index and not args.dry_run:
        index_built, index_error = run_index_build(wiki_dir, tokenizer=args.tokenizer or None)

    # ── 狀態判定（F-3：index_built 與 ok/exit code 不再解耦）
    #   blocked（guard/taxonomy 擋下）        → ok:false, exit 1
    #   partial（落盤成功但索引 build 失敗）    → ok:false, exit 3, 帶 index_error
    #   全成功                                → ok:true,  exit 0
    index_failed = bool(created) and not args.no_index and not args.dry_run and not index_built
    if blocked:
        status, exit_code = "blocked", 1
    elif index_failed:
        status, exit_code = "partial", 3
    else:
        status, exit_code = "ok", 0

    payload = {"ok": status == "ok", "action": "ingest", "status": status,
               "created": len(created), "blocked": len(blocked),
               "index_built": index_built, "results": results}
    if index_error:
        payload["index_error"] = index_error
    if args.json:
        emit_json(payload, exit_code)

    for r in results:
        mark = {"ok": "[OK]", "blocked": "🚧", "skip": "[SKIP]", "dry_run": "[DRY]"}[r["status"]]
        extra = r.get("code") or r.get("reason") or r.get("page", "")
        print(f"  {mark} {r['file']} {extra}")
    idx_msg = "已重建" if index_built else ("建置失敗" if index_failed else "未重建")
    print(f"\n{'✅' if status == 'ok' else '⚠️'} 建立 {len(created)}｜擋下 {len(blocked)}"
          f"｜索引{idx_msg}")
    if index_error:
        print(f"  ❌ 索引錯誤：{index_error}", file=sys.stderr)
    if exit_code:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
