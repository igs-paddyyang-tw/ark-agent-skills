#!/usr/bin/env python3
"""ark-chatbot-generator Phase 2 產出檔案完整性驗證腳本。

檢查目標專案目錄下所有 Phase 2 新增的必要檔案是否存在。

使用方式：
    python scripts/validate_bot.py <project_dir>
    python scripts/validate_bot.py ./output/my_project

範例：
    $ python scripts/validate_bot.py ./output/ark_slot_analyzer
    ✅ 驗證通過：22/22 個 Phase 2 檔案皆已產出
"""

import sys
from pathlib import Path


# Phase 2 新增的必要檔案清單
PHASE2_REQUIRED_FILES: list[str] = [
    # Telegram Bot（5）
    "src/bot/__init__.py",
    "src/bot/main.py",
    "src/bot/handlers.py",
    "src/bot/permissions.py",
    "src/bot/kiro_handlers.py",
    # LLM 整合層（5）
    "src/llm/__init__.py",
    "src/llm/adapter.py",
    "src/llm/gemini_adapter.py",
    "src/llm/kiro_adapter.py",
    "src/llm/llm_router.py",
    # 對話管理（8）
    "src/conversation/__init__.py",
    "src/conversation/session.py",
    "src/conversation/session_manager.py",
    "src/conversation/memory.py",
    "src/conversation/memory_search.py",
    "src/conversation/user_profiler.py",
    "src/conversation/planner.py",
    "src/conversation/progress.py",
    # Skill 追蹤（1）
    "src/skills/tracker.py",
    # 排程 CRUD API（1）
    "src/server/api/schedules.py",
    # 排程引擎（1）
    "src/scheduler/engine.py",
    # 資料目錄（1）
    "data/memory",
    # 設定檔（1）
    "config/telegram.json",
]

# Phase 1 前置檔案（必須已存在）
PHASE1_PREREQUISITE_FILES: list[str] = [
    "src/skills/base.py",
    "src/skills/registry.py",
    "src/server/main.py",
    "requirements.txt",
    ".env.example",
]

# 設定檔更新檢查（檢查內容是否包含 Phase 2 關鍵字）
CONFIG_CHECKS: dict[str, list[str]] = {
    ".env.example": [
        "TELEGRAM_BOT_TOKEN",
        "GEMINI_API_KEY",
        "ALLOWED_USER_IDS",
        "LLM_BACKEND",
        "KIRO_CLI_CMD",
        "KIRO_WORKSPACE",
    ],
    "requirements.txt": [
        "google-genai",
        "python-telegram-bot",
        "chromadb",
        "mcp",
    ],
}


def validate_phase2(project_dir: str) -> tuple[list[str], list[str], list[str]]:
    """驗證 Phase 2 產出檔案完整性。

    Args:
        project_dir: 目標專案目錄路徑。

    Returns:
        (found, missing, warnings) — 已存在、缺失、警告的檔案/項目清單。
    """
    root = Path(project_dir)
    found: list[str] = []
    missing: list[str] = []
    warnings: list[str] = []

    # 檢查 Phase 2 新增檔案
    for rel_path in PHASE2_REQUIRED_FILES:
        full_path = root / rel_path
        if full_path.is_file() or full_path.is_dir():
            found.append(rel_path)
        else:
            missing.append(rel_path)

    # 檢查 Phase 1 前置檔案
    for rel_path in PHASE1_PREREQUISITE_FILES:
        full_path = root / rel_path
        if not full_path.is_file():
            warnings.append(f"Phase 1 前置檔案缺失: {rel_path}")

    # 檢查設定檔內容更新
    for config_file, keywords in CONFIG_CHECKS.items():
        config_path = root / config_file
        if config_path.is_file():
            content = config_path.read_text(encoding="utf-8")
            for keyword in keywords:
                if keyword not in content:
                    warnings.append(f"{config_file} 缺少 Phase 2 設定: {keyword}")
        else:
            warnings.append(f"設定檔不存在: {config_file}")

    return found, missing, warnings


def main() -> None:
    """CLI 入口：驗證 Phase 2 產出檔案並輸出結果。"""
    if len(sys.argv) < 2:
        print("使用方式: python validate_bot.py <project_dir>")
        print("範例:     python validate_bot.py ./output/my_project")
        sys.exit(1)

    project_dir = sys.argv[1]
    root = Path(project_dir)

    if not root.is_dir():
        print(f"❌ 目錄不存在: {root}")
        sys.exit(1)

    found, missing, warnings = validate_phase2(project_dir)
    total = len(PHASE2_REQUIRED_FILES)

    # 輸出警告
    if warnings:
        print("⚠️  警告：")
        for warn in warnings:
            print(f"  - {warn}")
        print()

    # 輸出結果
    if not missing:
        print(f"✅ 驗證通過：{total}/{total} 個 Phase 2 檔案皆已產出")
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
