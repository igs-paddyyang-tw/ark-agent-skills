#!/usr/bin/env python3
"""build_ai_bot.py — 一鍵建置 ai-bot 專案（串接所有 scaffold）。

使用方式：
    python build_ai_bot.py <project_dir>
    python build_ai_bot.py ai-bot
"""
from __future__ import annotations

import sys
from pathlib import Path

SKILLS_DIR = Path(__file__).resolve().parent.parent.parent  # .kiro/skills/


def main() -> None:
    if len(sys.argv) < 2:
        print("使用方式: python build_ai_bot.py <project_dir>")
        sys.exit(1)

    project_dir = Path(sys.argv[1]).resolve()
    project_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n🤖 建置 ai-bot: {project_dir}\n")

    total_created: list[str] = []

    # Step 1: .kiro/ + .agents/ 配置
    print("── Step 1: AI IDE 配置 (.kiro/.agents/) ──")
    kiro_script = SKILLS_DIR / "ark-webapp-generator" / "scripts" / "scaffold_kiro_config.py"
    if kiro_script.exists():
        ns = {}
        exec(compile(kiro_script.read_text(encoding="utf-8"), str(kiro_script), "exec"), ns)
        created = ns["scaffold"](project_dir)
        total_created.extend(created)
        print(f"   ✅ {len(created)} 個檔案")
    else:
        print("   ⚠️ scaffold_kiro_config.py 不存在，跳過")

    # Step 2: Bot + 對話系統
    print("── Step 2: Telegram Bot ──")
    bot_script = SKILLS_DIR / "ark-chatbot-generator" / "scripts" / "scaffold_bot.py"
    if bot_script.exists():
        ns = {}
        exec(compile(bot_script.read_text(encoding="utf-8"), str(bot_script), "exec"), ns)
        created = ns["scaffold"](project_dir)
        total_created.extend(created)
        print(f"   ✅ {len(created)} 個檔案")
    else:
        print("   ⚠️ scaffold_bot.py 不存在，跳過")

    # Step 3: Workflow + 排程
    print("── Step 3: Workflow + 排程 ──")
    sched_script = SKILLS_DIR / "ark-scheduler-generator" / "scripts" / "scaffold_scheduler.py"
    if sched_script.exists():
        ns = {}
        exec(compile(sched_script.read_text(encoding="utf-8"), str(sched_script), "exec"), ns)
        created = ns["scaffold"](project_dir)
        total_created.extend(created)
        print(f"   ✅ {len(created)} 個檔案")
    else:
        print("   ⚠️ scaffold_scheduler.py 不存在，跳過")

    # Step 4: LLM CLI
    print("── Step 4: LLM CLI ──")
    llm_script = SKILLS_DIR / "ark-llm-cli" / "scripts" / "scaffold_llm_cli.py"
    if llm_script.exists():
        ns = {}
        exec(compile(llm_script.read_text(encoding="utf-8"), str(llm_script), "exec"), ns)
        created = ns["scaffold"](project_dir)
        total_created.extend(created)
        print(f"   ✅ {len(created)} 個檔案")
    else:
        print("   ⚠️ scaffold_llm_cli.py 不存在，跳過")

    # Step 5: 爬蟲（選配）
    print("── Step 5: 爬蟲（選配） ──")
    scraper_script = SKILLS_DIR / "ark-web-scraper" / "scripts" / "scaffold_scraper.py"
    if scraper_script.exists():
        ns = {}
        exec(compile(scraper_script.read_text(encoding="utf-8"), str(scraper_script), "exec"), ns)
        created = ns["scaffold"](project_dir)
        total_created.extend(created)
        print(f"   ✅ {len(created)} 個檔案")
    else:
        print("   ⚠️ scaffold_scraper.py 不存在，跳過")

    # 產出 requirements.txt
    req_path = project_dir / "requirements.txt"
    if not req_path.exists():
        req_path.write_text(
            "fastapi>=0.111.0\n"
            "uvicorn>=0.30.0\n"
            "python-dotenv>=1.0.0\n"
            "pydantic>=2.5.0\n"
            "python-telegram-bot[ext]>=21.0\n"
            "httpx>=0.27.0\n"
            "beautifulsoup4>=4.12.0\n"
            "jinja2>=3.1.0\n"
            "pyyaml>=6.0.0\n"
            "apscheduler>=3.10.0\n"
            "google-genai>=1.0.0\n",
            encoding="utf-8",
        )
        total_created.append("requirements.txt")

    # 產出 .env.example
    env_path = project_dir / ".env.example"
    if not env_path.exists():
        env_path.write_text(
            "TELEGRAM_BOT_TOKEN=your_token\n"
            "ALLOWED_USER_IDS=your_user_id\n"
            "LLM_BACKEND=gemini\n"
            "GEMINI_MODEL=gemini-2.5-flash\n"
            "GEMINI_CLI_CMD=gemini.cmd\n"
            "# AI_BOT_WORKSPACE=.\n",
            encoding="utf-8",
        )
        total_created.append(".env.example")

    # 產出 .gitignore
    gi_path = project_dir / ".gitignore"
    if not gi_path.exists():
        gi_path.write_text(
            ".venv/\n__pycache__/\n*.pyc\n.env\ndata/\noutput/\nartifacts/\n",
            encoding="utf-8",
        )
        total_created.append(".gitignore")

    # 摘要
    print(f"\n{'═' * 50}")
    print(f"✅ 建置完成！共產出 {len(total_created)} 個檔案")
    print(f"{'═' * 50}")
    print(f"\n🚀 下一步：")
    print(f"   1. cd {project_dir.name}")
    print(f"   2. cp .env.example .env  # 填入 Bot Token")
    print(f"   3. pip install -r requirements.txt")
    print(f"   4. gemini  # 登入 Gemini CLI")
    print(f"   5. python -m src.bot.main  # 啟動 Bot")
    print(f"\n   Telegram 輸入 /start 開始對話！")
    print(f"   輸入「幫我寫一個 XXX Skill」→ Bot 自動產出並載入\n")


if __name__ == "__main__":
    main()
