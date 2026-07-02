"""build_agent.py — 一鍵產出完整 AI Agent 專案（對齊 sample/a-agent）。

產出結構：
    {output}/
    ├── start.py
    ├── .env.example
    ├── requirements.txt
    ├── src/
    │   ├── agent/          ← cli + session + memory + planner
    │   ├── bot/            ← Inline Button + handlers
    │   ├── skills/         ← BaseSkill + 5 內建 Skills
    │   ├── wiki/           ← WikiEngine
    │   ├── llm/            ← Gemini Chat
    │   └── server/         ← FastAPI
    ├── agents/             ← 8 Agent 預設配置（從 templates/agents/ 複製）
    ├── config/
    ├── templates/
    ├── knowledge/
    └── tests/

Usage:
    python build_agent.py <output_dir> [project_name]
    python build_agent.py --validate <project_dir>
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = SKILL_ROOT / "assets"
TEMPLATES_DIR = SKILL_ROOT / "templates"
AGENTS_DIR = TEMPLATES_DIR / "agents"


def build_agent(output_dir: Path, project_name: str = "my-agent") -> list[str]:
    """產出完整 AI Agent 專案。回傳已建立的檔案清單。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []

    # ── 1. 目錄結構 ──
    dirs = [
        "src/agent",
        "src/bot",
        "src/skills/internal",
        "src/wiki",
        "src/llm",
        "src/server",
        "config",
        "templates",
        "knowledge/raw",
        "knowledge/wiki",
        "tests",
        "docs",
    ]
    for d in dirs:
        (output_dir / d).mkdir(parents=True, exist_ok=True)

    # ── 2. assets → 直接複製 ──
    asset_map = {
        "news_sources.yaml": "config/news_sources.yaml",
        "llm_prompts.yaml": "config/llm_prompts.yaml",
        "requirements.txt": "requirements.txt",
        "start.bat": "start.bat",
        "start.sh": "start.sh",
        "env.example": ".env.example",
        "gitignore.txt": ".gitignore",
        "tech-daily.html": "templates/tech-daily.html",
    }
    for src_name, dst_path in asset_map.items():
        src = ASSETS_DIR / src_name
        dst = output_dir / dst_path
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
            created.append(dst_path)

    # ── 3. templates → 程式碼產出 ──
    template_map = {
        # Agent 核心
        "agent_cli.py": "src/agent/cli.py",
        "agent_session.py": "src/agent/session.py",
        "agent_memory.py": "src/agent/memory.py",
        "agent_planner.py": "src/agent/planner.py",
        # Bot（Inline Button 版）
        "bot_main.py": "src/bot/main.py",
        "handlers.py": "src/bot/handlers.py",
        # Skills
        "base.py": "src/skills/base.py",
        "registry.py": "src/skills/registry.py",
        "echo.py": "src/skills/internal/echo.py",
        "news.py": "src/skills/internal/news.py",
        "news_renderer.py": "src/skills/internal/news_renderer.py",
        "summarize.py": "src/skills/internal/summarize.py",
        "translate.py": "src/skills/internal/translate.py",
        # Wiki
        "wiki_engine.py": "src/wiki/engine.py",
        # LLM
        "gemini_chat.py": "src/llm/gemini_chat.py",
        # Server
        "server_main.py": "src/server/main.py",
    }
    for src_name, dst_path in template_map.items():
        src = TEMPLATES_DIR / src_name
        dst = output_dir / dst_path
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
            created.append(dst_path)

    # ── 4. __init__.py 補齊 ──
    init_dirs = [
        "src", "src/agent", "src/bot", "src/skills",
        "src/skills/internal", "src/wiki", "src/llm", "src/server",
        "tests",
    ]
    for d in init_dirs:
        init_file = output_dir / d / "__init__.py"
        if not init_file.exists():
            init_file.write_text("", encoding="utf-8")

    # ── 5. agents/ 預設配置（8 Agent）──
    agents_dst = output_dir / "agents"
    if AGENTS_DIR.exists() and not agents_dst.exists():
        shutil.copytree(AGENTS_DIR, agents_dst)
        agent_count = len(list(agents_dst.iterdir()))
        created.append(f"agents/ ({agent_count} agents)")

    # ── 6. knowledge/ 基礎結構 ──
    for fname, content in [
        ("knowledge/schema.md", "# 知識庫 Schema\n\n## 合法 type\nconcept | entity | source | system\n\n## 規則\n- raw/ 只讀\n- wiki/ 由 ingest 產出\n"),
        ("knowledge/index.md", "# Wiki 索引\n\n（ingest 後自動更新）\n"),
        ("knowledge/log.md", "# 操作日誌\n"),
    ]:
        dst = output_dir / fname
        if not dst.exists():
            dst.write_text(content, encoding="utf-8")
            created.append(fname)
    (output_dir / "knowledge" / "wiki" / ".gitkeep").touch()

    # ── 7. start.py ──
    start_py = output_dir / "start.py"
    if not start_py.exists():
        start_py.write_text(
            '"""AI Agent — 一鍵啟動。"""\n'
            "from __future__ import annotations\n\n"
            "import os\nimport threading\nfrom pathlib import Path\n\n\n"
            "def main() -> None:\n"
            "    os.chdir(Path(__file__).parent)\n"
            "    from dotenv import load_dotenv\n"
            "    load_dotenv()\n\n"
            "    tg_token = os.getenv('TELEGRAM_BOT_TOKEN', '')\n"
            "    gemini_key = os.getenv('GEMINI_API_KEY', '')\n\n"
            '    print("═" * 50)\n'
            '    print("  🤖 AI Agent")\n'
            '    print("═" * 50)\n'
            f'    print(f"  Tier 0: ✅ Skills + Wiki + API")\n'
            f'    print(f"  Tier 1: {{\'✅\' if tg_token else \'⬚\'}} Telegram Bot")\n'
            f'    print(f"  Tier 2: {{\'✅\' if gemini_key else \'⬚\'}} Gemini AI")\n'
            '    print("═" * 50)\n\n'
            "    from src.skills.registry import SkillRegistry\n"
            "    registry = SkillRegistry()\n"
            "    count = registry.auto_discover('src.skills.internal')\n"
            f'    print(f"\\n  📦 Skills: {{count}} 個")\n\n'
            "    if tg_token:\n"
            "        from src.bot.main import create_app\n"
            "        bot_app = create_app()\n"
            "        def run_bot():\n"
            "            import asyncio\n"
            "            asyncio.run(bot_app.run_polling(drop_pending_updates=True))\n"
            "        t = threading.Thread(target=run_bot, daemon=True)\n"
            "        t.start()\n"
            '        print("  🤖 Bot: polling 啟動")\n\n'
            f'    print("\\n  🚀 http://localhost:8000\\n")\n'
            "    import uvicorn\n"
            "    uvicorn.run('src.server.main:app', host='0.0.0.0', port=8000, reload=True)\n\n\n"
            'if __name__ == "__main__":\n'
            "    main()\n",
            encoding="utf-8",
        )
        created.append("start.py")

    return created


