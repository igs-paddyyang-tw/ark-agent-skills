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
    python wiki_taxonomy.py retag   --schema schema.md --wiki_dir knowledge/proj/wiki \\
        --map cli=kiro-cli --map 架構= [--drop-unknown] [--dry_run] [--by agent]
        # 白名單建好後修存量頁：只改 frontmatter 的 tags，內文逐位元組不動（ingest 會跳過既有頁、且只產骨架，不能拿來改 tag）

Exit code：check 有未知 tag 回 1；retag 有殘留未知 tag 或頁面會被清空 tags 回 1、對照表不合法回 2。
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _wikilib import _FM_RE, ErrorCode, emit_error, emit_json, parse_frontmatter  # noqa: E402

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
    """讀頁面 tags。

    改用 `_wikilib.parse_frontmatter`（支援 inline 與 block list、容忍 BOM）——
    自帶的 `^---` regex 對有 BOM 的頁面讀不到 frontmatter → tags 回空 →
    **白名單檢查靜默放行**（fail-open）。那比報錯更糟。
    """
    tags = parse_frontmatter(page.read_text(encoding="utf-8", errors="replace")).get("tags", [])
    if isinstance(tags, str):
        tags = [tags]
    return [str(t).strip() for t in tags if str(t).strip()]


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


def _append_approve_log(schema: Path, tag: str, by: str) -> None:
    """approve 後 append 一行到 schema 同層的 log.md（治理稽核軌跡）。

    🔴 F-6（aidev-agent 回報）：approve 是治理關鍵動作卻無稽核軌跡 ——
    出了問題要能回答「這個 tag 是誰、何時核准進白名單的」。
    log 位置 = schema 同層的 log.md（knowledge/{proj}/log.md），
    格式與 wiki_ingest 的 log 平行：`date | op | tag | by | note`。
    """
    log_path = schema.parent / "log.md"
    entry = (f"- **{date.today().isoformat()}** | approve | tag `{tag}` | {by} | "
             f"核准入白名單\n")
    if log_path.exists():
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)
    else:
        log_path.write_text(f"# Wiki 操作日誌\n\n{entry}", encoding="utf-8")


def cmd_approve(schema: Path, tag: str, by: str = "unknown") -> int:
    text = _read(schema)
    if tag in load_whitelist(schema):
        print(f"ℹ '{tag}' 已在白名單", file=sys.stderr)
        return 0
    if WHITELIST_HEADER not in text:
        text = f"{WHITELIST_HEADER}\n\n- {tag}\n\n" + text
    else:
        text = re.sub(rf"({re.escape(WHITELIST_HEADER)}\s*\n)", rf"\g<1>- {tag}\n", text, count=1)
    # 從提案佇列移除
    text = re.sub(rf"\|\s*{re.escape(tag)}\s*\|.*\n", "", text)
    schema.write_text(text, encoding="utf-8")
    # 寫入白名單成功才記 log（已存在的 tag 在上面提前 return，不會重複寫）
    _append_approve_log(schema, tag, by)
    print(f"✅ '{tag}' 已入白名單（by {by}，已記 log.md）", file=sys.stderr)
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


# ── retag：白名單建好後修存量頁 ──────────────────────────────────
#
# 為什麼不走 raw → ingest：ingest 遇既有頁回 `already_exists` 跳過，且只產「待填骨架」
# （內文全換成空章節）→ 想靠重新 ingest 改 tag 只能先刪頁，整理過的內容就沒了。
# retag 只動 frontmatter 的 `tags:`，其餘位元組（含 BOM、CRLF、內文）原封不動，
# 每頁變更記進 log.md —— 確定性的 metadata 維護，不是手寫 wiki 內容。

_TAGS_INLINE_RE = re.compile(r"^tags:[ \t]*\[(?P<items>[^\]\r\n]*)\][ \t]*(?=\r?$)", re.MULTILINE)
_TAGS_BLOCK_RE = re.compile(
    r"^tags:[ \t]*(?P<nl>\r?\n)(?P<items>(?:[ \t]*-[ \t]+[^\r\n]*(?:\r?\n|\Z))+)", re.MULTILINE)


