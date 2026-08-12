"""文件完整性檢查腳本。

驗證 docs/specs/、docs/designs/、docs/plans/、docs/one-pagers/ 下的標準化文件
是否符合 ark-superpowers 格式要求（frontmatter + 必要章節 + 空白章節 + 自動化檢查 + 任務表契約）。

用法：
    python -m scripts.check_doc_completeness docs/specs/my-spec.md
    python -m scripts.check_doc_completeness docs/specs/*.md
    python -m scripts.check_doc_completeness --parity   # 中英模板 parity check
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


# ── 必要的 frontmatter 欄位 ────────────────────────────────────

REQUIRED_FRONTMATTER = ["title", "status", "created"]


# ── 依文件類型對應的必要章節 ────────────────────────────────────

REQUIRED_SECTIONS_ZH: dict[str, list[str]] = {
    "spec": ["摘要", "動機", "目標與非目標", "成功指標"],
    "spec-onepager": ["問題", "提案", "目標", "成功指標"],
    "design": ["概述", "架構決策", "故障隔離"],
    "design-onepager": ["背景", "方案比較", "決策"],
    "adr": ["背景", "選項", "決策", "後果"],
    "plan": ["里程碑", "風險管理", "驗證標準", "回滾計畫"],
    "plan-onepager": ["目標", "里程碑", "關鍵風險", "驗收條件"],
    "one-pager": ["問題與目標", "方案", "執行計畫", "風險與驗收"],
}

REQUIRED_SECTIONS_EN: dict[str, list[str]] = {
    "spec": ["Summary", "Motivation", "Goals", "Success Metrics"],
    "spec-onepager": ["Problem", "Proposal", "Goals", "Success Metrics"],
    "design": ["Overview", "Architecture Decisions", "Failure Isolation"],
    "design-onepager": ["Context", "Options Comparison", "Decision"],
    "adr": ["Context", "Options", "Decision", "Consequences"],
    "plan": ["Milestones", "Risk Management", "Verification Criteria", "Rollback Plan"],
    "plan-onepager": ["Goal", "Milestones", "Key Risks", "Acceptance Criteria"],
    "one-pager": ["Problem & Goal", "Solution", "Execution Plan", "Risks & Acceptance"],
}


# ── 任務表欄位契約 ──────────────────────────────────────────────

PLAN_FULL_COLUMNS = 7  # # | 任務 | 角色 | 產出檔案 | 估時 | AC-ID | AC
PLAN_ONEPAGER_COLUMNS = 4  # # | 任務 | 產出檔案 | AC
VALID_ROLES = {"coder", "ai-dev", "qa", "human"}


# ── 空白章節 placeholder 模式 ───────────────────────────────────

PLACEHOLDER_PATTERNS = [
    re.compile(r"^\s*\.{3}\s*$"),          # ...
    re.compile(r"^\s*TODO\b", re.IGNORECASE),  # TODO / todo
    re.compile(r"^\{[^}]*\}$"),            # {placeholder} / {...}
    re.compile(r"^\s*（待填）\s*$"),        # （待填）
    re.compile(r"^\s*\(TBD\)\s*$", re.IGNORECASE),  # (TBD)
]

# 模板預設句（匹配含這些關鍵片段的行，視為 placeholder）
TEMPLATE_DEFAULT_FRAGMENTS = [
    "一段話描述",
    "describe the",
    "one paragraph",
    "{",
]

MIN_SECTION_CONTENT_CHARS = 20


# ── 解析工具 ────────────────────────────────────────────────────

def parse_frontmatter(content: str) -> dict[str, str]:
    """從 Markdown 內容中解析 YAML frontmatter。"""
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}

    frontmatter: dict[str, str] = {}
    for line in match.group(1).split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            frontmatter[key.strip()] = value.strip().strip('"').strip("'")
    return frontmatter


def extract_headings(content: str) -> list[str]:
    """提取所有 Markdown 標題文字。"""
    headings: list[str] = []
    for line in content.split("\n"):
        match = re.match(r"^#{1,6}\s+(.+)", line)
        if match:
            heading = match.group(1).strip()
            heading = re.sub(r"^\d+(\.\d+)*\.?\s*", "", heading)
            heading = re.sub(r"\（.*?\）", "", heading)
            heading = re.sub(r"\(.*?\)", "", heading)
            headings.append(heading.strip())
    return headings


def extract_sections(content: str) -> dict[str, str]:
    """提取每個章節標題及其完整內容（含子標題）。

    以 ##（二級標題）為章節邊界。所有內容（包括子標題 ### 以下）
    都歸入最近的 ## 父章節。
    """
    sections: dict[str, str] = {}
    lines = content.split("\n")
    current_heading: str | None = None
    current_body: list[str] = []

    for line in lines:
        # 只以 ## 級（二級）標題作為章節分界
        heading_match = re.match(r"^##\s+(.+)", line)
        if heading_match:
            # 存入前一章節
            if current_heading is not None:
                sections[current_heading] = "\n".join(current_body)
            raw_heading = heading_match.group(1).strip()
            raw_heading = re.sub(r"^\d+(\.\d+)*\.?\s*", "", raw_heading)
            raw_heading = re.sub(r"\（.*?\）", "", raw_heading)
            raw_heading = re.sub(r"\(.*?\)", "", raw_heading)
            current_heading = raw_heading.strip()
            current_body = []
        else:
            current_body.append(line)

    # 最後一個章節
    if current_heading is not None:
        sections[current_heading] = "\n".join(current_body)

    return sections


def _is_placeholder_line(line: str) -> bool:
    """判斷一行是否為 placeholder。"""
    stripped = line.strip()
    if not stripped:
        return True
    for pat in PLACEHOLDER_PATTERNS:
        if pat.match(stripped):
            return True
    for frag in TEMPLATE_DEFAULT_FRAGMENTS:
        if frag.lower() in stripped.lower():
            return True
    return False


def _meaningful_char_count(body: str) -> int:
    """計算章節中非空白、非 placeholder 的有效字元數。"""
    count = 0
    for line in body.split("\n"):
        stripped = line.strip()
        # 跳過空行、表格分隔列、frontmatter 分隔
        if not stripped or re.match(r"^[\s\-:|]+$", stripped) or stripped == "---":
            continue
        if _is_placeholder_line(line):
            continue
        # 跳過純表格標題列（以 | 開頭且含多個 |）
        # 不跳過——表格資料列可能有有效內容
        count += len(stripped)
    return count


def check_empty_sections(content: str, doc_type: str, language: str) -> list[str]:
    """檢查必要章節是否為空或僅含 placeholder。"""
    errors: list[str] = []
    sections_map = REQUIRED_SECTIONS_EN if language == "en" else REQUIRED_SECTIONS_ZH
    required = sections_map.get(doc_type, [])
    if not required:
        return errors

    sections = extract_sections(content)
    sections_lower = {k.lower(): v for k, v in sections.items()}

    for section in required:
        # 找到匹配的章節
        body: str | None = None
        for heading, content_body in sections_lower.items():
            if section.lower() in heading:
                body = content_body
                break

        if body is None:
            # 章節不存在——由 check_file 的章節存在性檢查處理
            continue

        char_count = _meaningful_char_count(body)
        if char_count < MIN_SECTION_CONTENT_CHARS:
            errors.append(
                f"章節「{section}」內容不足（有效字元 {char_count} < {MIN_SECTION_CONTENT_CHARS}），"
                f"疑似空白或僅含 placeholder"
            )

    return errors


# ── 自動化 checklist 可驗項（M2.3）─────────────────────────────

def check_design_alternatives(content: str, doc_type: str) -> list[str]:
    """Design/ADR：至少 2 個替代方案。"""
    errors: list[str] = []
    if doc_type not in ("design", "design-onepager", "adr"):
        return errors

    # 計算選項：尋找 ### 選項/Option 標題 或 表格中選項列
    option_headings = 0
    option_table_rows = 0

    for line in content.split("\n"):
        # 選項標題（### 選項 A / ### Option A）
        if re.match(r"^###\s+(選項|Option)\s+\w", line, re.IGNORECASE):
            option_headings += 1
        # 方案標題（### 方案 A）
        if re.match(r"^###\s+方案\s+\w", line, re.IGNORECASE):
            option_headings += 1
        # 表格列：以 | A: / | B: 開頭的選項列
        if re.match(r"^\|\s*[A-Z][\s:：]", line):
            option_table_rows += 1

    alternatives = max(option_headings, option_table_rows)
    if alternatives < 2:
        errors.append(
            f"Design/ADR 必須列出至少 2 個替代方案（偵測到 {alternatives} 個）"
        )

    return errors


def check_spec_nfr_quantified(content: str, doc_type: str) -> list[str]:
    """Spec：NFR 章節含數字（量化指標）。"""
    errors: list[str] = []
    if doc_type not in ("spec", "spec-onepager"):
        return errors

    # 找 NFR / 非功能性需求 章節
    sections = extract_sections(content)
    nfr_body: str | None = None
    for heading, body in sections.items():
        if any(k in heading.lower() for k in ["非功能性需求", "nfr", "non-functional"]):
            nfr_body = body
            break

    if nfr_body is None:
        # 沒有 NFR 章節——不額外報錯（由章節存在性檢查處理）
        return errors

    # 檢查是否含數字（排除表格分隔列）
    has_number = False
    for line in nfr_body.split("\n"):
        stripped = line.strip()
        if re.match(r"^[\s\-:|]+$", stripped):
            continue
        if re.search(r"\d+", stripped):
            has_number = True
            break

    if not has_number:
        errors.append("Spec NFR 章節缺少量化指標（應含具體數字）")

    return errors


# ── 任務表契約檢查 ──────────────────────────────────────────────

def check_plan_task_table(content: str, doc_type: str) -> list[str]:
    """檢查 plan 任務表是否符合 executor 格式契約。"""
    errors: list[str] = []

    expected_cols = PLAN_FULL_COLUMNS if doc_type == "plan" else PLAN_ONEPAGER_COLUMNS

    lines = content.split("\n")
    task_tables_found = 0

    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if re.match(r"^\|.*#.*\|", stripped):
            header_cells = [c.strip() for c in stripped.strip("|").split("|")]
            header_lower = [h.lower() for h in header_cells]
            is_task_table = (
                "#" in header_lower
                and any(k in " ".join(header_lower) for k in ["任務", "task"])
            )
            if is_task_table:
                task_tables_found += 1
                actual_cols = len(header_cells)
                if actual_cols != expected_cols:
                    errors.append(
                        f"任務表欄位數不符 executor 契約：期望 {expected_cols} 欄，實際 {actual_cols} 欄"
                        f"（標題列：{stripped}）"
                    )
                i += 1
                if i < len(lines) and re.match(r"^\|[\s\-:|]+\|$", lines[i].strip()):
                    i += 1
                while i < len(lines):
                    row_stripped = lines[i].strip()
                    if not re.match(r"^\|.*\|$", row_stripped):
                        break
                    cells = [c.strip() for c in row_stripped.strip("|").split("|")]
                    if all(c in ("...", "") for c in cells):
                        i += 1
                        continue
                    if len(cells) != expected_cols:
                        errors.append(
                            f"任務表第 {i + 1} 行欄位數不符：期望 {expected_cols}，實際 {len(cells)}"
                        )
                    if doc_type == "plan" and len(cells) >= 3:
                        role = cells[2].lower().strip().strip("`")
                        if role and role != "..." and role not in VALID_ROLES:
                            errors.append(
                                f"任務表角色值不合法：'{cells[2].strip()}'"
                                f"（允許值：{', '.join(sorted(VALID_ROLES))}）"
                            )
                    i += 1
                continue
        i += 1

    if task_tables_found == 0:
        errors.append("未偵測到任務表（需含 | # | 任務/Task | 欄位的表格）")

    return errors


# ── 主檢查函式 ──────────────────────────────────────────────────

def check_file(filepath: Path) -> list[str]:
    """檢查單一文件，回傳錯誤清單。"""
    errors: list[str] = []

    if not filepath.exists():
        return [f"檔案不存在：{filepath}"]

    content = filepath.read_text(encoding="utf-8")

    # 檢查 frontmatter
    frontmatter = parse_frontmatter(content)
    if not frontmatter:
        errors.append("缺少 YAML frontmatter（---...--- 區塊）")
        return errors

    for field in REQUIRED_FRONTMATTER:
        if field not in frontmatter or not frontmatter[field]:
            errors.append(f"frontmatter 缺少必要欄位：{field}")

    # 判斷文件類型
    doc_type = frontmatter.get("type", "")
    if not doc_type:
        path_str = str(filepath)
        if "one-pagers" in path_str:
            doc_type = "one-pager"
        elif "specs" in path_str:
            doc_type = "spec"
        elif "adr" in path_str:
            doc_type = "adr"
        elif "designs" in path_str:
            doc_type = "design"
        elif "plans" in path_str:
            doc_type = "plan"

    if not doc_type:
        errors.append("無法判斷文件類型（frontmatter 缺少 type 欄位）")
        return errors

    # 判斷語言
    language = frontmatter.get("language", "zh-TW")
    sections_map = REQUIRED_SECTIONS_EN if language == "en" else REQUIRED_SECTIONS_ZH

    # 檢查必要章節
    required = sections_map.get(doc_type, [])
    if not required:
        errors.append(f"未知的文件類型：{doc_type}")
        return errors

    headings = extract_headings(content)
    headings_lower = [h.lower() for h in headings]

    for section in required:
        found = any(section.lower() in h for h in headings_lower)
        if not found:
            errors.append(f"缺少必要章節：{section}")

    # 空白章節檢查（M2.2）
    empty_errors = check_empty_sections(content, doc_type, language)
    errors.extend(empty_errors)

    # 自動化 checklist（M2.3）
    errors.extend(check_design_alternatives(content, doc_type))
    errors.extend(check_spec_nfr_quantified(content, doc_type))

    # 任務表欄位契約驗證（僅 plan / plan-onepager）
    if doc_type in ("plan", "plan-onepager"):
        table_errors = check_plan_task_table(content, doc_type)
        errors.extend(table_errors)

    return errors


# ── 中英模板 Parity Check（M4.4）────────────────────────────────

SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = SKILL_ROOT / "references" / "templates"


def _count_table_columns(content: str) -> list[int]:
    """提取所有表格的欄位數。"""
    col_counts: list[int] = []
    for line in content.split("\n"):
        stripped = line.strip()
        if re.match(r"^\|.*\|$", stripped) and not re.match(r"^\|[\s\-:|]+\|$", stripped):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            col_counts.append(len(cells))
    return col_counts


def _extract_frontmatter_keys(content: str) -> list[str]:
    """提取 frontmatter 所有欄位名稱。"""
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return []
    keys: list[str] = []
    for line in match.group(1).split("\n"):
        if ":" in line:
            key = line.split(":", 1)[0].strip()
            if key:
                keys.append(key)
    return keys


def _count_headings(content: str) -> int:
    """計算標題數。"""
    count = 0
    for line in content.split("\n"):
        if re.match(r"^#{1,6}\s+", line):
            count += 1
    return count


def check_template_parity() -> list[str]:
    """比對每對模板的章節數、frontmatter 欄位、表格欄數。"""
    errors: list[str] = []
    zh_dir = TEMPLATES_DIR / "zh-TW"
    en_dir = TEMPLATES_DIR / "en"

    if not zh_dir.exists() or not en_dir.exists():
        errors.append("模板目錄不存在")
        return errors

    zh_files = {f.name for f in zh_dir.glob("*.md")}
    en_files = {f.name for f in en_dir.glob("*.md")}

    # 檢查檔案對稱
    only_zh = zh_files - en_files
    only_en = en_files - zh_files
    if only_zh:
        errors.append(f"僅存在 zh-TW 模板：{', '.join(sorted(only_zh))}")
    if only_en:
        errors.append(f"僅存在 en 模板：{', '.join(sorted(only_en))}")

    # 逐一比對
    common = zh_files & en_files
    for filename in sorted(common):
        zh_content = (zh_dir / filename).read_text(encoding="utf-8")
        en_content = (en_dir / filename).read_text(encoding="utf-8")

        # 章節數
        zh_headings = _count_headings(zh_content)
        en_headings = _count_headings(en_content)
        if zh_headings != en_headings:
            errors.append(
                f"[{filename}] 章節數不一致：zh-TW={zh_headings}, en={en_headings}"
            )

        # frontmatter 欄位
        zh_keys = _extract_frontmatter_keys(zh_content)
        en_keys = _extract_frontmatter_keys(en_content)
        if set(zh_keys) != set(en_keys):
            zh_only = set(zh_keys) - set(en_keys)
            en_only = set(en_keys) - set(zh_keys)
            diff_parts: list[str] = []
            if zh_only:
                diff_parts.append(f"zh-TW 多出 {zh_only}")
            if en_only:
                diff_parts.append(f"en 多出 {en_only}")
            errors.append(f"[{filename}] frontmatter 欄位不一致：{'; '.join(diff_parts)}")

        # 表格欄數
        zh_tables = _count_table_columns(zh_content)
        en_tables = _count_table_columns(en_content)
        if len(zh_tables) != len(en_tables):
            errors.append(
                f"[{filename}] 表格數量不一致：zh-TW={len(zh_tables)}, en={len(en_tables)}"
            )
        else:
            for idx, (zh_cols, en_cols) in enumerate(zip(zh_tables, en_tables)):
                if zh_cols != en_cols:
                    errors.append(
                        f"[{filename}] 第 {idx + 1} 個表格欄位數不一致："
                        f"zh-TW={zh_cols}, en={en_cols}"
                    )

    return errors


# ── CLI 入口 ────────────────────────────────────────────────────

def main() -> int:
    """主程式入口。"""
    if len(sys.argv) < 2:
        print("用法：python -m scripts.check_doc_completeness <file1.md> [file2.md ...]")
        print("      python -m scripts.check_doc_completeness --parity")
        return 1

    # Parity check 模式
    if sys.argv[1] == "--parity":
        errors = check_template_parity()
        if errors:
            print("❌ 模板 Parity Check 失敗：")
            for e in errors:
                print(f"   - {e}")
            return 1
        else:
            print("✅ 中英模板 Parity Check 通過")
            return 0

    all_passed = True

    for arg in sys.argv[1:]:
        filepath = Path(arg)
        errors = check_file(filepath)

        if errors:
            all_passed = False
            print(f"\n❌ FAIL: {filepath}")
            for err in errors:
                print(f"   - {err}")
        else:
            print(f"✅ PASS: {filepath}")

    if all_passed:
        print("\n🎉 所有文件通過完整性檢查。")
        return 0
    else:
        print("\n⚠️  部分文件未通過檢查，請補齊缺失項目。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
