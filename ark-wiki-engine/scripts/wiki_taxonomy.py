"""wiki_taxonomy.py — 受控詞彙表（tags 白名單）管理。

三件套整合的關鍵對接點：report_lint.py --wiki-schema 讀同一份白名單。
遵循 controlled taxonomy 原則：LLM 不得自創 tag，新概念走 propose → 人工 approve。

白名單存於 knowledge/{proj}/schema.md 的固定區塊（機器可解析）：

    ## tags 白名單
    - agent-architecture
    - skill-review
    ...

    ## tags 提案佇列
    | tag | 提案原因 | 提案者 | 日期 |

用法：
    python wiki_taxonomy.py list    --schema knowledge/proj/schema.md
    python wiki_taxonomy.py check   --schema schema.md page1.md page2.md
    python wiki_taxonomy.py propose --schema schema.md new-tag --reason "..." [--by agent-name]
    python wiki_taxonomy.py approve --schema schema.md new-tag        # 人工執行
    python wiki_taxonomy.py migrate --schema schema.md --wiki_dir knowledge/proj/wiki
        # 首次建表：統計存量頁面 tags 生成候選白名單（printed，人工確認後 approve）

Exit code：check 有未知 tag 回 1。
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _wikilib import ErrorCode, emit_error, emit_json  # noqa: E402

WHITELIST_HEADER = "## tags 白名單"
QUEUE_HEADER = "## tags 提案佇列"
TAG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _read(schema: Path) -> str:
    if not schema.exists():
        print(f"❌ schema 不存在：{schema}")
        sys.exit(1)
    return schema.read_text(encoding="utf-8")


def load_whitelist(schema: Path) -> set[str]:
    text = _read(schema)
    m = re.search(rf"{re.escape(WHITELIST_HEADER)}\s*\n((?:\s*-\s*.+\n?)+)", text)
    if not m:
        return set()
    return {re.sub(r"^`|`$", "", t.strip()) for t in re.findall(r"-\s*(\S+)", m.group(1))}


def page_tags(page: Path) -> list[str]:
    text = page.read_text(encoding="utf-8", errors="replace")
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return []
    tm = re.search(r"^tags:\s*\[([^\]]*)\]", m.group(1), re.MULTILINE)
    if tm:
        return [t.strip().strip('"').strip("'") for t in tm.group(1).split(",") if t.strip()]
    # 多行 list 格式
    tm = re.search(r"^tags:\s*\n((?:\s+-\s+.+\n?)+)", m.group(1), re.MULTILINE)
    if tm:
        return [t.strip() for t in re.findall(r"-\s+(\S+)", tm.group(1))]
    return []


def cmd_list(schema: Path) -> int:
    wl = load_whitelist(schema)
    if not wl:
        print("（白名單為空 —— 用 migrate 從存量生成候選，或 propose + approve 建立）")
        return 0
    for t in sorted(wl):
        print(t)
    print(f"\n共 {len(wl)} 個 tag")
    return 0


def cmd_check(schema: Path, pages: list[Path]) -> int:
    wl = load_whitelist(schema)
    bad = 0
    for page in pages:
        unknown = [t for t in page_tags(page) if t not in wl]
        malformed = [t for t in page_tags(page) if not TAG_RE.match(t)]
        if unknown or malformed:
            bad += 1
            print(f"❌ {page}")
            if unknown:
                print(f"   - 不在白名單：{unknown}（走 propose，不自創）")
            if malformed:
                print(f"   - 格式違規（需 kebab-case）：{malformed}")
        else:
            print(f"✅ {page}")
    return 1 if bad else 0


def cmd_propose(schema: Path, tag: str, reason: str, by: str) -> int:
    if not TAG_RE.match(tag):
        print(f"❌ tag 需為 kebab-case：{tag}")
        return 1
    if tag in load_whitelist(schema):
        print(f"ℹ '{tag}' 已在白名單")
        return 0
    text = _read(schema)
    row = f"| {tag} | {reason} | {by} | {date.today()} |"
    if QUEUE_HEADER not in text:
        text += f"\n{QUEUE_HEADER}\n\n| tag | 提案原因 | 提案者 | 日期 |\n|---|---|---|---|\n{row}\n"
    elif f"| {tag} |" in text:
        print(f"ℹ '{tag}' 已在提案佇列")
        return 0
    else:
        text = re.sub(rf"({re.escape(QUEUE_HEADER)}\n\n\|.*\n\|[-| ]+\|\n)",
                      rf"\g<1>{row}\n", text, count=1)
    schema.write_text(text, encoding="utf-8")
    print(f"✅ 已提案 '{tag}'（等待人工 approve）")
    return 0


def cmd_approve(schema: Path, tag: str) -> int:
    text = _read(schema)
    if tag in load_whitelist(schema):
        print(f"ℹ '{tag}' 已在白名單")
        return 0
    if WHITELIST_HEADER not in text:
        text = f"{WHITELIST_HEADER}\n\n- {tag}\n\n" + text
    else:
        text = re.sub(rf"({re.escape(WHITELIST_HEADER)}\s*\n)", rf"\g<1>- {tag}\n", text, count=1)
    # 從提案佇列移除
    text = re.sub(rf"\|\s*{re.escape(tag)}\s*\|.*\n", "", text)
    schema.write_text(text, encoding="utf-8")
    print(f"✅ '{tag}' 已入白名單")
    return 0


def cmd_migrate(schema: Path, wiki_dir: Path) -> int:
    counts: dict[str, int] = {}
    for page in wiki_dir.rglob("*.md"):
        for t in page_tags(page):
            counts[t] = counts.get(t, 0) + 1
    if not counts:
        print("存量頁面無 tags")
        return 0
    print("存量 tag 統計（人工確認後逐一 approve，或直接編輯 schema.md 白名單區塊）：\n")
    for t, c in sorted(counts.items(), key=lambda x: -x[1]):
        flag = "" if TAG_RE.match(t) else "  ⚠ 格式違規，建議改名"
        print(f"  {c:3d}×  {t}{flag}")
    return 0


def check_payload(schema: Path, pages: list[Path]) -> dict:
    """check 的機器可讀版：列出每頁的未知 tag。"""
    whitelist = load_whitelist(schema)
    rows, unknown_total = [], 0
    for pg in pages:
        tags = page_tags(pg)
        unknown = sorted(t for t in tags if t not in whitelist)
        unknown_total += len(unknown)
        rows.append({"page": str(pg), "tags": tags, "unknown": unknown})
    return {"ok": True, "action": "check", "whitelist_size": len(whitelist),
            "pages": len(rows), "unknown_total": unknown_total, "results": rows}


def main() -> int:
    p = argparse.ArgumentParser(description="Wiki Taxonomy — tags 受控詞彙表")
    sub = p.add_subparsers(dest="cmd")

    for name, helptext in (("list", "列出白名單"), ("check", "檢查頁面 tags"),
                           ("propose", "提案新 tag"), ("approve", "核准提案（人工）"),
                           ("migrate", "由存量頁面產候選白名單")):
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument("--schema", required=True)
        sp.add_argument("--json", action="store_true")
        if name == "check":
            sp.add_argument("pages", nargs="+")
        if name in ("propose", "approve"):
            sp.add_argument("tag")
        if name == "propose":
            sp.add_argument("--reason", default="")
            sp.add_argument("--by", default="unknown")
        if name == "migrate":
            sp.add_argument("--wiki_dir", required=True)

    args = p.parse_args()
    if not args.cmd:
        p.print_help()
        return 2

    schema = Path(args.schema)
    if not schema.exists():
        emit_error(ErrorCode.SCHEMA_NOT_FOUND, f"schema 不存在：{schema}")

    if args.cmd == "list":
        if args.json:
            emit_json({"ok": True, "action": "list",
                       "tags": sorted(load_whitelist(schema))})
        return cmd_list(schema)
    if args.cmd == "check":
        pages = [Path(x) for x in args.pages]
        if args.json:
            payload = check_payload(schema, pages)
            emit_json(payload, 1 if payload["unknown_total"] else 0)
        return cmd_check(schema, pages)
    if args.cmd == "propose":
        rc = cmd_propose(schema, args.tag, args.reason, args.by)
        if args.json:
            emit_json({"ok": rc == 0, "action": "propose", "tag": args.tag}, rc)
        return rc
    if args.cmd == "approve":
        rc = cmd_approve(schema, args.tag)
        if args.json:
            emit_json({"ok": rc == 0, "action": "approve", "tag": args.tag}, rc)
        return rc
    return cmd_migrate(schema, Path(args.wiki_dir))


if __name__ == "__main__":
    sys.exit(main())
