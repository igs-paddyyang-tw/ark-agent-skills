"""build_docs.py — 一鍵產出工程標準化文件骨架 + ADR 索引管理。

功能：
  1. 從模板產出文件骨架（自動填入 title/date/number）
  2. ADR 自動編號 + 索引更新
  3. 驗證目錄結構完整性
  4. One Pager 升級為 spec + design + plan

Usage:
    python build_docs.py onepager "我的提案"
    python build_docs.py spec "用戶管理系統"
    python build_docs.py design "API Gateway 架構"
    python build_docs.py adr "選擇 PostgreSQL 作為主資料庫"
    python build_docs.py plan "Phase 1 上線計畫"
    python build_docs.py upgrade docs/one-pagers/my-proposal.md
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


def _has_non_ascii(text: str) -> bool:
    """檢查文字是否含有非 ASCII 字元。"""
    return bool(re.search(r"[^\x00-\x7f]", text))


def _to_kebab(title: str, slug: str | None = None) -> str:
    """將標題轉為 kebab-case 檔名。

    若 slug 已提供，直接使用。
    若標題含非 ASCII 且無 slug，拋出 ValueError 要求提供。
    """
    if slug:
        # 正規化 slug：確保 kebab-case
        name = re.sub(r"[^\w\s-]", "", slug)
        name = re.sub(r"[\s_]+", "-", name)
        return name.lower().strip("-")

    if _has_non_ascii(title):
        raise ValueError(
            f"標題含非 ASCII 字元：「{title}」\n"
            f"  請使用 --slug 參數指定英文檔名，例如：\n"
            f"  python build_docs.py --slug user-management spec \"{title}\""
        )

    # 純 ASCII：自動轉換
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
    slug: str | None = None,
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
    kebab_name = _to_kebab(title, slug=slug)

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


def upgrade_onepager(project_dir: Path, onepager_path: Path, lang: str = "zh-TW", author: str = "paddyyang") -> list[Path]:
    """將 one-pager 升級為 spec + design + plan 三份文件。

    流程：
    1. 讀取 one-pager 內容與 frontmatter
    2. 從 title 推斷 slug
    3. 產出 spec / design / plan 三份骨架
    4. 回填 one-pager 的 upgraded_to
    5. 新文件加 upgraded_from
    6. plan 自動連結 related_spec / related_design
    """
    if not onepager_path.exists():
        raise FileNotFoundError(f"One-pager 不存在：{onepager_path}")

    content = onepager_path.read_text(encoding="utf-8")
    frontmatter = {}
    fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if fm_match:
        for line in fm_match.group(1).split("\n"):
            if ":" in line:
                key, _, value = line.partition(":")
                frontmatter[key.strip()] = value.strip().strip('"').strip("'")

    title = frontmatter.get("title", onepager_path.stem)
    op_lang = frontmatter.get("language", lang)

    # 推斷 slug
    slug = onepager_path.stem
    if slug.endswith("-onepager") or slug.endswith("-one-pager"):
        slug = re.sub(r"-(one-?pager)$", "", slug)

    # 準備三份文件（先全部產到暫存再一次落盤）
    lang_dir = "en" if op_lang == "en" else "zh-TW"
    outputs: list[tuple[Path, str]] = []

    for doc_type in ("spec", "design", "plan"):
        template_file = TEMPLATE_MAP[doc_type]
        template_path = TEMPLATES_DIR / lang_dir / template_file
        if not template_path.exists():
            raise FileNotFoundError(f"模板不存在：{template_path}")

        tmpl_content = template_path.read_text(encoding="utf-8")

        # 替換佔位符
        if doc_type == "spec":
            filename = f"{slug}-spec.md"
            output_dir = project_dir / "docs" / "specs"
        elif doc_type == "design":
            filename = f"{slug}-design.md"
            output_dir = project_dir / "docs" / "designs"
        else:
            filename = f"{slug}-plan.md"
            output_dir = project_dir / "docs" / "plans"

        tmpl_content = tmpl_content.replace("{名稱}", title)
        tmpl_content = tmpl_content.replace("{專案名稱}", title)
        tmpl_content = tmpl_content.replace("{Project Name}", title)
        tmpl_content = tmpl_content.replace("{作者}", author)
        tmpl_content = tmpl_content.replace("{Author}", author)
        tmpl_content = tmpl_content.replace("YYYY-MM-DD", TODAY)

        # 加入 upgraded_from 欄位到 frontmatter
        onepager_rel = str(onepager_path.relative_to(project_dir)) if project_dir in onepager_path.parents else str(onepager_path)
        tmpl_content = _inject_frontmatter_field(tmpl_content, "upgraded_from", onepager_rel)

        # plan 加入 related_spec / related_design
        if doc_type == "plan":
            spec_path = f"docs/specs/{slug}-spec.md"
            design_path = f"docs/designs/{slug}-design.md"
            tmpl_content = _inject_frontmatter_field(tmpl_content, "related_spec", spec_path)
            tmpl_content = _inject_frontmatter_field(tmpl_content, "related_design", design_path)

        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / filename
        outputs.append((output_path, tmpl_content))

    # 一次落盤
    created: list[Path] = []
    for path, file_content in outputs:
        if path.exists():
            raise FileExistsError(f"檔案已存在：{path}")
        path.write_text(file_content, encoding="utf-8")
        created.append(path)

    # 回填 one-pager 的 upgraded_to
    upgraded_to_paths = [str(p.relative_to(project_dir)) for p in created]
    upgraded_to_value = ", ".join(upgraded_to_paths)

    # 修改 one-pager frontmatter
    new_op_content = re.sub(
        r"(upgraded_to:\s*).*",
        f"\\1\"{upgraded_to_value}\"",
        content,
    )
    if "upgraded_to" not in content:
        # 在 frontmatter 結束前插入
        new_op_content = content.replace("\n---\n", f"\nupgraded_to: \"{upgraded_to_value}\"\n---\n", 1)

    onepager_path.write_text(new_op_content, encoding="utf-8")

    return created


def _inject_frontmatter_field(content: str, key: str, value: str) -> str:
    """在 frontmatter 中注入或更新一個欄位。"""
    pattern = re.compile(rf"^({key}:\s*).*$", re.MULTILINE)
    if pattern.search(content):
        return pattern.sub(f"{key}: \"{value}\"", content)
    # 在 --- 結束前插入
    return content.replace("\n---\n", f"\n{key}: \"{value}\"\n---\n", 1)


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

    # Upgrade 模式
    if arg1 == "upgrade":
        if len(sys.argv) < 3:
            print("Usage: python build_docs.py upgrade <onepager-path>")
            sys.exit(1)
        onepager_path = Path(sys.argv[2]).resolve()
        project_dir = Path.cwd()
        try:
            created = upgrade_onepager(project_dir, onepager_path)
            print(f"✅ 升級完成，產出 {len(created)} 份文件：")
            for p in created:
                print(f"  + {p.relative_to(project_dir)}")
            print(f"  ↑ one-pager upgraded_to 已回填")
        except (FileExistsError, FileNotFoundError, ValueError) as e:
            print(f"❌ {e}")
            sys.exit(1)
        sys.exit(0)

    # 語言選項
    lang = "zh-TW"
    slug: str | None = None
    args = list(sys.argv[1:])
    if "--lang" in args:
        idx = args.index("--lang")
        lang = args[idx + 1]
        args = args[:idx] + args[idx + 2:]
    if "--slug" in args:
        idx = args.index("--slug")
        slug = args[idx + 1]
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
        output = build_doc(project_dir, doc_type, title, lang=lang, slug=slug)
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