def _split_inline(items: str) -> list[str]:
    return [t.strip().strip('"').strip("'") for t in items.split(",") if t.strip().strip('"').strip("'")]


def _rewrite_tags(text: str, mapper) -> tuple[str, list[str], list[str]] | None:
    """回傳 (新全文, 原 tags, 新 tags)；找不到 frontmatter 或 tags 欄位回 None。

    mapper(list[str]) -> list[str]。只替換 tags 片段，切片拼回，其他位元組不經手。
    """
    fm = _FM_RE.match(text)   # 共用 _wikilib 的 regex（BOM／CRLF 行為與 parse_frontmatter 一致，AC-003）
    if not fm:
        return None
    body_start, fm_text = fm.start(1), fm.group(1)
    m = _TAGS_INLINE_RE.search(fm_text)
    if m:
        old = _split_inline(m.group("items"))
        new = mapper(old)
        repl = f"tags: [{', '.join(new)}]"
    else:
        m = _TAGS_BLOCK_RE.search(fm_text)
        if not m:
            return None
        lines = m.group("items").splitlines(keepends=True)
        old = [re.sub(r"^[ \t]*-[ \t]+", "", ln).strip().strip('"').strip("'") for ln in lines]
        new = mapper(old)
        indent = re.match(r"^([ \t]*)-", lines[0]).group(1)
        nl = m.group("nl")
        tail_nl = nl if m.group("items").endswith(("\n",)) else ""
        repl = "tags:" + nl + nl.join(f"{indent}- {t}" for t in new) + tail_nl
    s, e = body_start + m.start(), body_start + m.end()
    return text[:s] + repl + text[e:], old, new


def _parse_map(pairs: list[str], whitelist: set[str]) -> tuple[dict[str, str], list[str]]:
    """`old=new`（new 留空＝移除）。new 必須已在白名單且合 kebab-case —— 不給繞過受控詞彙的後門。"""
    mapping, errors = {}, []
    for raw in pairs:
        if "=" not in raw:
            errors.append(f"'{raw}' 缺少 '='（寫法：old=new，new 留空代表移除）")
            continue
        old, _, new = (x.strip() for x in raw.partition("="))
        if not old:
            errors.append(f"'{raw}' 的舊 tag 是空的")
        elif new and new not in whitelist:
            errors.append(f"'{old}={new}'：'{new}' 不在白名單 → 先 propose＋approve，或改對應到已核准的 tag")
        else:
            mapping[old] = new
    return mapping, errors


def _append_retag_log(schema: Path, page: str, before: list[str], after: list[str], by: str) -> None:
    log_path = schema.parent / "log.md"
    entry = (f"- **{date.today().isoformat()}** | retag | `{page}` | {by} | "
             f"{', '.join(before)} → {', '.join(after)}\n")
    if log_path.exists():
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)
    else:
        log_path.write_text(f"# Wiki 操作日誌\n\n{entry}", encoding="utf-8")


def retag_payload(schema: Path, wiki_dir: Path, pairs: list[str], *, drop_unknown: bool,
                  dry_run: bool, by: str, rebuild_index: bool = True) -> tuple[dict, int]:
    whitelist = load_whitelist(schema)
    if not whitelist:
        return ({"ok": False, "action": "retag",
                 "error": "白名單為空 —— 先 migrate＋approve 建表，再 retag"}, 2)
    mapping, errors = _parse_map(pairs, whitelist)
    if errors:
        return {"ok": False, "action": "retag", "error": "對照表不合法，未改任何檔", "details": errors}, 2

    def mapper(tags: list[str]) -> list[str]:
        out: list[str] = []
        for t in tags:
            t = mapping.get(t, t)
            if not t or (drop_unknown and t not in whitelist):
                continue
            if t not in out:
                out.append(t)
        return out

    changed, skipped, residual = [], [], []
    for page in sorted(wiki_dir.rglob("*.md")):
        if page.name in ("index.md", "log.md"):
            continue
        with open(page, encoding="utf-8", newline="") as f:   # newline="" 保留 CRLF
            text = f.read()
        res = _rewrite_tags(text, mapper)
        if res is None:
            continue
        new_text, before, after = res
        rel = page.relative_to(wiki_dir).as_posix()
        if not after:
            skipped.append({"page": rel, "reason": "would_empty", "tags": before,
                            "hint": "對照後沒有任何 tag —— 給它一個已核准的 tag 再跑"})
            continue
        left = [t for t in after if t not in whitelist]
        if left:
            residual.append({"page": rel, "unknown": left})
        if after == before:
            continue
        changed.append({"page": rel, "before": before, "after": after})
        if not dry_run:
            with open(page, "w", encoding="utf-8", newline="") as f:
                f.write(new_text)
            _append_retag_log(schema, rel, before, after, by)

    payload = {"ok": True, "action": "retag", "dry_run": dry_run, "changed": changed,
               "skipped": skipped, "residual": residual}
    if changed and not dry_run and rebuild_index:
        proc = subprocess.run([sys.executable, str(Path(__file__).parent / "wiki_index.py"),
                               "build", "--wiki_dir", str(wiki_dir)], capture_output=True, text=True)
        payload["index_rebuilt"] = proc.returncode == 0
        if proc.returncode != 0:
            payload["index_error"] = (proc.stderr or proc.stdout or "").strip()[-500:]
    rc = 1 if (residual or skipped) else 0
    return payload, rc


