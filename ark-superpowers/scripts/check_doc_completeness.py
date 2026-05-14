"""文件完整性檢查腳本。

驗證 docs/specs/、docs/designs/、docs/plans/ 下的標準化文件
是否符合 ark-superpowers 格式要求（frontmatter + 必要章節）。

用法：
    python -m scripts.check_doc_completeness docs/specs/my-spec.md
    python -m scripts.check_doc_completeness docs/specs/*.md
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


# 必要的 frontmatter 欄位
REQUIRED_FRONTMATTER = ["title", "status", "created"]

# 依文件類型對應的必要章節（繁中）
REQUIRED_SECTIONS_ZH: dict[str, list[str]] = {
    "spec": ["摘要", "動機", "目標與非目標", "成功指標"],
    "spec-onepager": ["問題", "提案", "目標", "成功指標"],
    "design": ["概述", "架構決策", "故障隔離"],
    "design-onepager": ["背景", "方案比較", "決策"],
    "adr": ["狀態", "背景", "選項", "決策", "後果"],
    "plan": ["里程碑", "風險管理", "驗證標準", "回滾計畫"],
    "plan-onepager": ["目標", "里程碑", "關鍵風險", "驗收條件"],
}

# 依文件類型對應的必要章節（英文）
REQUIRED_SECTIONS_EN: dict[str, list[str]] = {
    "spec": ["Summary", "Motivation", "Goals", "Success Metrics"],
    "spec-onepager": ["Problem", "Proposal", "Goals", "Success Metrics"],
    "design": ["Overview", "Architecture Decisions", "Failure Isolation"],
    "design-onepager": ["Context", "Options Comparison", "Decision"],
    "adr": ["Status", "Context", "Options", "Decision", "Consequences"],
    "plan": ["Milestones", "Risk Management", "Verification Criteria", "Rollback Plan"],
    "plan-onepager": ["Goal", "Milestones", "Key Risks", "Acceptance Criteria"],
}


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
            # 移除編號前綴（如 "1. " 或 "4.1 "）和括號內容
            heading = match.group(1).strip()
            heading = re.sub(r"^\d+(\.\d+)*\.?\s*", "", heading)
            heading = re.sub(r"\（.*?\）", "", heading)
            heading = re.sub(r"\(.*?\)", "", heading)
            headings.append(heading.strip())
    return headings


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
        # 從路徑推斷
        path_str = str(filepath)
        if "specs" in path_str:
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
        # 模糊匹配：章節標題包含關鍵字即可
        found = any(section.lower() in h for h in headings_lower)
        if not found:
            errors.append(f"缺少必要章節：{section}")

    return errors


def main() -> int:
    """主程式入口。"""
    if len(sys.argv) < 2:
        print("用法：python -m scripts.check_doc_completeness <file1.md> [file2.md ...]")
        return 1

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
