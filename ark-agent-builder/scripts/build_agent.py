"""build_agent.py — 一鍵產出完整 AI Agent Bot 專案。

從 assets/ 複製樣板資源，從 templates/ 產出程式碼。
產出後可直接 `python -m src.bot.main` 或 `start.bat` 啟動。

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


def build_agent(output_dir: Path, project_name: str = "ai-bot") -> list[str]:
    """產出完整 AI Agent Bot 專案。回傳已建立的檔案清單。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []

    # ── 1. 目錄結構 ──────────────────────────────────────────
    dirs = [
        "src/skills/internal",
        "src/bot",
        "src/llm",
        "src/conversation",
        "src/agent",
        "src/server/api",
        "config",
        "templates",
        "output/news",
        "data/memory",
        "tests",
    ]
    for d in dirs:
        (output_dir / d).mkdir(parents=True, exist_ok=True)

    # ── 2. assets → 直接複製 ─────────────────────────────────
    asset_map = {
        "news_sources.yaml": "config/news_sources.yaml",
        "llm_prompts.yaml": "config/llm_prompts.yaml",
        "requirements.txt": "requirements.txt",
        "start.bat": "start.bat",
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

    # ── 3. templates → 程式碼產出 ─────────────────────────────
    template_map = {
        "base.py": "src/skills/base.py",
        "registry.py": "src/skills/registry.py",
        "echo.py": "src/skills/internal/echo.py",
        "llm_cli.py": "src/skills/internal/llm_cli.py",
        "news_scraper.py": "src/skills/internal/news_scraper.py",
        "news_renderer.py": "src/skills/internal/news_renderer.py",
        "session.py": "src/conversation/session.py",
        "planner.py": "src/conversation/planner.py",
        "memory_search.py": "src/conversation/memory_search.py",
        "gemini_chat.py": "src/llm/gemini_chat.py",
        "bot_main.py": "src/bot/main.py",
        "handlers.py": "src/bot/handlers.py",
    }
    for src_name, dst_path in template_map.items():
        src = TEMPLATES_DIR / src_name
        dst = output_dir / dst_path
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
            created.append(dst_path)

    # ── 4. __init__.py 補齊 ───────────────────────────────────
    init_dirs = [
        "src", "src/skills", "src/skills/internal",
        "src/bot", "src/llm", "src/conversation", "src/agent",
        "src/server", "src/server/api",
    ]
    for d in init_dirs:
        init_file = output_dir / d / "__init__.py"
        if not init_file.exists():
            init_file.write_text("", encoding="utf-8")

    # ── 5. HTML 模板 ─────────────────────────────────────────
    template_html = TEMPLATES_DIR / "tech-daily.html"
    dst_html = output_dir / "templates" / "tech-daily.html"
    if template_html.exists() and not dst_html.exists():
        shutil.copy2(template_html, dst_html)
        created.append("templates/tech-daily.html")

    # ── 6. pytest.ini ─────────────────────────────────────────
    pytest_ini = output_dir / "pytest.ini"
    if not pytest_ini.exists():
        pytest_ini.write_text(
            "[pytest]\nasyncio_mode = auto\ntestpaths = tests\n",
            encoding="utf-8",
        )
        created.append("pytest.ini")

    return created


def validate(project_dir: Path) -> list[str]:
    """驗證專案結構完整性。回傳錯誤清單（空=通過）。"""
    errors: list[str] = []
    required = [
        "src/skills/base.py",
        "src/skills/registry.py",
        "src/skills/internal/echo.py",
        "src/skills/internal/llm_cli.py",
        "src/bot/main.py",
        "src/bot/handlers.py",
        "src/conversation/planner.py",
        "config/news_sources.yaml",
        ".env.example",
        "requirements.txt",
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

        # ── 補建 agents/ + knowledge/ 目錄 ──
        agents_dir = out / "agents" / "admin-agent"
        for sub in ("docs", "knowledge/raw", "output", "skills"):
            (agents_dir / sub).mkdir(parents=True, exist_ok=True)
        (out / "knowledge" / "raw").mkdir(parents=True, exist_ok=True)
        (out / "knowledge" / "wiki").mkdir(parents=True, exist_ok=True)

        print(f"\n✅ 產出完成（{len(files)} 個檔案）→ {out}/")
        print(f"\n📋 下一步：")
        print(f"  1. python .kiro/skills/ark-kiro-init/scripts/build_kiro.py --standalone {out}")
        print(f"     → 產出 .kiro/ 配置（SOUL + KIRO + MEMORY + mcp.json）")
        print(f"  2. 編輯 {out}/.kiro/steering/SOUL.md 設計你的 Bot 人格")
        print(f"  3. cp {out}/.env.example {out}/.env  # 填入 Token")
        print(f"  4. cd {out} && pip install -r requirements.txt && python start.py")
