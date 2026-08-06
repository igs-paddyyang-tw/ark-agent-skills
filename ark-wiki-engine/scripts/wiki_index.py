"""wiki_index.py — 重建 Wiki index.md

用途：掃描 wiki/ 目錄下所有 .md 檔案，自動重建 index.md。
按 category（子目錄）分組，附帶統計資訊。

使用方式：
    python scripts/wiki_index.py --wiki_dir knowledge/wiki

    # 輸出到指定路徑（預設寫入 wiki 上層的 index.md）
    python scripts/wiki_index.py --wiki_dir knowledge/wiki --output knowledge/index.md

    # 預覽不寫入
    python scripts/wiki_index.py --wiki_dir knowledge/wiki --dry_run
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path


def parse_frontmatter(content: str) -> dict:
    """解析 YAML frontmatter。"""
    match = re.match(r"^---\n(.+?)\n---", content, re.DOTALL)
    if not match:
        return {}
    result = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if v.startswith("[") and v.endswith("]"):
                v = [x.strip().strip('"').strip("'") for x in v[1:-1].split(",") if x.strip()]
            result[k] = v
    return result


def build_index(wiki_dir: Path) -> str:
    """掃描 wiki/ 建立 index.md 內容。"""
    md_files = sorted(wiki_dir.rglob("*.md"))
    if not md_files:
        return "# 知識庫索引\n\n（尚無頁面）\n"

    # 按子目錄分組
    categories: dict[str, list[dict]] = {}
    total = 0
    status_count = {"seedling": 0, "developing": 0, "mature": 0}

    for f in md_files:
        content = f.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(content)
        title = fm.get("title", f.stem)
        status = fm.get("status", "seedling")
        page_type = fm.get("type", "")

        # 判斷 category
        rel = f.relative_to(wiki_dir)
        if len(rel.parts) > 1:
            category = rel.parts[0]
        else:
            category = "_root"

        if category not in categories:
            categories[category] = []

        categories[category].append({
            "name": f.stem,
            "title": title,
            "status": status,
            "type": page_type,
            "path": str(rel),
        })

        total += 1
        if status in status_count:
            status_count[status] += 1

    # 產出 Markdown
    today = date.today().isoformat()
    lines = [
        f"# 知識庫索引",
        f"",
        f"> 自動產生 by `wiki_index.py` — {today}",
        f"> 共 {total} 頁面 | 🌱 seedling: {status_count['seedling']} | 🌿 developing: {status_count['developing']} | 🌳 mature: {status_count['mature']}",
        f"",
    ]

    # 排序 category（_root 放最後）
    sorted_cats = sorted(categories.keys(), key=lambda x: (x == "_root", x))

    for cat in sorted_cats:
        pages = categories[cat]
        if cat == "_root":
            lines.append("## 根目錄")
        else:
            lines.append(f"## {cat}/")
        lines.append("")

        for page in sorted(pages, key=lambda x: x["title"]):
            status_icon = {"seedling": "🌱", "developing": "🌿", "mature": "🌳"}.get(page["status"], "")
            lines.append(f"- {status_icon} [[{page['name']}]] — {page['title']}")

        lines.append("")

    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description="Wiki Index — 重建 index.md")
    p.add_argument("--wiki_dir", required=True, help="wiki/ 目錄路徑")
    p.add_argument("--output", default="", help="輸出路徑（預設: wiki_dir 上層的 index.md）")
    p.add_argument("--dry_run", action="store_true", help="預覽不寫入")
    args = p.parse_args()

    wiki_dir = Path(args.wiki_dir)
    if not wiki_dir.exists():
        print(f"[ERROR] 目錄不存在：{wiki_dir}", file=sys.stderr)
        sys.exit(1)

    content = build_index(wiki_dir)

    if args.dry_run:
        print(content)
        return

    # 輸出路徑
    if args.output:
        out_path = Path(args.output)
    else:
        out_path = wiki_dir.parent / "index.md"

    out_path.write_text(content, encoding="utf-8")
    print(f"✅ index.md 已重建：{out_path}")


if __name__ == "__main__":
    main()
