"""build_team.py — 一鍵產出完整可獨立運作的 Agent Team 專案。

整合 ark-agent-team-builder + ark-team-core + ark-kiro-init，
確保產出的專案可以直接 `python start.py` 啟動。

Usage:
    python build_team.py <output_dir> [team.yaml]
    python build_team.py --diff <existing_dir>
    python build_team.py --validate <project_dir>

v2.0 — 對齊 game-analytics-team 參考實作
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from datetime import date

import yaml

# ── 常數 ─────────────────────────────────────────────────────

SKILL_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = SKILL_ROOT / "assets"
TEMPLATES_DIR = SKILL_ROOT / "references" / "templates"

# ark_team_core 來源（從參考專案 vendored）
CORE_SOURCE = Path(__file__).resolve().parents[4] / "projects" / "game-analytics-team" / "src" / "ark_team_core"
FALLBACK_CORE = Path(__file__).resolve().parents[3] / "src" / "ark_team_agent"

TODAY = date.today().isoformat()


# ── 主函式 ────────────────────────────────────────────────────

def build_team(output_dir: Path, team_yaml_path: Path | None = None, level: str = "full") -> list[str]:
    """產出完整 Agent Team 專案。level: 'team'=基礎 / 'full'=完整平台。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []

    # 1. team.yaml
    if team_yaml_path and team_yaml_path.exists():
        shutil.copy2(team_yaml_path, output_dir / "team.yaml")
    else:
        _write_default_team_yaml(output_dir)
    created.append("team.yaml")

    with open(output_dir / "team.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    # 2. scheduler.yaml
    if not (output_dir / "scheduler.yaml").exists():
        _write_scheduler_yaml(output_dir, cfg)
    created.append("scheduler.yaml")

    # 3. src/ 核心模組
    if level == "team":
        # team 模式：產出舊結構（ark_team_core + 業務層）
        core_dst = output_dir / "src" / "ark_team_core"
        if not core_dst.exists():
            _vendor_core(core_dst)
        created.append("src/ark_team_core/")

        biz_created = _vendor_business_layer(output_dir, cfg)
        created.extend(biz_created)
    # full 模式：由 generators 產出四層架構（gateway/coordinator/runtime/business）

    # 3c. src/gateway/（入口層：API + Telegram + Gemini Chat）
    if level == "full":
        try:
            from generators.gateway import write_gateway
            created.extend(write_gateway(output_dir))
        except ImportError:
            pass

    # 3d. src/coordinator/（協調層：A2A + DB + Events + Services）
    if level == "full":
        try:
            from generators.coordinator import write_coordinator
            created.extend(write_coordinator(output_dir))
        except ImportError:
            pass

    # 3e. src/runtime/（執行層）
    if level == "full":
        try:
            from generators.runtime import write_runtime
            created.extend(write_runtime(output_dir))
        except ImportError:
            pass

    # 3f. src/business/（業務技能）
    if level == "full":
        try:
            from generators.business import write_business
            created.extend(write_business(output_dir))
        except ImportError:
            pass

    # 3g. src/bootstrap.py（統一入口邏輯）
    if level == "full":
        try:
            from generators.bootstrap import write_bootstrap
            write_bootstrap(output_dir)
            created.append("src/bootstrap.py")
        except ImportError:
            pass

    # 4. start.py（統一入口：API + TG + Daemon + EventBus + Scheduler）
    if not (output_dir / "start.py").exists():
        try:
            from generators.start_py import write_start_py
            write_start_py(output_dir)
        except ImportError:
            _write_start_py(output_dir, cfg)
    created.append("start.py")

    # 5. Watchdog scripts
    for fname in ("start-team.bat", "start-team.sh"):
        src = ASSETS_DIR / fname
        dst = output_dir / fname
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
            created.append(fname)
        elif fname == "start-team.sh" and not dst.exists():
            # fallback: 產出 sh 腳本
            _write_start_team_sh(output_dir)
            created.append(fname)

    # 6. pyproject.toml
    if not (output_dir / "pyproject.toml").exists():
        _write_pyproject(output_dir, cfg)
    created.append("pyproject.toml")

    # 7. requirements.txt
    if not (output_dir / "requirements.txt").exists():
        _write_requirements(output_dir)
    created.append("requirements.txt")

    # 8. .env.example
    if not (output_dir / ".env.example").exists():
        _write_env_example(output_dir, cfg)
    created.append(".env.example")

    # 9. .gitignore
    if not (output_dir / ".gitignore").exists():
        _write_gitignore(output_dir)
    created.append(".gitignore")

    # 10. tasks/
    tasks_dir = output_dir / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    (tasks_dir / "items").mkdir(exist_ok=True)
    board = tasks_dir / "board.json"
    if not board.exists():
        board.write_text(json.dumps({"tasks": []}, indent=2), encoding="utf-8")
    created.append("tasks/board.json")

    # 11. agents/ 目錄骨架
    agents_created = _scaffold_agents(output_dir, cfg)
    created.extend(agents_created)

    # 12. .kiro/ (admin workspace)
    kiro_created = _scaffold_kiro(output_dir, cfg)
    created.extend(kiro_created)

    # 13. docs/ 目錄骨架
    docs_created = _scaffold_docs(output_dir)
    created.extend(docs_created)

    # 14. secrets/ 目錄
    secrets_created = _scaffold_secrets(output_dir)
    created.extend(secrets_created)

    # 15. knowledge/ (團隊級知識庫)
    knowledge_created = _scaffold_team_knowledge(output_dir)
    created.extend(knowledge_created)

    # 15b. apps/web/（Web Dashboard — Next.js）
    if level == "full":
        try:
            from generators.web import write_web
            created.extend(write_web(output_dir))
        except ImportError:
            pass

    # 16. Dockerfile + docker-compose.prod.yml
    if level == "full":
        try:
            from generators.docker import write_docker
            write_docker(output_dir)
            created.append("Dockerfile")
            created.append("docker-compose.prod.yml")
        except ImportError:
            pass

    # 17. tests/
    if level == "full":
        try:
            from generators.tests import write_tests
            write_tests(output_dir)
            created.append("tests/test_api.py")
        except ImportError:
            pass

    # 17b. Phase 1-4 功能（task lifecycle + multi-runtime + kanban + multica）
    if level == "full":
        try:
            from generators.phase1_4 import write_phase1_4
            created.extend(write_phase1_4(output_dir))
        except ImportError:
            pass

    # 18. README.md
    if not (output_dir / "README.md").exists():
        _write_readme(output_dir, cfg)
    created.append("README.md")

    return created


# ── team.yaml ─────────────────────────────────────────────────

def _write_default_team_yaml(output_dir: Path) -> None:
    """產出預設 5 人團隊 team.yaml（對齊 GA Team 格式）。"""
    content = """\
# Agent Team 配置
# 啟動：python start.py

# 團隊名稱（顯示在 Telegram 啟動訊息）
name: "My Agent Team"

# 啟動訊息範例（顯示在 /start 指令）
examples:
  - "「規劃新功能」→ 需求分析派工"
  - "「寫一個 API」→ 程式開發"
  - "「今日科技新聞」→ 市場研究"
  - "「@leader 拆解任務」→ 指定 agent"

channel:
  bot_token_env: TELEGRAM_BOT_TOKEN
  # group_id: -100xxxxxxxxxx        # 有值 = Group Topics；無值 = 純私聊 @mention
  # general_topic_id: 1

# Forum Topics 定義（Group Topics 模式時使用）
# topics:
#   project_daily: 2    # 專案日報
#   news_daily: 3       # 新聞日報
#   assistant_chat: 1   # 助理對話區

access:
  mode: locked
  allowed_users:
    - 123456789                      # 你的 Telegram ID

defaults:
  backend: kiro-cli
  model: auto
  skip_resume: false

# 上下文壓縮觸發百分比（建議值）
# context_compaction:
#   leader: 70       # 派工決策鏈珍貴，早壓縮
#   worker: 75       # 保留當前任務，完成的可丟
#   admin: 85        # 短指令為主，最晚觸發

cost_guard:
  daily_limit_usd: 30.0
  warn_at_percentage: 80
  timezone: Asia/Taipei

hang_detector:
  enabled: true
  timeout_minutes: 60
  escalation_minutes: 180

instances:
  admin-agent:
    working_directory: agents/admin-agent
    description: "👑 Admin — 服務管理、開發維護、團隊指揮"
    private_chat: 123456789
    role: admin
    skip_resume: false

  pm-agent:
    working_directory: agents/pm-agent
    description: "🧠 Leader — 需求分析、派工、驗收"
    role: leader
    skip_resume: false

  ai-dev-agent:
    working_directory: agents/ai-dev-agent
    description: "🤖 AI Dev — AI/ML 架構、Prompt 工程、Agent 設計"
    role: worker
    skip_resume: false

  coder-agent:
    working_directory: agents/coder-agent
    description: "💻 Coder — 全端開發、API 實作、程式碼產出"
    role: worker
    skip_resume: false

  qa-agent:
    working_directory: agents/qa-agent
    description: "🧪 QA — 測試、品質保證、Code Review"
    role: worker
    skip_resume: false

health_port: 13030
"""
    (output_dir / "team.yaml").write_text(content, encoding="utf-8")


# ── scheduler.yaml ────────────────────────────────────────────

def _write_scheduler_yaml(output_dir: Path, cfg: dict) -> None:
    """產出 scheduler.yaml（對齊 GA Team 格式：id + reply_to）。"""
    leader = "pm-agent"
    admin = "admin-agent"
    for name, inst in cfg.get("instances", {}).items():
        inst = inst or {}
        if inst.get("role") == "leader":
            leader = name
        if inst.get("role") == "admin":
            admin = name

    content = f"""\
timezone: Asia/Taipei

jobs:
  # ── 狀態回報 → 管理者私訊 ──────────────────────────────────
  - id: hourly-check
    target: {admin}
    prompt: "⏰ 請用 query_team_status() 查詢團隊狀態，回報在線數量。"
    cron: "0 9-21 * * *"
    reply_to: private

  # ── 每日摘要 ───────────────────────────────────────────────
  - id: daily-summary
    target: {leader}
    prompt: "📋 今日摘要：整理成果 + 明日計劃，reply 回報。"
    cron: "0 21 * * *"
    reply_to: private

  # ── 系統管理摘要 → 管理者私訊 ──────────────────────────────
  - id: daily-ops-report
    target: {admin}
    prompt: |
      📊 產出每日系統管理摘要（私訊回報）：
      1. Agent 狀態（X/N running）
      2. 今日重啟次數
      3. 錯誤通報
    cron: "5 21 * * *"
    reply_to: private

  # ── 每日知識沉澱 → 廣播全員 ─────────────────────────────────
  - id: daily-knowledge-digest
    target: {admin}
    prompt: |
      請用 broadcast_all 廣播：
      「📚 每日知識沉澱時間！請整理今日學到的知識，寫入 knowledge/wiki/。」
    cron: "30 21 * * *"
    reply_to: private
"""
    (output_dir / "scheduler.yaml").write_text(content, encoding="utf-8")


# ── start.py ──────────────────────────────────────────────────

def _write_start_py(output_dir: Path, cfg: dict) -> None:
    """產出 start.py（完整版：CoreDaemon + TelegramAdapter + Scheduler + API）。"""
    pkg_name = output_dir.name.replace("-", "_")
    content = f'''\
"""一鍵啟動 Agent Team（Daemon + Telegram + Scheduler + API）。"""
from __future__ import annotations

import asyncio
import importlib.util
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv()

from ark_team_core import CoreDaemon
from ark_team_core.process import AgentProcess


def _load_module(name: str, path: str):
    """直接載入模組（繞過 __init__.py 依賴問題）。"""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def main() -> None:
    # 確保 logs/ 目錄存在
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / "team.log"
    fmt = "%(asctime)s [%(name)s] %(levelname)s %(message)s"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(fmt))
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(fmt))
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, console_handler])
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    log = logging.getLogger("team")

    base = Path(__file__).resolve().parent
    daemon = CoreDaemon("team.yaml")

    # 事件日誌
    try:
        event_log_mod = _load_module(
            "event_log", str(base / "src" / "{pkg_name}" / "event_log.py")
        )
        event_log = event_log_mod.EventLog()
        event_log.log("system", "startup", f"Team starting ({{len(daemon.config.instances)}} agents)")
        daemon.event_log = event_log
    except Exception as e:
        log.info("EventLog 未載入: %s", e)

    # 業務 MCP Tools（可選）
    try:
        from src.{pkg_name}.mcp_setup import register_tools
        register_tools(daemon.mcp_registry)
        log.info("MCP tools registered")
    except (ImportError, ModuleNotFoundError, Exception) as e:
        log.info("MCP tools 未載入: %s", e)

    # TelegramAdapter
    adapter = None
    try:
        adapter_mod = _load_module(
            "telegram_adapter",
            str(base / "src" / "{pkg_name}" / "telegram_adapter.py"),
        )
        TelegramAdapter = adapter_mod.TelegramAdapter
        adapter = TelegramAdapter(daemon)
    except Exception as e:
        log.warning("TelegramAdapter 未載入: %s", e)

    # HTTP API（MCP tools 的接收端）
    api_task = None
    try:
        api_mod = _load_module("api", str(base / "src" / "{pkg_name}" / "api.py"))
        api_mod.init_api(daemon, adapter)
        port = daemon.config.health_port
        api_task = asyncio.create_task(api_mod.start_api(port=port))
        await asyncio.sleep(1)
        log.info("HTTP API 已啟動 (port %d)", port)
    except Exception as e:
        log.warning("HTTP API 未啟動: %s", e)

    # 啟動所有 agent
    log.info("啟動團隊（%d agents）...", len(daemon.config.instances))
    for name, ic in daemon.config.instances.items():
        proc = AgentProcess(
            name=name,
            working_dir=ic.working_directory,
            model=ic.model,
            skip_resume=ic.skip_resume,
        )
        daemon._agents[name] = proc
        daemon._last_activity[name] = time.time()
        daemon._restart_count[name] = 0
        await proc.start()
        await asyncio.sleep(2)

    log.info("所有 agent 已啟動 (%d/%d)", len(daemon._agents), len(daemon.config.instances))
    daemon._running = True

    # 啟動 Telegram Adapter
    if adapter:
        await adapter.start()
        log.info("Telegram Adapter 已啟動")

    # 排程器
    try:
        scheduler_mod = _load_module(
            "scheduler", str(base / "src" / "ark_team_core" / "scheduler.py")
        )
        scheduler = scheduler_mod.Scheduler(
            send_fn=daemon.send_to,
            timezone_name="Asia/Taipei",
            on_schedule=adapter.set_scheduled_reply_target if adapter else None,
        )
        count = scheduler.load_yaml("scheduler.yaml")
        if count > 0:
            scheduler.start()
            log.info("排程器已啟動（%d jobs）", count)
    except Exception as e:
        log.warning("排程器啟動失敗: %s", e)

    # 主迴圈
    try:
        while daemon._running:
            await asyncio.sleep(30)
            await daemon._health_check()
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        if api_task:
            api_task.cancel()
        if adapter:
            await adapter.stop()
        await daemon.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\\n團隊已停止。")
'''
    (output_dir / "start.py").write_text(content, encoding="utf-8")


# ── 輔助檔案 ──────────────────────────────────────────────────

def _write_requirements(output_dir: Path) -> None:
    """產出 requirements.txt（對齊 GA Team）。"""
    content = """\
pyyaml>=6.0
python-telegram-bot[ext]>=21.0
python-dotenv>=1.0.0
httpx>=0.25.0
fastapi>=0.110.0
uvicorn>=0.27.0
"""
    (output_dir / "requirements.txt").write_text(content, encoding="utf-8")


def _write_env_example(output_dir: Path, cfg: dict) -> None:
    """產出 .env.example。"""
    channel = cfg.get("channel", {}) or {}
    token_env = channel.get("bot_token_env", "TELEGRAM_BOT_TOKEN")
    content = f"""\
# Agent Team 環境變數
{token_env}=your-bot-token-here

# Backend API Port
API_PORT=33333

# RBAC (format: key:role,key:role)
# PLATFORM_API_KEYS=abc123:admin,def456:member

# LLM API Keys (optional)
# GEMINI_API_KEY=your-key-here
# OPENAI_API_KEY=your-key-here

# Database (optional)
# DATABASE_URL=postgresql://user:pass@localhost/db
# GOOGLE_APPLICATION_CREDENTIALS=secrets/service-account.json
"""
    (output_dir / ".env.example").write_text(content, encoding="utf-8")


def _write_gitignore(output_dir: Path) -> None:
    """產出 .gitignore（完整版，對齊 GA Team）。"""
    content = """\
__pycache__/
*.pyc
.env
*.duckdb
*.duckdb.wal
output/
data/
.venv/
logs/
*.log
state/
*.pid
secrets/
!secrets/.gitignore
!secrets/README.md
.DS_Store
Thumbs.db
"""
    (output_dir / ".gitignore").write_text(content, encoding="utf-8")


def _write_pyproject(output_dir: Path, cfg: dict) -> None:
    """產出 pyproject.toml。"""
    project_name = output_dir.name or "my-agent-team"
    content = f"""\
[project]
name = "{project_name}"
version = "0.1.0"
description = "AI Agent 團隊"
requires-python = ">=3.11"
dependencies = [
    "pyyaml>=6.0",
    "python-telegram-bot[ext]>=21.0",
    "python-dotenv>=1.0.0",
    "httpx>=0.25.0",
    "fastapi>=0.110.0",
    "uvicorn>=0.27.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
"""
    (output_dir / "pyproject.toml").write_text(content, encoding="utf-8")


# ── agents/ 骨架 ──────────────────────────────────────────────

def _scaffold_agents(output_dir: Path, cfg: dict) -> list[str]:
    """建立 agents/ 目錄骨架（三件套 + 知識庫五件套 + data/）。"""
    created: list[str] = []
    agents_dir = output_dir / "agents"
    agents_dir.mkdir(exist_ok=True)

    # AGENTS.md（完整版）
    agents_md = agents_dir / "AGENTS.md"
    if not agents_md.exists():
        _write_agents_md(agents_md, cfg)
        created.append("agents/AGENTS.md")

    # 每個 agent 的目錄
    for name, inst in cfg.get("instances", {}).items():
        inst = inst or {}
        wd = inst.get("working_directory", f"agents/{name}")
        if wd == "." or Path(wd).is_absolute():
            continue

        agent_dir = output_dir / wd
        # 三件套 + data/
        for sub in ("docs", "output", "knowledge", "data"):
            d = agent_dir / sub
            if not d.exists():
                d.mkdir(parents=True, exist_ok=True)
                (d / ".gitkeep").touch()

        # 知識庫五件套
        _ensure_knowledge(agent_dir / "knowledge", name)
        created.append(f"{wd}/ (三件套 + 知識庫五件套)")

    return created


def _write_agents_md(path: Path, cfg: dict) -> None:
    """產出完整版 AGENTS.md（含 reply kind + 錯誤處理）。"""
    instances = cfg.get("instances", {})
    n = len(instances)

    lines = [
        f"# 團隊共用行為準則\n",
        f"> 所有 agent 必須遵守。\n",
        f"## 團隊成員（{n} agents）\n",
        "| Instance | 角色 | 職責 |",
        "|----------|------|------|",
    ]
    for name, inst in instances.items():
        inst = inst or {}
        lines.append(f"| {name} | {inst.get('role', 'worker')} | "
                     f"{inst.get('description', '')} |")

    lines.extend([
        "\n## MCP 工具使用規則\n",
        "| 工具 | 用途 | 權限 |",
        "|------|------|------|",
        "| `reply(text, kind)` | 回覆使用者 | 全員 |",
        "| `send_to_instance(instance, msg)` | 跨 agent 通訊 | 全員 |",
        "| `delegate_task(instance, task)` | 派工 | leader only |",
        "| `query_team_status()` | 查詢狀態 | 全員 |",
        "| `log_to_leader(text)` | 私下回報 leader | worker |",
        "\n### reply kind 規則\n",
        '- `kind="primary"` — 最終結論，送到 TG（≤150字）',
        '- `kind="followup"` — 補充資訊（加 ↪️ 前綴）',
        "- 最後一則 reply 必須是 primary\n",
        "## 回覆格式\n",
        "- 繁體中文",
        "- 結論先行",
        "- 不貼 raw stdout / stack trace\n",
        "## 錯誤處理\n",
        "- 工具失敗 → `log_to_leader` 回報",
        "- 不把錯誤丟給使用者",
        "- 可恢復錯誤自行重試 1 次\n",
        "## 協作流程\n",
        "```",
        "使用者 → leader（理解+分派）→ worker（執行）→ leader（整合）→ 使用者",
        "```\n",
        "退回規則：worker 結果不合格 → leader 退回並說明原因，不跳級。",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def _ensure_knowledge(knowledge_dir: Path, agent_name: str) -> None:
    """確保知識庫五件套存在。"""
    knowledge_dir.mkdir(parents=True, exist_ok=True)

    schema = knowledge_dir / "schema.md"
    if not schema.exists():
        schema.write_text(
            f"---\ntitle: \"{agent_name} Knowledge Schema\"\n"
            f"type: system\ncreated: {TODAY}\nupdated: {TODAY}\n---\n\n"
            "# Wiki Schema v3.1\n\n"
            "## 目錄結構\n\n```\nknowledge/\n"
            "├── raw/          → 所有輸入先進這裡\n"
            "├── wiki/         → 由 LLM ingest 產出（不可手動寫入）\n"
            "├── schema.md     → 本文件\n"
            "├── index.md      → 索引目錄\n"
            "└── log.md        → 操作日誌（append-only）\n```\n\n"
            "## Frontmatter（必要）\n\n"
            "```yaml\n---\ntitle: \"頁面標題\"\n"
            "type: concept | entity | source | synthesis | overview\n"
            "tags: [tag1, tag2]\ncreated: YYYY-MM-DD\n"
            "updated: YYYY-MM-DD\nstatus: seedling | developing | mature\n---\n```\n\n"
            "## 操作規則\n\n"
            "| 規則 | 說明 |\n|------|------|\n"
            "| 所有輸入先進 raw/ | Agent、人類、排程都寫 raw |\n"
            "| 修改後同步 | 改 wiki → 必須更新 index.md + log.md |\n"
            "| log append-only | 禁止刪除舊記錄 |\n",
            encoding="utf-8",
        )

    index = knowledge_dir / "index.md"
    if not index.exists():
        index.write_text("# 知識庫索引\n\n（尚無頁面）\n", encoding="utf-8")

    log_md = knowledge_dir / "log.md"
    if not log_md.exists():
        log_md.write_text("# 操作日誌\n\n", encoding="utf-8")

    raw_dir = knowledge_dir / "raw"
    raw_dir.mkdir(exist_ok=True)
    (raw_dir / ".gitkeep").touch()

    wiki_dir = knowledge_dir / "wiki"
    wiki_dir.mkdir(exist_ok=True)
    overview = wiki_dir / "overview.md"
    if not overview.exists():
        overview.write_text(
            f"---\ntitle: \"{agent_name} 概覽\"\ntype: overview\n"
            f"tags: [overview]\ncreated: {TODAY}\nupdated: {TODAY}\n---\n\n"
            f"# {agent_name}\n\n（待填充）\n",
            encoding="utf-8",
        )


# ── .kiro/ admin workspace ────────────────────────────────────

def _scaffold_kiro(output_dir: Path, cfg: dict) -> list[str]:
    """產出 .kiro/ admin workspace（精簡版 ark-kiro-init）。"""
    created: list[str] = []
    kiro_dir = output_dir / ".kiro"

    # steering/
    steering_dir = kiro_dir / "steering"
    steering_dir.mkdir(parents=True, exist_ok=True)

    _write_if_missing(steering_dir / "MEMORY.md",
        "# 🧠 專案記憶\n\n> Agent 工作記憶。每完成一個段落更新。\n\n---\n\n"
        f"## 專案快照\n\n- **建立日期：** {TODAY}\n- **狀態：** 初始化\n\n"
        "## 待辦\n\n- [ ] 填寫 .env\n- [ ] 啟動團隊\n")
    created.append(".kiro/steering/MEMORY.md")

    _write_if_missing(steering_dir / "USER.md",
        "# USER.md — 使用者百科\n\n"
        "## 個人特徵與偏好\n\n- **稱呼：** （填入）\n"
        "- **偏好語言：** 繁體中文\n\n"
        "## 溝通風格\n\n- **回答風格：** 簡短直接\n- **字數限制：** ≤ 100 字\n")
    created.append(".kiro/steering/USER.md")

    _write_if_missing(steering_dir / "AGENTS.md",
        "# 團隊共用規範\n\n> 所有 agent 必須遵守。\n"
        "> **所有回覆使用繁體中文。**\n\n"
        "## 工具使用規則\n\n"
        "- reply(text, kind) — 回覆使用者\n"
        "- send_to_instance — 跨 agent 通訊\n"
        "- log_to_leader — 錯誤/過程私下回報\n\n"
        "## 回覆風格\n\n"
        "- 結論先行\n- 不貼 raw stdout\n- ≤ 150 字\n")
    created.append(".kiro/steering/AGENTS.md")

    # settings/mcp.json
    settings_dir = kiro_dir / "settings"
    settings_dir.mkdir(parents=True, exist_ok=True)
    _write_if_missing(settings_dir / "mcp.json",
        json.dumps({"mcpServers": {}}, indent=2))
    created.append(".kiro/settings/mcp.json")

    # agents/ (admin identity)
    agents_dir = kiro_dir / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    for name, inst in cfg.get("instances", {}).items():
        if (inst or {}).get("role") == "admin":
            _write_if_missing(agents_dir / f"{name}.json",
                json.dumps({
                    "name": name,
                    "description": (inst or {}).get("description", "Admin"),
                    "role": "admin",
                }, indent=2, ensure_ascii=False))
            created.append(f".kiro/agents/{name}.json")
            break

    # prompts/
    prompts_dir = kiro_dir / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    _write_if_missing(prompts_dir / "service-check.md",
        "# 服務檢查\n\n用 query_team_status() 查詢團隊狀態，回報結果。\n")
    created.append(".kiro/prompts/")

    # skills/ (空目錄，由 ark-kiro-init 填充)
    skills_dir = kiro_dir / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    return created


# ── docs/ + secrets/ + knowledge/ ─────────────────────────────

def _scaffold_docs(output_dir: Path) -> list[str]:
    """建立 docs/ 目錄骨架。"""
    created: list[str] = []
    docs_dir = output_dir / "docs"
    for sub in ("specs", "plans", "research"):
        d = docs_dir / sub
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            (d / ".gitkeep").touch()
    created.append("docs/ (specs + plans + research)")
    return created


def _scaffold_secrets(output_dir: Path) -> list[str]:
    """建立 secrets/ 目錄。"""
    created: list[str] = []
    secrets_dir = output_dir / "secrets"
    secrets_dir.mkdir(exist_ok=True)

    gi = secrets_dir / ".gitignore"
    if not gi.exists():
        gi.write_text("*\n!.gitignore\n!README.md\n", encoding="utf-8")

    readme = secrets_dir / "README.md"
    if not readme.exists():
        readme.write_text(
            "# secrets/\n\n此目錄存放金鑰與憑證，已被 .gitignore 排除。\n\n"
            "## 放置方式\n\n- `service-account.json` — GCP 服務帳號金鑰\n"
            "- 其他 API 金鑰檔案\n",
            encoding="utf-8",
        )

    created.append("secrets/ (.gitignore + README.md)")
    return created


def _scaffold_team_knowledge(output_dir: Path) -> list[str]:
    """建立團隊級知識庫（根目錄 knowledge/）。"""
    created: list[str] = []
    knowledge_dir = output_dir / "knowledge"
    _ensure_knowledge(knowledge_dir, "team")
    created.append("knowledge/ (團隊級知識庫五件套)")
    return created


# ── vendor business layer ─────────────────────────────────────

# 業務層來源（從 GA Team 複製）
_BIZ_SOURCE = Path(__file__).resolve().parents[4] / "projects" / "game-analytics-team" / "src" / "ga_team_agent"


def _vendor_business_layer(output_dir: Path, cfg: dict) -> list[str]:
    """產出 src/{pkg}/ 業務層（telegram_adapter + api + event_log + mcp_setup + tools/）。"""
    created: list[str] = []
    pkg_name = output_dir.name.replace("-", "_")
    biz_dst = output_dir / "src" / pkg_name
    biz_dst.mkdir(parents=True, exist_ok=True)

    # __init__.py
    init_py = biz_dst / "__init__.py"
    if not init_py.exists():
        init_py.write_text(
            f'"""{pkg_name} — Agent Team 業務層。"""\nfrom __future__ import annotations\n',
            encoding="utf-8",
        )
        created.append(f"src/{pkg_name}/__init__.py")

    # event_log.py — 完全通用，直接複製
    _copy_or_write(
        src=_BIZ_SOURCE / "event_log.py",
        dst=biz_dst / "event_log.py",
        fallback=_event_log_py(),
        created=created,
        label=f"src/{pkg_name}/event_log.py",
    )

    # api.py — 通用，動態替換 codenames
    if not (biz_dst / "api.py").exists():
        _write_api_py(biz_dst / "api.py", cfg, pkg_name)
        created.append(f"src/{pkg_name}/api.py")

    # telegram_adapter.py — 已被 src/tg_ui/ 取代，不再產出
    # if not (biz_dst / "telegram_adapter.py").exists():
    #     _write_telegram_adapter_py(biz_dst / "telegram_adapter.py", cfg, pkg_name)
    #     created.append(f"src/{pkg_name}/telegram_adapter.py")

    # mcp_setup.py — 空骨架（業務工具由 ark-mcp-builder 疊加）
    if not (biz_dst / "mcp_setup.py").exists():
        (biz_dst / "mcp_setup.py").write_text(_mcp_setup_py(pkg_name), encoding="utf-8")
        created.append(f"src/{pkg_name}/mcp_setup.py")

    # tools/ 骨架
    tools_dst = biz_dst / "tools"
    tools_dst.mkdir(exist_ok=True)
    if not (tools_dst / "__init__.py").exists():
        (tools_dst / "__init__.py").write_text(_tools_init_py(), encoding="utf-8")
        created.append(f"src/{pkg_name}/tools/__init__.py")
    if not (tools_dst / "base.py").exists():
        (tools_dst / "base.py").write_text(_tools_base_py(), encoding="utf-8")
        created.append(f"src/{pkg_name}/tools/base.py")

    return created


def _copy_or_write(src: Path, dst: Path, fallback: str, created: list[str], label: str) -> None:
    """複製來源檔案，若不存在則寫入 fallback。"""
    if dst.exists():
        return
    if src.exists():
        shutil.copy2(src, dst)
    else:
        dst.write_text(fallback, encoding="utf-8")
    created.append(label)


# ── vendor core ───────────────────────────────────────────────

def _vendor_core(dst: Path) -> None:
    """複製 ark_team_core 到目標目錄。"""
    dst.mkdir(parents=True, exist_ok=True)

    if CORE_SOURCE.exists():
        for f in CORE_SOURCE.glob("*.py"):
            if "__pycache__" in str(f):
                continue
            shutil.copy2(f, dst / f.name)
    else:
        # Fallback: 最小版本
        _write_minimal_core(dst)


def _write_minimal_core(dst: Path) -> None:
    """產出最小可運作的 ark_team_core（5 模組）。"""
    (dst / "__init__.py").write_text(
        '"""ark_team_core — 多 Agent 團隊管理核心引擎。"""\n'
        "from __future__ import annotations\n\n"
        '__version__ = "0.1.0"\n\n'
        "from .config import TeamConfig, InstanceConfig, load_config\n"
        "from .process import AgentProcess\n"
        "from .daemon import CoreDaemon\n"
        "from .mcp_registry import McpRegistry, ToolDefinition\n\n"
        '__all__ = ["TeamConfig", "InstanceConfig", "load_config", '
        '"AgentProcess", "CoreDaemon", "McpRegistry", "ToolDefinition"]\n',
        encoding="utf-8",
    )

    # ── config.py ──
    (dst / "config.py").write_text('''\
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import yaml

@dataclass
class InstanceConfig:
    working_directory: str = "."
    description: str = ""
    role: str = "worker"
    model: str = "auto"
    skip_resume: bool = False
    private_chat: int | None = None

@dataclass
class TeamConfig:
    name: str = "Agent Team"
    instances: dict[str, InstanceConfig] = field(default_factory=dict)
    health_port: int = 13030
    model: str = "auto"
    channel: dict = field(default_factory=dict)
    access: dict = field(default_factory=dict)
    cost_guard: dict = field(default_factory=dict)
    hang_detector: dict = field(default_factory=dict)
    examples: list[str] = field(default_factory=list)

def load_config(path: str | Path) -> TeamConfig:
    p = Path(path)
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    instances = {}
    for name, cfg in data.get("instances", {}).items():
        instances[name] = InstanceConfig(
            working_directory=cfg.get("working_directory", "."),
            description=cfg.get("description", ""),
            role=cfg.get("role", "worker"),
            model=cfg.get("model", data.get("defaults", {}).get("model", "auto")),
            skip_resume=cfg.get("skip_resume", False),
            private_chat=cfg.get("private_chat"),
        )
    return TeamConfig(
        name=data.get("name", "Agent Team"),
        instances=instances,
        health_port=data.get("health_port", 13030),
        model=data.get("defaults", {}).get("model", "auto"),
        channel=data.get("channel", {}),
        access=data.get("access", {}),
        cost_guard=data.get("cost_guard", {}),
        hang_detector=data.get("hang_detector", {}),
        examples=data.get("examples", []),
    )
''', encoding="utf-8")

    # ── process.py ──
    (dst / "process.py").write_text('''\
from __future__ import annotations
import asyncio
import logging
from pathlib import Path

log = logging.getLogger("process")

class AgentProcess:
    def __init__(self, name: str, working_dir: str = ".", model: str = "auto", skip_resume: bool = False):
        self.name = name
        self.working_dir = working_dir
        self.model = model
        self.skip_resume = skip_resume
        self._proc: asyncio.subprocess.Process | None = None
        self._running = False

    def _build_cmd(self) -> list[str]:
        cmd = ["kiro-cli", "chat", "--no-interactive", "--trust-all-tools", "--model", self.model]
        if not self.skip_resume:
            cmd.append("--resume")
        return cmd

    async def start(self) -> None:
        cwd = Path(self.working_dir).resolve()
        cwd.mkdir(parents=True, exist_ok=True)
        cmd = self._build_cmd()
        log.info("Starting %s: %s (cwd=%s)", self.name, " ".join(cmd), cwd)
        try:
            self._proc = await asyncio.create_subprocess_exec(
                *cmd, stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd),
            )
            self._running = True
        except Exception as e:
            log.error("Failed to start %s: %s", self.name, e)
            self._running = False

    async def send(self, text: str) -> str | None:
        if not self._proc or not self._proc.stdin:
            return None
        try:
            self._proc.stdin.write((text + "\\n").encode())
            await self._proc.stdin.drain()
            return "sent"
        except Exception as e:
            log.error("Send to %s failed: %s", self.name, e)
            return None

    def is_alive(self) -> bool:
        if not self._proc:
            return False
        return self._proc.returncode is None

    async def kill(self) -> None:
        if self._proc and self.is_alive():
            self._proc.terminate()
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._proc.kill()
        self._running = False
''', encoding="utf-8")

    # ── mcp_registry.py ──
    (dst / "mcp_registry.py").write_text('''\
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable

@dataclass
class ToolDefinition:
    name: str
    description: str
    handler: Callable | None = None
    parameters: dict = field(default_factory=dict)

class McpRegistry:
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, name: str, description: str, handler: Callable | None = None, parameters: dict | None = None) -> None:
        self._tools[name] = ToolDefinition(name=name, description=description, handler=handler, parameters=parameters or {})

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())
''', encoding="utf-8")

    # ── daemon.py ──
    (dst / "daemon.py").write_text('''\
from __future__ import annotations
import asyncio
import logging
import time

from .config import TeamConfig, load_config
from .process import AgentProcess
from .mcp_registry import McpRegistry

log = logging.getLogger("daemon")

class CoreDaemon:
    def __init__(self, config_path: str = "team.yaml"):
        self.config = load_config(config_path)
        self.mcp_registry = McpRegistry()
        self._agents: dict[str, AgentProcess] = {}
        self._running = False
        self._last_activity: dict[str, float] = {}
        self._restart_count: dict[str, int] = {}
        self.event_log = None

    async def send_to(self, instance_name: str, message: str) -> bool:
        agent = self._agents.get(instance_name)
        if not agent:
            log.warning("Agent not found: %s", instance_name)
            return False
        result = await agent.send(message)
        if result:
            self._last_activity[instance_name] = time.time()
        return result is not None

    def get_status(self) -> dict:
        status = {}
        for name, agent in self._agents.items():
            status[name] = {
                "alive": agent.is_alive(),
                "role": self.config.instances[name].role if name in self.config.instances else "unknown",
                "last_activity": self._last_activity.get(name, 0),
                "restarts": self._restart_count.get(name, 0),
            }
        return status

    async def _health_check(self) -> None:
        for name, agent in list(self._agents.items()):
            if not agent.is_alive() and self._running:
                log.warning("Agent %s is dead, restarting...", name)
                self._restart_count[name] = self._restart_count.get(name, 0) + 1
                await agent.start()
                self._last_activity[name] = time.time()

    async def shutdown(self) -> None:
        self._running = False
        log.info("Shutting down %d agents...", len(self._agents))
        for name, agent in self._agents.items():
            await agent.kill()
        log.info("All agents stopped.")
''', encoding="utf-8")

    # ── scheduler.py ──
    (dst / "scheduler.py").write_text('''\
from __future__ import annotations
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable
import yaml

log = logging.getLogger("scheduler")

class Scheduler:
    def __init__(self, send_fn: Callable, timezone_name: str = "Asia/Taipei", on_schedule: Callable | None = None):
        self.send_fn = send_fn
        self.timezone_name = timezone_name
        self.on_schedule = on_schedule
        self._jobs: list[dict] = []
        self._task: asyncio.Task | None = None
        self._running = False

    def load_yaml(self, path: str) -> int:
        p = Path(path)
        if not p.exists():
            return 0
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        self._jobs = data.get("schedules", []) if data else []
        return len(self._jobs)

    def start(self) -> None:
        self._running = True
        self._task = asyncio.ensure_future(self._loop())

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()

    async def _loop(self) -> None:
        while self._running:
            await asyncio.sleep(60)
            now = datetime.now()
            for job in self._jobs:
                if not job.get("enabled", True):
                    continue
                if self._should_run(job, now):
                    target = job.get("target", "")
                    prompt = job.get("prompt", "")
                    if target and prompt:
                        log.info("Scheduler triggering: %s", target)
                        if self.on_schedule:
                            self.on_schedule(target)
                        await self.send_fn(target, prompt)

    def _should_run(self, job: dict, now: datetime) -> bool:
        cron = job.get("cron", "")
        if not cron:
            return False
        parts = cron.split()
        if len(parts) != 5:
            return False
        minute, hour, dom, mon, dow = parts
        if not self._match(minute, now.minute):
            return False
        if not self._match(hour, now.hour):
            return False
        if not self._match(dom, now.day):
            return False
        if not self._match(mon, now.month):
            return False
        if not self._match(dow, now.isoweekday() % 7):
            return False
        return True

    def _match(self, field: str, value: int) -> bool:
        if field == "*":
            return True
        for part in field.split(","):
            if "-" in part:
                lo, hi = part.split("-", 1)
                if int(lo) <= value <= int(hi):
                    return True
            elif part.startswith("*/"):
                step = int(part[2:])
                if value % step == 0:
                    return True
            else:
                if int(part) == value:
                    return True
        return False
''', encoding="utf-8")


def _write_start_team_sh(output_dir: Path) -> None:
    """產出 start-team.sh（Mac/Linux watchdog）。"""
    content = """\
#!/bin/bash
cd "$(dirname "$0")"

while true; do
    echo "[$(date)] Starting Agent Team..."
    python start.py

    if [ -f "restart.flag" ]; then
        rm "restart.flag"
        echo "[$(date)] Restart requested, restarting in 3s..."
        sleep 3
    else
        echo "[$(date)] Stopped."
        break
    fi
done
"""
    sh_path = output_dir / "start-team.sh"
    sh_path.write_text(content, encoding="utf-8")
    # 設定執行權限（Unix）
    try:
        import stat
        sh_path.chmod(sh_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    except Exception:
        pass


# ── README ────────────────────────────────────────────────────

def _write_readme(output_dir: Path, cfg: dict) -> None:
    """產出完整版 README.md。"""
    instances = cfg.get("instances", {})
    project_name = output_dir.name or "Agent Team"
    n = len(instances)

    lines = [
        f"# {project_name}\n",
        f"> {n} Agent 團隊 — 可獨立運作\n",
        "## 啟動方式\n",
        "```bash",
        f"cd {project_name}",
        "py start.py",
        "```\n",
        "## 目錄結構\n",
        "```",
        f"{project_name}/",
        "├── start.py                    # 主入口（CoreDaemon + TG Bot）",
        "├── start-team.bat              # Windows watchdog",
        "├── team.yaml                   # 團隊配置",
        "├── scheduler.yaml              # 排程定義",
        "├── .env                        # 環境變數",
        "├── src/",
        "│   └── ark_team_core/          # 核心引擎（vendored）",
        "├── agents/                     # 各 agent 工作目錄",
        "├── knowledge/                  # 團隊知識庫",
        "├── docs/                       # 文件（specs + plans）",
        "├── secrets/                    # 金鑰（.gitignore）",
        "├── tasks/                      # 任務板",
        "└── .kiro/                      # Admin workspace",
        "```\n",
        "## 環境變數\n",
        "| 變數 | 必要 | 說明 |",
        "|------|------|------|",
    ]

    channel = cfg.get("channel", {}) or {}
    token_env = channel.get("bot_token_env", "TELEGRAM_BOT_TOKEN")
    lines.append(f"| {token_env} | ✅ | TG Bot Token |")
    lines.append("| GEMINI_API_KEY | 選用 | LLM API Key |\n")

    lines.extend([
        "## 團隊成員\n",
        "| Agent | 角色 | 職責 |",
        "|-------|------|------|",
    ])
    for name, inst in instances.items():
        inst = inst or {}
        lines.append(f"| {name} | {inst.get('role', 'worker')} | "
                     f"{inst.get('description', '')} |")

    lines.extend([
        "\n## 依賴\n",
        "```",
        "python-telegram-bot[ext]>=21.0",
        "python-dotenv",
        "pyyaml",
        "httpx",
        "fastapi",
        "uvicorn",
        "```\n",
        "## 快速啟動\n",
        "```bash",
        "# 1. 安裝依賴",
        "pip install -r requirements.txt\n",
        "# 2. 設定環境變數",
        "cp .env.example .env",
        "# 編輯 .env 填入 Telegram Bot Token\n",
        "# 3. 啟動團隊",
        "python start.py",
        "```\n",
    ])
    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


# ── 業務層模板函式 ────────────────────────────────────────────

def _build_codenames(cfg: dict) -> dict:
    """從 team.yaml instances 動態建構 codenames dict。"""
    emoji_map = {
        "admin": "👑", "leader": "🧠", "worker": "🤖",
    }
    role_emoji = {
        "admin": "👑", "leader": "🧠",
    }
    desc_emoji = [
        ("📊", ["data", "數據", "analyst"]),
        ("📰", ["market", "市場", "research"]),
        ("📋", ["report", "報告", "報表"]),
        ("💻", ["coder", "dev", "engineer", "工程"]),
        ("🤖", ["ai", "llm", "ml"]),
        ("⚙️", ["devops", "ops", "維運"]),
        ("🧪", ["qa", "test", "測試"]),
    ]
    result = {}
    for name, inst in cfg.get("instances", {}).items():
        inst = inst or {}
        desc = inst.get("description", "")
        role = inst.get("role", "worker")
        # 從 description 取 emoji（第一個字元）
        if desc and ord(desc[0]) > 127:
            emoji = desc[0]
        else:
            emoji = role_emoji.get(role, "🤖")
        # 取 description 中的角色名（去掉 emoji 和 — 後的說明）
        role_name = desc.split("—")[0].strip().lstrip(emoji).strip() if desc else name
        result[name] = f"{emoji} {role_name}"
    return result


def _write_api_py(path: Path, cfg: dict, pkg_name: str) -> None:
    """產出 api.py（通用版，codenames 動態產出）。"""
    # 嘗試從 GA Team 複製並替換 pkg import
    src = _BIZ_SOURCE / "api.py"
    if src.exists():
        content = src.read_text(encoding="utf-8")
        # 替換 ga_team_agent → {pkg_name}
        content = content.replace("from ga_team_agent", f"from {pkg_name}")
        content = content.replace("from .ga_team_agent", f"from .{pkg_name}")
        # 替換 hardcoded codenames dict
        codenames = _build_codenames(cfg)
        codenames_str = "{\n" + "".join(
            f'    "{k}": "{v}",\n' for k, v in codenames.items()
        ) + "}"
        import re
        content = re.sub(
            r"_CODENAMES\s*=\s*\{[^}]+\}",
            f"_CODENAMES = {codenames_str}",
            content,
            flags=re.DOTALL,
        )
        path.write_text(content, encoding="utf-8")
    else:
        path.write_text(_api_py_fallback(pkg_name, cfg), encoding="utf-8")


def _write_telegram_adapter_py(path: Path, cfg: dict, pkg_name: str) -> None:
    """產出 telegram_adapter.py（通用版，codenames 動態產出）。"""
    src = _BIZ_SOURCE / "telegram_adapter.py"
    if src.exists():
        content = src.read_text(encoding="utf-8")
        # 替換 ga_team_agent → {pkg_name}
        content = content.replace("from ga_team_agent", f"from {pkg_name}")
        # 替換 hardcoded _names dict
        codenames = _build_codenames(cfg)
        names_str = "{\n" + "".join(
            f'            "{k}": "{v}",\n' for k, v in codenames.items()
        ) + "        }"
        import re
        content = re.sub(
            r"_names\s*=\s*\{[^}]+\}",
            f"_names = {names_str}",
            content,
            flags=re.DOTALL,
        )
        path.write_text(content, encoding="utf-8")
    else:
        path.write_text(_telegram_adapter_py_fallback(pkg_name, cfg), encoding="utf-8")


def _event_log_py() -> str:
    return '''\
"""事件日誌 — SQLite 記錄所有團隊事件。"""
from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path

log = logging.getLogger(__name__)


class EventLog:
    """SQLite 事件日誌，保留 30 天。"""

    def __init__(self, db_path: str = "state/events.db") -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                instance TEXT,
                event_type TEXT,
                detail TEXT
            )
        """)
        self._conn.commit()

    def log(self, instance: str, event_type: str, detail: str = "") -> None:
        self._conn.execute(
            "INSERT INTO events (timestamp, instance, event_type, detail) VALUES (?, ?, ?, ?)",
            (time.time(), instance, event_type, detail[:500]),
        )
        self._conn.commit()

    def query(self, instance: str | None = None, event_type: str | None = None,
              limit: int = 50) -> list[dict]:
        sql = "SELECT id, timestamp, instance, event_type, detail FROM events WHERE 1=1"
        params: list = []
        if instance:
            sql += " AND instance = ?"
            params.append(instance)
        if event_type:
            sql += " AND event_type = ?"
            params.append(event_type)
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        return [{"id": r[0], "ts": r[1], "instance": r[2], "type": r[3], "detail": r[4]}
                for r in rows]

    def today_summary(self) -> dict:
        today_start = time.time() - (time.time() % 86400)
        rows = self._conn.execute(
            "SELECT event_type, COUNT(*) FROM events WHERE timestamp > ? GROUP BY event_type",
            (today_start,),
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    def cleanup(self, days: int = 30) -> int:
        cutoff = time.time() - days * 86400
        cur = self._conn.execute("DELETE FROM events WHERE timestamp < ?", (cutoff,))
        self._conn.commit()
        return cur.rowcount
'''


def _mcp_setup_py(pkg_name: str) -> str:
    return f'''\
"""MCP Tools 註冊 — 將業務工具接入 MCP 協議。"""
from __future__ import annotations

from ark_team_core import McpRegistry, ToolDefinition

from {pkg_name}.tools import TOOL_DEFINITIONS

HANDLERS: dict[str, object] = {{
    # 業務工具 handler 在此註冊
    # "tool_name": handler_function,
}}


def register_tools(registry: McpRegistry) -> None:
    """將業務工具註冊到 MCP Server。"""
    for defn in TOOL_DEFINITIONS:
        name = defn["name"]
        handler = HANDLERS.get(name)
        if handler:
            registry.register(ToolDefinition(
                name=name,
                description=defn["description"],
                input_schema=defn["inputSchema"],
                handler=handler,
            ))
'''


def _tools_init_py() -> str:
    return '''\
"""業務 MCP Tools。"""
from __future__ import annotations

# 業務工具定義（由 ark-mcp-builder 疊加）
TOOL_DEFINITIONS: list[dict] = [
    # {
    #     "name": "tool_name",
    #     "description": "工具描述",
    #     "inputSchema": {"type": "object", "properties": {}, "required": []},
    # },
]

__all__ = ["TOOL_DEFINITIONS"]
'''


def _tools_base_py() -> str:
    return '''\
"""MCP Tools 共用基礎設施。"""
from __future__ import annotations

_db = None


def get_db():
    """取得資料庫連線（延遲初始化）。"""
    global _db
    if _db is None:
        # 依專案需求初始化（SQLite / BigQuery / PostgreSQL）
        pass
    return _db


def init_tools(config: dict | None = None) -> None:
    """初始化工具依賴（由 daemon 啟動時呼叫）。"""
    pass
'''


def _api_py_fallback(pkg_name: str, cfg: dict) -> str:
    """api.py fallback（GA Team 來源不可用時）。"""
    codenames = _build_codenames(cfg)
    codenames_str = "{\n" + "".join(
        f'    "{k}": "{v}",\n' for k, v in codenames.items()
    ) + "}"
    return f'''\
"""HTTP API — 處理 agent MCP tool 呼叫（reply/send/status）。"""
from __future__ import annotations

import asyncio
import html as _html_mod
import logging
from typing import TYPE_CHECKING

from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

if TYPE_CHECKING:
    from ark_team_core import CoreDaemon
    from .telegram_adapter import TelegramAdapter

log = logging.getLogger(__name__)
app = FastAPI(title="Team API", version="1.0.0")

_daemon: "CoreDaemon | None" = None
_adapter: "TelegramAdapter | None" = None

_CODENAMES = {codenames_str}


def _format_reply_html(instance: str, text: str, style: str = "chat") -> str:
    if style == "report":
        return text
    header = _CODENAMES.get(instance, f"🤖 {{instance.replace(\'-agent\', \'\')}}")
    body = _html_mod.escape(text)
    return f"<b>{{header}}</b>\\n{{body}}"


def init_api(daemon: "CoreDaemon", adapter: "TelegramAdapter") -> None:
    global _daemon, _adapter
    _daemon = daemon
    _adapter = adapter


class SendRequest(BaseModel):
    instance: str
    message: str
    source: str = ""


class ReplyRequest(BaseModel):
    instance: str
    text: str
    kind: str = "primary"
    style: str = "chat"
    topic_id: int | None = None


class LogRequest(BaseModel):
    instance: str
    source: str = ""
    text: str


class SendPhotoRequest(BaseModel):
    instance: str
    photo_path: str
    caption: str = ""
    chat_id: int | None = None
    topic: int | None = None


class SendDocumentRequest(BaseModel):
    instance: str
    file_path: str
    caption: str = ""
    chat_id: int | None = None
    topic: int | None = None


@app.post("/api/send")
async def api_send(req: SendRequest):
    if not _daemon:
        return {{"ok": False, "error": "daemon not ready"}}
    success = await _daemon.send_to(req.instance, req.message)
    return {{"ok": success}}


@app.post("/api/reply")
async def api_reply(req: ReplyRequest):
    if not _adapter:
        return {{"ok": False, "error": "telegram adapter not ready"}}
    if req.kind == "followup":
        log.info("📝 BUFFERED %s (followup)", req.instance)
        return {{"ok": True, "buffered": True}}
    formatted = _format_reply_html(req.instance, req.text, style=req.style)
    await _adapter._send_reply(formatted, source=req.instance, parse_mode="HTML", topic_id=req.topic_id)
    return {{"ok": True}}


@app.post("/api/log")
async def api_log(req: LogRequest):
    if not _daemon:
        return {{"ok": False, "error": "daemon not ready"}}
    leader = next((n for n, ic in _daemon.config.instances.items() if ic.role == "leader"), None)
    if leader:
        await _daemon.send_to(leader, f"[{{req.source}}] {{req.text}}")
    return {{"ok": True}}


@app.post("/api/send_photo")
async def api_send_photo(req: SendPhotoRequest):
    if not _adapter:
        return {{"ok": False, "error": "telegram adapter not ready"}}
    from pathlib import Path
    photo = Path(req.photo_path)
    if not photo.exists():
        return {{"ok": False, "error": f"file not found: {{req.photo_path}}"}}
    await _adapter._send_photo_reply(photo, caption=req.caption, source=req.instance,
                                     chat_id=req.chat_id, topic=req.topic)
    return {{"ok": True}}


@app.post("/api/send_document")
async def api_send_document(req: SendDocumentRequest):
    if not _adapter:
        return {{"ok": False, "error": "telegram adapter not ready"}}
    from pathlib import Path
    doc = Path(req.file_path)
    if not doc.exists():
        return {{"ok": False, "error": f"file not found: {{req.file_path}}"}}
    await _adapter._send_document_reply(doc, caption=req.caption, source=req.instance,
                                        chat_id=req.chat_id, topic=req.topic)
    return {{"ok": True}}


@app.get("/api/status")
async def api_status():
    if not _daemon:
        return {{"ok": False, "error": "daemon not ready"}}
    return _daemon.get_status()


@app.post("/api/restart/{{name}}")
async def api_restart(name: str):
    if not _daemon:
        return {{"ok": False, "error": "daemon not ready"}}
    proc = _daemon._agents.get(name)
    if not proc:
        return {{"ok": False, "error": f"unknown instance: {{name}}"}}
    await proc.stop()
    await proc.start()
    import time
    _daemon._last_activity[name] = time.time()
    _daemon._restart_count[name] = _daemon._restart_count.get(name, 0) + 1
    return {{"ok": True, "instance": name, "status": "restarted"}}


async def start_api(host: str = "127.0.0.1", port: int = 13030) -> None:
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()
'''


def _telegram_adapter_py_fallback(pkg_name: str, cfg: dict) -> str:
    """telegram_adapter.py 最小可運作 fallback。"""
    codenames = _build_codenames(cfg)
    names_str = "{\n" + "".join(
        f'            "{k}": "{v}",\n' for k, v in codenames.items()
    ) + "        }"
    return f'''\
"""Telegram Adapter — 訊息收發 + 路由。"""
from __future__ import annotations

import asyncio
import html
import logging
import os
import re
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ark_team_core import CoreDaemon

log = logging.getLogger(__name__)


class TelegramAdapter:
    """Telegram Bot 適配器。"""

    def __init__(self, daemon: "CoreDaemon") -> None:
        self.daemon = daemon
        self.config = daemon.config
        self._app = None
        self._reply_targets: dict[str, dict] = {{}}
        self._processing_messages: dict[str, int] = {{}}
        self._agent_messages: dict[int, str] = {{}}
        self._last_send: float = 0
        self._bot_token = os.environ.get(self.config.channel.bot_token_env, "")
        self._admin_name = ""
        self._leader_name = ""
        for name, ic in self.config.instances.items():
            if ic.role == "admin":
                self._admin_name = name
            elif ic.role == "leader":
                self._leader_name = name
        self._default_target = self._leader_name or self._admin_name

    def _get_codename(self, instance: str) -> str:
        _names = {names_str}
        return _names.get(instance, f"🤖 {{instance.replace(\'-agent\', \'\')}}")

    async def start(self) -> None:
        if not self._bot_token:
            log.warning("TELEGRAM_BOT_TOKEN 未設定，跳過 Telegram adapter")
            return
        try:
            from telegram import BotCommand
            from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
        except ImportError:
            log.error("python-telegram-bot 未安裝")
            return

        self._app = ApplicationBuilder().token(self._bot_token).build()
        self._app.add_handler(CommandHandler("start", self._cmd_start))
        self._app.add_handler(CommandHandler("status", self._cmd_status))
        self._app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, self._on_message))

        async def _error_handler(update, context):
            log.error("Telegram error: %s", context.error)
        self._app.add_error_handler(_error_handler)

        await self._app.initialize()
        await self._app.bot.set_my_commands([
            BotCommand("start", "歡迎訊息"),
            BotCommand("status", "團隊狀態"),
        ])
        await self._app.start()
        await self._app.updater.start_polling(drop_pending_updates=True)
        await self._notify_startup()
        log.info("Telegram adapter 已啟動")

    async def stop(self) -> None:
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()

    def set_scheduled_reply_target(self, instance: str, reply_to: str) -> None:
        group_id = self.config.channel.group_id
        if reply_to == "private":
            for ic in self.config.instances.values():
                if ic.private_chat:
                    self._reply_targets[instance] = {{"chat_id": ic.private_chat, "thread_id": None}}
                    return
        elif reply_to and group_id:
            try:
                import yaml
                from pathlib import Path
                raw = yaml.safe_load(Path("team.yaml").read_text(encoding="utf-8")) or {{}}
                thread_id = raw.get("topics", {{}}).get(reply_to)
                if thread_id:
                    self._reply_targets[instance] = {{"chat_id": group_id, "thread_id": thread_id}}
                    return
            except Exception:
                pass

    async def _on_message(self, update, context) -> None:
        if not update.message or not update.message.text:
            return
        user_id = update.message.from_user.id
        chat_id = update.message.chat_id
        chat_type = update.message.chat.type
        text = update.message.text.strip()
        thread_id = update.message.message_thread_id if update.message.is_topic_message else None

        if chat_type in ("group", "supergroup"):
            bot_username = (await self._app.bot.get_me()).username if self._app else None
            if bot_username and f"@{{bot_username}}" in text:
                text = text.replace(f"@{{bot_username}}", "").strip()
            else:
                return

        target = self._default_target
        mention_match = re.match(r"@([\\w-]+)\\s*(.*)", text, re.DOTALL)
        if mention_match:
            mentioned = mention_match.group(1)
            if not mentioned.endswith("-agent"):
                mentioned += "-agent"
            if mentioned in self.daemon._agents:
                target = mentioned
                text = mention_match.group(2).strip() or text

        self._reply_targets[target] = {{"chat_id": chat_id, "thread_id": thread_id}}
        success = await self.daemon.send_to(target, text)
        if not success:
            await self._send(chat_id, f"⚠️ {{target}} 目前無法接收訊息", thread_id=thread_id)
        else:
            codename = self._get_codename(target)
            msg = await self._send_and_return(
                chat_id, f"⏳ <b>{{codename}}</b> 處理中...", thread_id=thread_id, parse_mode="HTML"
            )
            if msg:
                self._processing_messages[target] = msg.message_id

    async def _send_reply(self, text: str, source: str = "", parse_mode: str = None,
                          topic_id: int | None = None) -> None:
        if topic_id:
            group_id = self.config.channel.group_id
            if group_id:
                await self._send_and_return(group_id, text, thread_id=topic_id, parse_mode=parse_mode)
                return

        target_info = self._reply_targets.get(source, {{}})
        chat_id = target_info.get("chat_id")
        thread_id = target_info.get("thread_id")

        processing_msg_id = self._processing_messages.pop(source, None)
        if processing_msg_id and chat_id and self._app:
            try:
                kwargs = {{"chat_id": chat_id, "message_id": processing_msg_id, "text": text}}
                if parse_mode:
                    kwargs["parse_mode"] = parse_mode
                await self._app.bot.edit_message_text(**kwargs)
                return
            except Exception:
                pass

        if chat_id:
            await self._send_and_return(chat_id, text, thread_id=thread_id, parse_mode=parse_mode)
            return

        for ic in self.config.instances.values():
            if ic.private_chat:
                await self._send_and_return(ic.private_chat, text, parse_mode=parse_mode)
                return

    async def _send_photo_reply(self, photo_path, caption: str = "", source: str = "",
                                chat_id: int | None = None, topic: int | None = None) -> None:
        if not self._app:
            return
        if not chat_id:
            target_info = self._reply_targets.get(source, {{}})
            chat_id = target_info.get("chat_id")
            topic = target_info.get("thread_id")
        if not chat_id:
            for ic in self.config.instances.values():
                if ic.private_chat:
                    chat_id = ic.private_chat
                    break
        if not chat_id:
            return
        try:
            with open(photo_path, "rb") as f:
                kwargs = {{"chat_id": chat_id, "photo": f, "caption": caption[:1024]}}
                if topic:
                    kwargs["message_thread_id"] = topic
                await self._app.bot.send_photo(**kwargs)
        except Exception as e:
            log.error("send_photo failed: %s", e)

    async def _send_document_reply(self, file_path, caption: str = "", source: str = "",
                                   chat_id: int | None = None, topic: int | None = None) -> None:
        if not self._app:
            return
        if not chat_id:
            target_info = self._reply_targets.get(source, {{}})
            chat_id = target_info.get("chat_id")
            topic = target_info.get("thread_id")
        if not chat_id:
            for ic in self.config.instances.values():
                if ic.private_chat:
                    chat_id = ic.private_chat
                    break
        if not chat_id:
            return
        try:
            with open(file_path, "rb") as f:
                kwargs = {{"chat_id": chat_id, "document": f, "caption": caption[:1024]}}
                if topic:
                    kwargs["message_thread_id"] = topic
                await self._app.bot.send_document(**kwargs)
        except Exception as e:
            log.error("send_document failed: %s", e)

    async def _send_and_return(self, chat_id: int, text: str, thread_id=None, parse_mode=None):
        if not self._app:
            return None
        try:
            kwargs = {{"chat_id": chat_id, "text": text}}
            if parse_mode:
                kwargs["parse_mode"] = parse_mode
            if thread_id:
                kwargs["message_thread_id"] = thread_id
            return await self._app.bot.send_message(**kwargs)
        except Exception as e:
            log.debug("send failed: %s", e)
            return None

    async def _send(self, chat_id: int, text: str, parse_mode: str = "HTML",
                    thread_id: int | None = None) -> None:
        now = time.time()
        wait = 0.1 - (now - self._last_send)
        if wait > 0:
            await asyncio.sleep(wait)
        parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for part in parts:
            kwargs = {{"chat_id": chat_id, "text": part}}
            if thread_id:
                kwargs["message_thread_id"] = thread_id
            try:
                await self._app.bot.send_message(**kwargs, parse_mode="HTML")
            except Exception:
                try:
                    import re as _re
                    kwargs["text"] = _re.sub(r"<[^>]+>", "", part)
                    await self._app.bot.send_message(**kwargs)
                except Exception as e:
                    log.error("send failed: %s", e)
            self._last_send = time.time()

    async def _notify_startup(self) -> None:
        instances = self.config.instances
        n = len(instances)
        text = f"✅ <b>Agent Team</b> 就緒（{{n}} agents）\\n\\n"
        text += "\\n".join(f"• {{ic.description}}" for ic in instances.values())
        for ic in instances.values():
            if ic.private_chat:
                await self._send(ic.private_chat, text, parse_mode="HTML")
                return

    async def start_output_monitor(self) -> None:
        """啟動輸出監控（可選）。"""
        pass

    async def _cmd_start(self, update, context) -> None:
        agents_list = "\\n".join(f"• {{ic.description}}" for ic in self.config.instances.values())
        text = (
            "✅ <b>Agent Team</b> 就緒\\n\\n"
            "💬 <b>使用方式：</b>\\n"
            "直接發訊息，或用 @agent-name 指定 agent\\n\\n"
            f"🤖 <b>團隊成員：</b>\\n{{agents_list}}"
        )
        await update.message.reply_text(text, parse_mode="HTML")

    async def _cmd_status(self, update, context) -> None:
        status = self.daemon.get_status()
        lines = []
        for name, s in status.items():
            icon = "🟢" if s.get("alive") else "🔴"
            lines.append(f"{{icon}} {{name}}")
        await update.message.reply_text("\\n".join(lines) or "無 agent")
'''


# ── 工具函式 ──────────────────────────────────────────────────

def _write_if_missing(path: Path, content: str) -> None:
    """只在檔案不存在時寫入。"""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


# ── Diff / Validate ──────────────────────────────────────────

def validate_project(project_dir: Path) -> list[str]:
    """驗證專案結構完整性。回傳錯誤清單。"""
    errors: list[str] = []
    p = project_dir

    # 必要根檔案
    for f in ("team.yaml", "scheduler.yaml", "start.py", "pyproject.toml",
              "requirements.txt", ".env.example", ".gitignore", "README.md",
              "start-team.bat", "start-team.sh"):
        if not (p / f).exists():
            errors.append(f"❌ 缺少: {f}")

    # team.yaml 內容檢查
    team_yaml = p / "team.yaml"
    if team_yaml.exists():
        with open(team_yaml, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

        for key in ("defaults", "cost_guard", "hang_detector", "instances",
                    "health_port", "channel", "access"):
            if key not in cfg:
                errors.append(f"team.yaml: 缺少 '{key}'")

        instances = cfg.get("instances", {})
        admins = [n for n, v in instances.items()
                  if (v or {}).get("role") == "admin"]
        leaders = [n for n, v in instances.items()
                   if (v or {}).get("role") == "leader"]

        if len(admins) != 1:
            errors.append(f"team.yaml: 需要恰好 1 個 admin，找到 {len(admins)}")
        if len(leaders) != 1:
            errors.append(f"team.yaml: 需要恰好 1 個 leader，找到 {len(leaders)}")

        for name, inst in instances.items():
            inst = inst or {}
            if "skip_resume" not in inst:
                errors.append(f"team.yaml: {name} 缺少 skip_resume")
            if "description" not in inst:
                errors.append(f"team.yaml: {name} 缺少 description")

    # scheduler.yaml 內容檢查
    sched = p / "scheduler.yaml"
    if sched.exists():
        with open(sched, encoding="utf-8") as f:
            sched_cfg = yaml.safe_load(f) or {}
        jobs = sched_cfg.get("jobs", [])
        if len(jobs) < 2:
            errors.append(f"scheduler.yaml: 需要 ≥ 2 jobs，只有 {len(jobs)}")
        for i, job in enumerate(jobs):
            if "id" not in job:
                errors.append(f"scheduler.yaml: job[{i}] 缺少 'id'（用了 'name'？）")
            if "reply_to" not in job:
                errors.append(f"scheduler.yaml: job[{i}] 缺少 'reply_to'")

    # 目錄結構
    for d in ("tasks", "agents", "docs", "secrets", "knowledge",
              "src/ark_team_core", ".kiro/steering", ".kiro/settings"):
        if not (p / d).exists():
            errors.append(f"❌ 目錄缺少: {d}/")

    # tasks/board.json
    if not (p / "tasks" / "board.json").exists():
        errors.append("❌ 缺少: tasks/board.json")

    # agents/AGENTS.md
    agents_md = p / "agents" / "AGENTS.md"
    if agents_md.exists():
        content = agents_md.read_text(encoding="utf-8")
        if "reply" not in content.lower():
            errors.append("agents/AGENTS.md: 缺少 reply kind 規則")
        if "錯誤" not in content:
            errors.append("agents/AGENTS.md: 缺少錯誤處理段落")
    else:
        errors.append("❌ 缺少: agents/AGENTS.md")

    # .gitignore 完整性
    gi = p / ".gitignore"
    if gi.exists():
        gi_content = gi.read_text(encoding="utf-8")
        for pattern in ("logs/", "data/", "output/"):
            if pattern not in gi_content and f"*{pattern}" not in gi_content:
                errors.append(f".gitignore: 缺少 '{pattern}'")

    # secrets/ 結構
    if (p / "secrets").exists():
        if not (p / "secrets" / ".gitignore").exists():
            errors.append("❌ 缺少: secrets/.gitignore")

    # knowledge/ 五件套
    if (p / "knowledge").exists():
        for f in ("schema.md", "index.md", "log.md"):
            if not (p / "knowledge" / f).exists():
                errors.append(f"knowledge/: 缺少 {f}")

    # Agent 目錄檢查
    if team_yaml.exists():
        for name, inst in cfg.get("instances", {}).items():
            inst = inst or {}
            wd = inst.get("working_directory", f"agents/{name}")
            if wd == "." or Path(wd).is_absolute():
                continue
            agent_dir = p / wd
            if not agent_dir.exists():
                errors.append(f"❌ Agent 目錄不存在: {wd}")
                continue
            for sub in ("docs", "output", "knowledge"):
                if not (agent_dir / sub).exists():
                    errors.append(f"⚠️ {wd}/{sub}/ 缺少")
            # 知識庫五件套
            k = agent_dir / "knowledge"
            for f in ("schema.md", "index.md", "log.md"):
                if not (k / f).exists():
                    errors.append(f"⚠️ {wd}/knowledge/{f} 缺少")
            if not (k / "raw").exists():
                errors.append(f"⚠️ {wd}/knowledge/raw/ 缺少")
            if not (k / "wiki").exists():
                errors.append(f"⚠️ {wd}/knowledge/wiki/ 缺少")

    # requirements.txt 必要依賴
    req = p / "requirements.txt"
    if req.exists():
        req_content = req.read_text(encoding="utf-8")
        if "python-telegram-bot" not in req_content:
            errors.append("requirements.txt: 缺少 python-telegram-bot")

    # 業務層檢查
    pkg_name = p.name.replace("-", "_")
    # 嘗試從 team.yaml 推斷，或掃描 src/ 下的目錄
    biz_dir = p / "src" / pkg_name
    if not biz_dir.exists():
        # 掃描 src/ 找業務層（排除 ark_team_core）
        src_dir = p / "src"
        if src_dir.exists():
            candidates = [d for d in src_dir.iterdir()
                          if d.is_dir() and d.name != "ark_team_core"
                          and not d.name.startswith("__")]
            if candidates:
                biz_dir = candidates[0]
                pkg_name = biz_dir.name

    if not biz_dir.exists():
        errors.append(f"❌ 缺少業務層: src/{pkg_name}/")
    else:
        for f in ("telegram_adapter.py", "api.py", "event_log.py", "mcp_setup.py"):
            if not (biz_dir / f).exists():
                errors.append(f"❌ 缺少: src/{pkg_name}/{f}")
        tools_dir = biz_dir / "tools"
        if not tools_dir.exists():
            errors.append(f"❌ 缺少: src/{pkg_name}/tools/")
        else:
            for f in ("__init__.py", "base.py"):
                if not (tools_dir / f).exists():
                    errors.append(f"❌ 缺少: src/{pkg_name}/tools/{f}")

    return errors


# ── CLI ──────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python build_team.py <output_dir> [team.yaml]  # 產出專案")
        print("  python build_team.py --validate <project_dir>  # 驗證結構")
        print("  python build_team.py --diff <existing_dir>     # 比對差異")
        sys.exit(1)

    if sys.argv[1] == "--validate":
        target = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
        errors = validate_project(target)
        if errors:
            print(f"\n❌ {len(errors)} 項問題（{target}）:\n")
            for e in errors:
                print(f"  {e}")
            sys.exit(1)
        else:
            print(f"\n✅ 結構完整（{target}）")
        return

    if sys.argv[1] == "--diff":
        target = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
        errors = validate_project(target)
        print(f"\n📋 差異報告（{target}）:\n")
        if errors:
            for e in errors:
                print(f"  {e}")
        else:
            print("  ✅ 結構完整，無差異")
        return

    output = Path(sys.argv[1])
    team_yaml = Path(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None

    # 解析 --level team/full
    level = "full"
    for i, arg in enumerate(sys.argv):
        if arg == "--level" and i + 1 < len(sys.argv):
            level = sys.argv[i + 1]

    created = build_team(output, team_yaml, level=level)
    print(f"\n✅ 團隊專案已建立: {output} (level={level})\n")
    print(f"📁 產出 {len(created)} 項:")
    for f in created:
        print(f"  • {f}")
    print(f"\n📋 下一步:")
    print(f"  1. cd {output}")
    print(f"  2. cp .env.example .env && 編輯 .env")
    print(f"  3. pip install -r requirements.txt")
    print(f"  4. python start.py")


if __name__ == "__main__":
    main()
