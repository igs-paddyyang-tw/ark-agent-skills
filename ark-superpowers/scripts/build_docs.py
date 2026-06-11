"""build_docs.py — 一鍵產出工程標準化文件骨架 + ADR 索引管理。

功能：
  1. 從模板產出文件骨架（自動填入 title/date/number）
  2. ADR 自動編號 + 索引更新
  3. 驗證目錄結構完整性

Usage:
    python build_docs.py onepager "我的提案"
    python build_docs.py spec "用戶管理系統"
    python build_docs.py design "API Gateway 架構"
    python build_docs.py adr "選擇 PostgreSQL 作為主資料庫"
    python build_docs.py plan "Phase 1 上線計畫"
    python build_docs.py --init                    # 建立 docs/ 目錄結構
    python build_docs.py --index                   # 重建 ADR 索引
    python build_docs.py --validate                # 驗證所有文件
    python build_docs.py --lang en spec "Auth System"  # 英文模板
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = SKILL_ROOT / "references" / "templates"
TODAY = str(date.today())


# ── 目錄結構 ──────────────────────────────────────────────────

DOCS_DIRS = [
    "docs/one-pagers",
    "docs/specs",
    "docs/designs",
    "docs/designs/adr",
    "docs/plans",
]


# ── 模板對照 ──────────────────────────────────────────────────

TEMPLATE_MAP = {
    "onepager": "onepager.md",
    "spec": "spec-full.md",
    "spec-onepager": "spec-onepager.md",
    "design": "design-full.md",
    "design-onepager": "design-onepager.md",
    "adr": "adr.md",
    "plan": "plan-full.md",
    "plan-onepager": "plan-onepager.md",
}

OUTPUT_DIR_MAP = {
    "onepager": "docs/one-pagers",
    "spec": "docs/specs",
    "spec-onepager": "docs/specs",
    "design": "docs/designs",
    "design-onepager": "docs/designs",
    "adr": "docs/designs/adr",
    "plan": "docs/plans",
    "plan-onepager": "docs/plans",
}


def _to_kebab(title: str) -> str:
    """將標題轉為 kebab-case 檔名。"""
    # 移除特殊字元，空白轉 dash
    name = re.sub(r"[^\w\s-]", "", title)
    name = re.sub(r"[\s_]+", "-", name)
    return name.lower().strip("-")


def _next_adr_number(adr_dir: Path) -> int:
    """取得下一個 ADR 編號。"""
    if not adr_dir.exists():
        return 1
    max_num = 0
    for f in adr_dir.glob("*.md"):
        if f.name.startswith("_"):
            continue
        match = re.match(r"^(\d+)-", f.name)
        if match:
            max_num = max(max_num, int(match.group(1)))
    return max_num + 1


def _update_adr_index(adr_dir: Path) -> None:
    """重建 ADR 索引（_index.md）。"""
    index_path = adr_dir / "_index.md"
    entries: list[tuple[int, str, str, str]] = []

    for f in sorted(adr_dir.glob("*.md")):
        if f.name.startswith("_"):
            continue
        match = re.match(r"^(\d+)-(.+)\.md$", f.name)
        if not match:
            continue
        num = int(match.group(1))
        content = f.read_text(encoding="utf-8")
        # 從 frontmatter 提取 title 和 status
        title = match.group(2).replace("-", " ").title()
        status = "proposed"
        created = ""
        fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if fm_match:
            for line in fm_match.group(1).split("\n"):
                if line.startswith("title:"):
                    title = line.split(":", 1)[1].strip().strip('"')
                elif line.startswith("status:"):
                    status = line.split(":", 1)[1].strip()
                elif line.startswith("created:"):
                    created = line.split(":", 1)[1].strip()
        entries.append((num, title, status, created))

    lines = [
        "# Architecture Decision Records\n",
        "| # | 標題 | 狀態 | 日期 |",
        "|---|------|------|------|",
    ]
    for num, title, status, created in entries:
        lines.append(f"| {num:03d} | {title} | {status} | {created} |")

    lines.append(f"\n---\n*自動產出：{TODAY}*\n")
    index_path.write_text("\n".join(lines), encoding="utf-8")


def init_docs(project_dir: Path) -> list[str]:
    """建立 docs/ 目錄結構。"""
    created: list[str] = []
    for d in DOCS_DIRS:
        path = project_dir / d
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(d)
    # ADR index
    adr_index = project_dir / "docs" / "designs" / "adr" / "_index.md"
    if not adr_index.exists():
        adr_index.write_text(
            "# Architecture Decision Records\n\n"
            "| # | 標題 | 狀態 | 日期 |\n"
            "|---|------|------|------|\n\n"
            "（尚無 ADR）\n",
            encoding="utf-8",
        )
        created.append("docs/designs/adr/_index.md")
    return created


def build_doc(
    project_dir: Path,
    doc_type: str,
    title: str,
    lang: str = "zh-TW",
    author: str = "paddyyang",
) -> Path:
    """從模板產出文件骨架。回傳產出的檔案路徑。"""
    template_file = TEMPLATE_MAP.get(doc_type)
    if not template_file:
        raise ValueError(f"不支援的文件類型：{doc_type}（支援：{', '.join(TEMPLATE_MAP.keys())}）")

    lang_dir = "en" if lang == "en" else "zh-TW"
    template_path = TEMPLATES_DIR / lang_dir / template_file
    if not template_path.exists():
        raise FileNotFoundError(f"模板不存在：{template_path}")

    content = template_path.read_text(encoding="utf-8")

    # 替換佔位符
    kebab_name = _to_kebab(title)

    if doc_type == "adr":
        adr_dir = project_dir / "docs" / "designs" / "adr"
        adr_dir.mkdir(parents=True, exist_ok=True)
        num = _next_adr_number(adr_dir)
        num_str = f"{num:03d}"
        content = content.replace("{NNN}", num_str)
        content = content.replace("{決策標題}", title)
        filename = f"{num_str}-{kebab_name}.md"
    else:
        filename = f"{kebab_name}.md"
        # Spec/Design 加後綴
        if doc_type == "spec":
            filename = f"{kebab_name}-spec.md"
        elif doc_type == "design":
            filename = f"{kebab_name}-design.md"
        elif doc_type == "plan":
            filename = f"{kebab_name}-plan.md"

    content = content.replace("{名稱}", title)
    content = content.replace("{作者}", author)
    content = content.replace("YYYY-MM-DD", TODAY)

    # 確保輸出目錄存在
    output_dir = project_dir / OUTPUT_DIR_MAP[doc_type]
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / filename
    if output_path.exists():
        raise FileExistsError(f"檔案已存在：{output_path}")

    output_path.write_text(content, encoding="utf-8")

    # ADR 自動更新索引
    if doc_type == "adr":
        _update_adr_index(project_dir / "docs" / "designs" / "adr")

    return output_path


def validate_docs(project_dir: Path) -> tuple[int, int, list[str]]:
    """驗證所有文件完整性。回傳 (passed, failed, errors)。"""
    from check_doc_completeness import check_file

    passed = 0
    failed = 0
    errors: list[str] = []

    for dir_name in ("specs", "designs", "plans", "one-pagers"):
        docs_dir = project_dir / "docs" / dir_name
        if not docs_dir.exists():
            continue
        for md in docs_dir.rglob("*.md"):
            if md.name.startswith("_"):
                continue
            file_errors = check_file(md)
            if file_errors:
                failed += 1
                errors.append(f"❌ {md.relative_to(project_dir)}")
                for e in file_errors:
                    errors.append(f"   - {e}")
            else:
                passed += 1

    return passed, failed, errors


def main() -> None:
    """CLI 入口。"""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    arg1 = sys.argv[1]

    # 特殊模式
    if arg1 == "--init":
        project_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.cwd()
        created = init_docs(project_dir)
        if created:
            print(f"✅ 已建立 {len(created)} 個目錄/檔案：")
            for c in created:
                print(f"  + {c}")
        else:
            print("✅ docs/ 結構已存在")
        sys.exit(0)

    if arg1 == "--index":
        project_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.cwd()
        adr_dir = project_dir / "docs" / "designs" / "adr"
        if not adr_dir.exists():
            print("❌ docs/designs/adr/ 不存在")
            sys.exit(1)
        _update_adr_index(adr_dir)
        print("✅ ADR 索引已重建")
        sys.exit(0)

    if arg1 == "--validate":
        project_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.cwd()
        passed, failed, errors = validate_docs(project_dir)
        if failed == 0:
            print(f"✅ 全部通過：{passed} 個文件")
        else:
            print(f"❌ {passed} 通過 / {failed} 失敗")
            for e in errors:
                print(f"  {e}")
            sys.exit(1)
        sys.exit(0)

    # 語言選項
    lang = "zh-TW"
    args = list(sys.argv[1:])
    if "--lang" in args:
        idx = args.index("--lang")
        lang = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    # 正常模式：build_docs <type> <title>
    if len(args) < 2:
        print("Usage: python build_docs.py <type> <title>")
        print(f"Types: {', '.join(TEMPLATE_MAP.keys())}")
        sys.exit(1)

    doc_type = args[0]
    title = " ".join(args[1:])
    project_dir = Path.cwd()

    try:
        output = build_doc(project_dir, doc_type, title, lang=lang)
        print(f"✅ 已產出：{output.relative_to(project_dir)}")
        if doc_type == "adr":
            print(f"   ADR 索引已更新")
    except FileExistsError as e:
        print(f"⚠️ {e}")
        sys.exit(1)
    except (ValueError, FileNotFoundError) as e:
        print(f"❌ {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