def validate(project_dir: Path) -> list[str]:
    """驗證專案結構完整性。回傳錯誤清單（空=通過）。"""
    errors: list[str] = []
    required = [
        "src/agent/cli.py",
        "src/agent/session.py",
        "src/agent/memory.py",
        "src/agent/planner.py",
        "src/bot/main.py",
        "src/bot/handlers.py",
        "src/skills/base.py",
        "src/skills/registry.py",
        "src/skills/internal/echo.py",
        "src/wiki/engine.py",
        "src/llm/gemini_chat.py",
        "src/server/main.py",
        "config/news_sources.yaml",
        "agents/admin-agent/.kiro/steering/SOUL.md",
        ".env.example",
        "requirements.txt",
        "start.py",
    ]
    for f in required:
        if not (project_dir / f).exists():
            errors.append(f"❌ 缺少: {f}")
    return errors


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python build_agent.py <output_dir> [project_name]")
        print("       python build_agent.py --validate <project_dir>")
        sys.exit(1)

    if sys.argv[1] == "--validate":
        target = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
        errs = validate(target)
        if errs:
            print("\n".join(errs))
            sys.exit(1)
        print("✅ 驗證通過")
    else:
        out = Path(sys.argv[1])
        name = sys.argv[2] if len(sys.argv) > 2 else out.name
        files = build_agent(out, name)

        print(f"\n✅ 產出完成（{len(files)} 項）→ {out}/")
        print(f"\n📋 下一步：")
        print(f"  1. python .kiro/skills/ark-kiro-init/scripts/build_kiro.py --standalone {out}")
        print(f"     → 產出 .kiro/ 配置（SOUL + KIRO + MEMORY + mcp.json）")
        print(f"  2. 編輯 {out}/.kiro/steering/SOUL.md 設計 Bot 人格")
        print(f"  3. cp {out}/.env.example {out}/.env  # 填入 Token")
        print(f"  4. cd {out} && pip install -r requirements.txt && python start.py")
