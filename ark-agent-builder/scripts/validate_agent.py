"""validate_agent.py — 驗證 AI Agent 專案結構完整性。

Usage:
    python validate_agent.py [project_dir]
"""
from __future__ import annotations

import sys
from pathlib import Path


def validate(project_dir: Path) -> list[str]:
    """驗證專案結構，回傳錯誤清單。"""
    errors: list[str] = []

    # 必要檔案
    required_files = [
        ("src/skills/base.py", "Skill 介面"),
        ("src/skills/registry.py", "Skill 管理"),
        ("src/skills/internal/echo.py", "Echo Skill"),
        ("src/skills/internal/llm_cli.py", "Agent CLI Skill"),
        ("src/bot/main.py", "Bot 入口"),
        ("src/bot/handlers.py", "訊息處理"),
        ("src/conversation/planner.py", "意圖路由"),
        ("config/news_sources.yaml", "新聞來源設定"),
        ("config/llm_prompts.yaml", "LLM 提詞"),
        (".env.example", "環境變數範本"),
        ("requirements.txt", "依賴清單"),
        ("start.bat", "啟動腳本"),
    ]

    for path, desc in required_files:
        if not (project_dir / path).exists():
            errors.append(f"❌ 缺少 {path} ({desc})")

    # 必要目錄
    required_dirs = [
        "src/skills/internal",
        "src/bot",
        "src/llm",
        "src/conversation",
        "config",
        "data",
        "output",
    ]

    for d in required_dirs:
        if not (project_dir / d).is_dir():
            errors.append(f"❌ 缺少目錄 {d}/")

    # __init__.py 檢查
    init_dirs = ["src", "src/skills", "src/skills/internal", "src/bot", "src/llm", "src/conversation"]
    for d in init_dirs:
        if not (project_dir / d / "__init__.py").exists():
            errors.append(f"⚠️ 缺少 {d}/__init__.py")

    # 內容檢查
    base_py = project_dir / "src/skills/base.py"
    if base_py.exists():
        content = base_py.read_text(encoding="utf-8")
        if "BaseSkill" not in content:
            errors.append("❌ base.py 缺少 BaseSkill 類別")
        if "SkillResult" not in content:
            errors.append("❌ base.py 缺少 SkillResult")

    llm_cli = project_dir / "src/skills/internal/llm_cli.py"
    if llm_cli.exists():
        content = llm_cli.read_text(encoding="utf-8")
        if "LlmCliSkill" not in content:
            errors.append("❌ llm_cli.py 缺少 LlmCliSkill 類別")
        if "BACKENDS" not in content:
            errors.append("❌ llm_cli.py 缺少 BACKENDS 設定")

    return errors


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    errors = validate(target)

    if errors:
        print(f"🔍 驗證結果：{len(errors)} 個問題\n")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    else:
        print("✅ 驗證通過 — 專案結構完整")
        print("\n💡 啟動方式：")
        print("  cp .env.example .env")
        print("  pip install -r requirements.txt")
        print("  python -m src.bot.main")
