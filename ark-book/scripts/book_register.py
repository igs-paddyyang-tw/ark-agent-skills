"""book_register.py — 把一本書登錄到圖書館目錄（library/catalog.json）。

流程：跑 book_lint.py（--json）→ 跑 book_build.py --check → 組 catalog 條目 → 寫 catalog.json →
重建 catalog.md → append log.md。published 書若 lint≠PASS 或 pair≠OK 則拒絕登錄。

用法：
    python book_register.py books/first-personal-agent/
    python book_register.py books/xxx/ --library library/          # 預設 <books 的上一層>/library
    python book_register.py books/xxx/ --wiki-schema knowledge/proj/schema.md

Exit code：0 已登錄 / 1 拒絕（published 但守門不過）或找不到書。
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from book_lint import load_yaml_text, split_frontmatter, FILENAME_RE  # noqa: E402

HERE = Path(__file__).resolve().parent
TZ = timezone(timedelta(hours=8))
DEFAULT_SHELVES = ["agent-basics", "skill-chain", "case-studies", "ops"]
CATALOG_VERSION = 1


def now() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def run_json(cmd: list[str]) -> dict:
    p = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        return {"status": "ERROR", "stdout": p.stdout, "stderr": p.stderr}


def rel(p: Path, root: Path) -> str:
    try:
        return str(p.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(p)


def build_entry(book_dir: Path, root: Path, lint: dict, pair: dict) -> tuple[dict, list[str]]:
    warns: list[str] = []
    meta = load_yaml_text((book_dir / "book.yaml").read_text(encoding="utf-8"))
    files = {p.stem: p for p in book_dir.glob("*.md") if FILENAME_RE.match(p.name)}
    chapters = []
    total = 0
    for stem in meta.get("chapters", []):
        p = files.get(str(stem))
        if not p:
            warns.append(f"chapters `{stem}` 檔案不存在（lint 應已 FAIL）")
            continue
        fm, _ = split_frontmatter(p.read_text(encoding="utf-8"))
        est = int(fm.get("est_minutes") or 0)
        total += est
        chapters.append({"n": int(fm.get("chapter", 0)), "slug": fm.get("slug"), "title": fm.get("title"),
                         "type": fm.get("type"), "est_minutes": est, "status": fm.get("status"),
                         "punchline": fm.get("punchline"), "tags": fm.get("tags") or []})
    cover = meta.get("cover") if isinstance(meta.get("cover"), dict) else {}
    entry = {
        "slug": meta["slug"], "title": meta["title"], "subtitle": meta.get("subtitle"),
        "author": meta.get("author"), "version": meta.get("version", 1), "status": meta.get("status"),
        "language": meta.get("language", "zh-Hant"), "level": meta.get("level"),
        "audience": meta.get("audience"), "outcomes": meta.get("outcomes", []),
        "prerequisites": meta.get("prerequisites", []), "tags": meta.get("tags", []),
        "shelf": meta.get("shelf"), "style": meta.get("style") or "library", "cover": cover, "est_minutes_total": total, "chapters": chapters,
        "paths": {"book_dir": rel(book_dir, root), "site": rel(book_dir / "site" / "index.html", root),
                  "book_yaml": rel(book_dir / "book.yaml", root)},
        "lint": {"status": lint.get("status", "ERROR"), "fails": lint.get("fails", 0), "warns": lint.get("warns", 0), "checked": now()},
        "pair": {"status": pair.get("status", "ERROR"), "checked": now()},
        "created": str(meta.get("created", "")), "updated": str(meta.get("updated", "")),
        "registered": now(),
    }
    return entry, warns


def write_catalog_md(catalog: dict, path: Path) -> None:
    lines = [f"# 圖書館目錄", "", f"更新：{catalog['updated']} · {len(catalog['books'])} 本 · 由 book_register.py 重建，請勿手改", ""]
    by_shelf: dict[str, list[dict]] = {}
    for b in catalog["books"]:
        by_shelf.setdefault(b.get("shelf") or "未分類", []).append(b)
    for shelf in catalog["shelves"] + [s for s in by_shelf if s not in catalog["shelves"]]:
        books = by_shelf.get(shelf)
        if not books:
            continue
        lines += [f"## {shelf}", "", "| 書名 | 讀者 | 難度 | 章數 | 時間 | 狀態 | 守門 | 開書 |", "|---|---|---|---|---|---|---|---|"]
        for b in sorted(books, key=lambda x: x["title"]):
            gate = f"lint {b['lint']['status']} · pair {b['pair']['status']}"
            lines.append(f"| {b['title']} | {b.get('audience') or ''} | {b.get('level')} | {len(b['chapters'])} | "
                         f"{b['est_minutes_total']} 分 | {b['status']} | {gate} | [{b['paths']['site']}]({b['paths']['site']}) |")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str]) -> int:
    if "-h" in argv or "--help" in argv:
        print(__doc__)
        return 0
    if not argv or argv[0].startswith("--"):
        print(__doc__)
        return 2
    book_dir = Path(argv[0]).resolve()
    if not (book_dir / "book.yaml").exists():
        print(f"找不到 {book_dir / 'book.yaml'}")
        return 1

    def opt(name: str) -> str | None:
        return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else None

    library = Path(opt("--library")) if opt("--library") else book_dir.parent.parent / "library"
    root = library.parent
    library.mkdir(parents=True, exist_ok=True)

    lint_cmd = [sys.executable, str(HERE / "book_lint.py"), str(book_dir), "--json"]
    if opt("--wiki-schema"):
        lint_cmd += ["--wiki-schema", opt("--wiki-schema")]
    lint = run_json(lint_cmd)
    pair = run_json([sys.executable, str(HERE / "book_build.py"), str(book_dir), "--check", "--json"])

    entry, warns = build_entry(book_dir, root, lint, pair)
    for w in warns:
        print(f"WARN  {w}")

    if entry["status"] == "published" and (lint.get("status") != "PASS" or pair.get("status") != "OK"):
        print(f"REJECT  published 書守門不過：lint={lint.get('status')} pair={pair.get('status')}")
        for f in lint.get("files", []):
            for msg in f.get("fails", []):
                print(f"      ✗ {f['path']}: {msg}")
        if pair.get("stale"):
            print(f"      ✗ 過期章節：{', '.join(pair['stale'])}（重跑 book_build.py）")
        return 1

    cat_path = library / "catalog.json"
    catalog = json.loads(cat_path.read_text(encoding="utf-8")) if cat_path.exists() else \
        {"catalog_version": CATALOG_VERSION, "updated": "", "shelves": DEFAULT_SHELVES, "books": []}
    if entry["shelf"] not in catalog["shelves"]:
        print(f"WARN  shelf `{entry['shelf']}` 不在受控清單 {catalog['shelves']}；圖書館會放到「未分類」，要新增請人工改 catalog.json shelves")
    books = [b for b in catalog["books"] if b["slug"] != entry["slug"]]
    action = "update" if len(books) != len(catalog["books"]) else "add"
    books.append(entry)
    catalog["books"] = sorted(books, key=lambda b: (b.get("shelf") or "", b["title"]))
    catalog["updated"] = now()
    cat_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    write_catalog_md(catalog, library / "catalog.md")

    log = library / "log.md"
    if not log.exists():
        log.write_text("# 圖書館登錄紀錄（append-only）\n\n| date | slug | version | status | chapters | lint | pair | action |\n|---|---|---|---|---|---|---|---|\n", encoding="utf-8")
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"| {now()} | {entry['slug']} | {entry['version']} | {entry['status']} | {len(entry['chapters'])} | "
                 f"{entry['lint']['status']} | {entry['pair']['status']} | {action} |\n")

    print(f"書已登錄 {entry['paths']['book_dir']}｜{len(entry['chapters'])} 章｜lint: {entry['lint']['status']}｜"
          f"pair: {entry['pair']['status']}｜site: {entry['paths']['site']}｜catalog: {action}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
