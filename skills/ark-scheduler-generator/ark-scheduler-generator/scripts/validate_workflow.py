#!/usr/bin/env python3
"""ark-scheduler-generator Phase 3 產出檔案完整性驗證腳本。

檢查目標專案目錄下所有 Phase 3 新增的必要檔案是否存在。

使用方式：
    python scripts/validate_workflow.py <project_dir>
    python scripts/validate_workflow.py ./output/my_project

範例：
    $ python scripts/validate_workflow.py ./output/ark_slot_analyzer
    ✅ 驗證通過：14/14 個 Phase 3 檔案皆已產出
"""

import sys
from pathlib import Path


# Phase 3 新增的必要檔案清單
PHASE3_REQUIRED_FILES: list[str] = [
    # WorkflowEngine（3）
    "src/workflow/__init__.py",
    "src/workflow/engine.py",
    "src/workflow/context.py",
    # ScheduleEngine（2）
    "src/scheduler/__init__.py",
    "src/scheduler/engine.py",
    # API 路由（2）
    "src/server/api/workflows.py",
    "src/server/api/schedules.py",
    # 新 Skills（2）
    "src/skills/internal/rtp_trend_visualizer.py",
    "src/skills/internal/daily_market_alert.py",
    # Workflow YAML（3）
    "workflows/hello.yaml",
    "workflows/daily_slot_report.yaml",
    "workflows/schedules/slot_morning_report.yaml",
]

# Phase 1 + Phase 2 前置檔案（必須已存在）
PREREQUISITE_FILES: list[str] = [
    # Phase 1 核心
    "src/skills/base.py",
    "src/skills/registry.py",
    "src/server/main.py",
    "requirements.txt",
    ".env.example",
    # Phase 2 核心
    "src/bot/main.py",
    "src/bot/handlers.py",
    "src/llm/adapter.py",
    "src/conversation/memory.py",
    # Phase 1 + 2 Skills
    "src/skills/internal/fetch_slot_game.py",
    "src/skills/internal/parser_slot_game.py",
    "src/skills/internal/wiki_trend_linker.py",
    "src/skills/internal/vibe_analyser.py",
]

# 設定檔更新檢查（檢查內容是否包含 Phase 3 關鍵字）
CONFIG_CHECKS: dict[str, list[str]] = {
    "requirements.txt": [
        "apscheduler",
        "matplotlib",
    ],
}

# 目錄存在檢查
REQUIRED_DIRS: list[str] = [
    "workflows",
    "workflows/schedules",
    "artifacts/charts",
]


def validate_phase3(project_dir: str) -> tuple[list[str], list[str], list[str]]:
    """驗證 Phase 3 產出檔案完整性。

    Args:
        project_dir: 目標專案目錄路徑。

    Returns:
        (found, missing, warnings) — 已存在、缺失、警告的檔案/項目清單。
    """
    root = Path(project_dir)
    found: list[str] = []
    missing: list[str] = []
    warnings: list[str] = []

    # 檢查 Phase 3 新增檔案
    for rel_path in PHASE3_REQUIRED_FILES:
        full_path = root / rel_path
        if full_path.is_file():
            found.append(rel_path)
        else:
            missing.append(rel_path)

    # 檢查前置檔案（Phase 1 + 2）
    for rel_path in PREREQUISITE_FILES:
        full_path = root / rel_path
        if not full_path.is_file():
            warnings.append(f"前置檔案缺失: {rel_path}")

    # 檢查必要目錄
    for rel_dir in REQUIRED_DIRS:
        full_dir = root / rel_dir
        if not full_dir.is_dir():
            warnings.append(f"目錄不存在: {rel_dir}")

    # 檢查設定檔內容更新
    for config_file, keywords in CONFIG_CHECKS.items():
        config_path = root / config_file
        if config_path.is_file():
            content = config_path.read_text(encoding="utf-8")
            for keyword in keywords:
                if keyword.lower() not in content.lower():
                    warnings.append(f"{config_file} 缺少 Phase 3 依賴: {keyword}")
        else:
            warnings.append(f"設定檔不存在: {config_file}")

    return found, missing, warnings


def main() -> None:
    """CLI 入口：驗證 Phase 3 產出檔案並輸出結果。"""
    if len(sys.argv) < 2:
        print("使用方式: python validate_workflow.py <project_dir>")
        print("範例:     python validate_workflow.py ./output/my_project")
        sys.exit(1)

    project_dir = sys.argv[1]
    root = Path(project_dir)

    if not root.is_dir():
        print(f"❌ 目錄不存在: {root}")
        sys.exit(1)

    found, missing, warnings = validate_phase3(project_dir)
    total = len(PHASE3_REQUIRED_FILES)

    # 輸出警告
    if warnings:
        print("⚠️  警告：")
        for warn in warnings:
            print(f"  - {warn}")
        print()

    # 輸出結果
    if not missing:
        print(f"✅ 驗證通過：{total}/{total} 個 Phase 3 檔案皆已產出")
        if warnings:
            print(f"   （{len(warnings)} 個警告，請檢查上方訊息）")
        sys.exit(0)
    else:
        print(f"❌ 驗證失敗：{len(found)}/{total} 個檔案已產出，{len(missing)} 個缺失\n")
        print("缺失檔案：")
        for path in missing:
            print(f"  - {path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
