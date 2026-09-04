"""wiki_lint.py — Wiki 健康檢查腳本

用途：檢查 wiki/ 目錄下所有頁面的品質問題。
- frontmatter 必要欄位驗證
- 孤立頁面偵測（無任何 inbound wikilink）
- 斷裂 wikilink（指向不存在的頁面）
- status 過期提醒

使用方式：
    python scripts/wiki_lint.py --wiki_dir knowledge/wiki

    # 只看錯誤（忽略警告）
    python scripts/wiki_lint.py --wiki_dir knowledge/wiki --errors-only

    # JSON 輸出（給程式用）
    python scripts/wiki_lint.py --wiki_dir knowledge/wiki --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _wikilib import (  # noqa: E402
    ErrorCode,
    emit_error,
    extract_wikilinks,
    index_dir,
    iter_pages,
    parse_frontmatter,
)


REQUIRED_FIELDS = ["title", "type", "created", "updated"]
RECOMMENDED_FIELDS = ["tags", "status"]
VALID_TYPES = ["concept", "entity", "source", "synthesis", "comparison", "overview", "system"]
VALID_STATUS = ["seedling", "developing", "mature"]


def lint_wiki(wiki_dir: Path, errors_only: bool = False) -> dict:
    """執行 lint，回傳結果字典。"""
    md_files = list(wiki_dir.rglob("*.md"))
    if not md_files:
        return {"files": 0, "errors": [], "warnings": []}

    errors = []
    warnings = []
    all_pages = {}  # filename_stem → path
    all_inbound: dict[str, int] = {}  # page_name → inbound count
    all_outbound: dict[str, list[str]] = {}  # page_name → list of targets

    # Pass 1: 收集所有頁面 + 驗證 frontmatter
    for f in md_files:
        content = f.read_text(encoding="utf-8", errors="replace")
        page_name = f.stem
        rel = f.relative_to(wiki_dir)
        all_pages[page_name] = f
        fm = parse_frontmatter(content)

        # Frontmatter 存在性
        if not fm:
            errors.append({"file": str(rel), "level": "error", "msg": "缺少 frontmatter"})
            continue

        # 必要欄位
        for field in REQUIRED_FIELDS:
            if field not in fm:
                errors.append({"file": str(rel), "level": "error", "msg": f"缺少必要欄位：{field}"})

        # 推薦欄位
        if not errors_only:
            for field in RECOMMENDED_FIELDS:
                if field not in fm:
                    warnings.append({"file": str(rel), "level": "warning", "msg": f"建議補充：{field}"})

        # type 合法值
        if "type" in fm and fm["type"] not in VALID_TYPES:
            warnings.append({"file": str(rel), "level": "warning", "msg": f"type 不在合法值中：{fm['type']}"})

        # status 合法值
        if "status" in fm and fm["status"] not in VALID_STATUS:
            warnings.append({"file": str(rel), "level": "warning", "msg": f"status 不在合法值中：{fm['status']}"})

        # status 過期（seedling 超過 30 天）
        if not errors_only and fm.get("status") == "seedling" and "created" in fm:
            try:
                created = date.fromisoformat(str(fm["created"]))
                if date.today() - created > timedelta(days=30):
                    warnings.append({
                        "file": str(rel), "level": "warning",
                        "msg": f"seedling 已超過 30 天（created: {fm['created']}），考慮升級或刪除"
                    })
            except ValueError:
                pass

        # Wikilinks
        links = extract_wikilinks(content)
        all_outbound[page_name] = links
        for link in links:
            all_inbound[link] = all_inbound.get(link, 0) + 1

    # Pass 2: 斷裂 wikilink + 孤立頁面
    for page_name, targets in all_outbound.items():
        for target in targets:
            if target not in all_pages:
                errors.append({
                    "file": str(all_pages[page_name].relative_to(wiki_dir)),
                    "level": "error",
                    "msg": f"斷裂 wikilink：[[{target}]] 指向不存在的頁面"
                })

    if not errors_only:
        for page_name, path in all_pages.items():
            if page_name not in all_inbound and page_name != "overview":
                warnings.append({
                    "file": str(path.relative_to(wiki_dir)),
                    "level": "warning",
                    "msg": "孤立頁面（無任何 inbound wikilink）"
                })

    return {
        "files": len(md_files),
        "errors": errors,
        "warnings": warnings,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Wiki Lint — 健康檢查")
    p.add_argument("--wiki_dir", required=True, help="wiki/ 目錄路徑")
    p.add_argument("--errors-only", action="store_true", help="只顯示錯誤")
    p.add_argument("--json", action="store_true", help="JSON 格式輸出")
    args = p.parse_args()

    wiki_dir = Path(args.wiki_dir)
    if not wiki_dir.exists():
        print(f"[ERROR] 目錄不存在：{wiki_dir}", file=sys.stderr)
        sys.exit(1)

    result = lint_wiki(wiki_dir, errors_only=args.errors_only)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # Human-readable output
    print(f"📋 Wiki Lint: {result['files']} 頁面掃描完成\n")

    if result["errors"]:
        print(f"❌ 錯誤 ({len(result['errors'])}):")
        for e in result["errors"]:
            print(f"  {e['file']}: {e['msg']}")
        print()

    if result["warnings"]:
        print(f"⚠️  警告 ({len(result['warnings'])}):")
        for w in result["warnings"]:
            print(f"  {w['file']}: {w['msg']}")
        print()

    if not result["errors"] and not result["warnings"]:
        print("✅ 全部通過，無問題。")
    elif not result["errors"]:
        print("✅ 無錯誤（有警告建議處理）。")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
