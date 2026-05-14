#!/usr/bin/env python3
"""ark-webapp-generator 產出檔案完整性驗證腳本。

依據 references/file-manifest.md 中定義的 29 個檔案清單，
檢查目標目錄下所有必要檔案是否存在。

使用方式：
    python scripts/validate_output.py <output_dir>/<project_name>
    python scripts/validate_output.py ./output/my_project

範例：
    $ python scripts/validate_output.py ./output/ark_slot_analyzer
    ✅ 驗證通過：31/31 個檔案皆已產出
"""

import sys
from pathlib import Path


# ark-webapp-generator 產出的 31 個必要檔案（依 file-manifest.md）
REQUIRED_FILES: list[str] = [
    # 專案設定檔案（4）
    "requirements.txt",
    ".env.example",
    ".gitignore",
    "pytest.ini",
    # Skill 插件系統（8）
    "src/__init__.py",
    "src/skills/__init__.py",
    "src/skills/base.py",
    "src/skills/registry.py",
    "src/skills/internal/__init__.py",
    "src/skills/internal/echo.py",
    "src/skills/external/__init__.py",
    "src/skills/marketplace/__init__.py",
    # FastAPI Server（10）
    "src/server/__init__.py",
    "src/server/main.py",
    "src/server/core/config.py",
    "src/server/core/errors.py",
    "src/server/api/router.py",
    "src/server/api/health.py",
    "src/server/api/skills.py",
    "src/server/api/chat.py",
    "src/server/models/slot_mechanics.py",
    "src/server/models/vibe_score.py",
    # Web Chat UI（4）
    "src/server/templates/base.html",
    "src/server/templates/index.html",
    "src/server/static/css/style.css",
    "src/server/static/js/app.js",
    # 測試檔案（3）
    "tests/conftest.py",
    "tests/test_health.py",
    "tests/test_skills.py",
]


def validate_output(project_dir: str) -> tuple[list[str], list[str]]:
    """驗證產出檔案完整性。

    Args:
        project_dir: 目標專案目錄路徑。

    Returns:
        (found, missing) — 已存在與缺失的檔案路徑清單。
    """
    root = Path(project_dir)
    found: list[str] = []
    missing: list[str] = []

    for rel_path in REQUIRED_FILES:
        full_path = root / rel_path
        if full_path.is_file():
            found.append(rel_path)
        else:
            missing.append(rel_path)

    return found, missing


def main() -> None:
    """CLI 入口：驗證產出檔案並輸出結果。"""
    if len(sys.argv) < 2:
        print("使用方式: python validate_output.py <project_dir>")
        print("範例:     python validate_output.py ./output/my_project")
        sys.exit(1)

    project_dir = sys.argv[1]
    root = Path(project_dir)

    if not root.is_dir():
        print(f"❌ 目錄不存在: {root}")
        sys.exit(1)

    found, missing = validate_output(project_dir)
    total = len(REQUIRED_FILES)

    if not missing:
        print(f"✅ 驗證通過：{total}/{total} 個檔案皆已產出")
        sys.exit(0)
    else:
        print(f"❌ 驗證失敗：{len(found)}/{total} 個檔案已產出，{len(missing)} 個缺失\n")
        print("缺失檔案：")
        for path in missing:
            print(f"  - {path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