def cmd_retag(payload: dict) -> None:
    tag = "（預覽，未寫入）" if payload.get("dry_run") else ""
    for c in payload["changed"]:
        print(f"✏ {c['page']}{tag}：{', '.join(c['before'])} → {', '.join(c['after'])}")
    for s in payload["skipped"]:
        print(f"⏭ {s['page']}：{s['hint']}（原 tags：{', '.join(s['tags'])}）")
    for r in payload["residual"]:
        print(f"⚠ {r['page']} 仍有不在白名單的 tag：{r['unknown']}"
              f" → 加 --map {r['unknown'][0]}=<已核准 tag>，或 --drop-unknown 移除")
    if not (payload["changed"] or payload["skipped"] or payload["residual"]):
        print("✅ 沒有需要改的頁")
    if payload.get("index_rebuilt") is False:
        print(f"❌ 索引重建失敗：{payload.get('index_error')}")


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
                           ("migrate", "由存量頁面產候選白名單"),
                           ("retag", "依對照表改存量頁 tags（只動 frontmatter）")):
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument("--schema", required=True)
        sp.add_argument("--json", action="store_true")
        if name == "check":
            sp.add_argument("pages", nargs="+")
        if name in ("propose", "approve"):
            sp.add_argument("tag")
        if name in ("propose", "approve", "retag"):
            sp.add_argument("--by", default="unknown")
        if name == "propose":
            sp.add_argument("--reason", default="")
        if name in ("migrate", "retag"):
            sp.add_argument("--wiki_dir", required=True)
        if name == "retag":
            sp.add_argument("--map", action="append", default=[], metavar="OLD=NEW",
                            help="可重複；NEW 留空＝移除；NEW 必須已在白名單")
            sp.add_argument("--drop-unknown", action="store_true",
                            help="對照後仍不在白名單的 tag 一律移除")
            sp.add_argument("--dry_run", action="store_true")
            sp.add_argument("--no-index", action="store_true", help="改完不重建索引")

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
        rc = cmd_approve(schema, args.tag, args.by)
        if args.json:
            emit_json({"ok": rc == 0, "action": "approve", "tag": args.tag}, rc)
        return rc
    if args.cmd == "retag":
        wiki_dir = Path(args.wiki_dir)
        if not wiki_dir.is_dir():
            emit_error(ErrorCode.WIKI_DIR_NOT_FOUND, f"wiki_dir 不存在：{wiki_dir}")
        payload, rc = retag_payload(schema, wiki_dir, args.map, drop_unknown=args.drop_unknown,
                                    dry_run=args.dry_run, by=args.by,
                                    rebuild_index=not args.no_index)
        if args.json:
            emit_json(payload, rc)
        if not payload["ok"]:
            print(f"❌ {payload['error']}")
            for d in payload.get("details", []):
                print(f"   - {d}")
            return rc
        cmd_retag(payload)
        return rc
    return cmd_migrate(schema, Path(args.wiki_dir))


if __name__ == "__main__":
    sys.exit(main())
