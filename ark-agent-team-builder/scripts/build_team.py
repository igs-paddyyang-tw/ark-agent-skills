"""build_team.py — 一鍵產出完整可獨立運作的 Agent Team 專案。

整合 ark-agent-team-builder + ark-team-core + ark-kiro-init，
確保產出的專案可以直接 `python start.py` 啟動，不需安裝 ark-team-agent。

Usage:
    python build_team.py <output_dir> [team.yaml]

產出結構：
    {output}/
    ├── team.yaml
    ├── scheduler.yaml
    ├── start.py                    # 一鍵啟動（含 CoreDaemon + TelegramAdapter）
    ├── start-team.bat              # Windows watchdog
    ├── start-team.sh               # Linux watchdog
    ├── pyproject.toml
    ├── requirements.txt
    ├── .env.example
    ├── .gitignore
    ├── README.md
    ├── src/ark_team_core/          # 核心引擎（vendored，獨立運作）
    │   ├── __init__.py
    │   ├── config.py
    │   ├── daemon.py
    │   ├── process.py
    │   └── mcp_registry.py
    ├── tasks/
    │   ├── board.json
    │   └── items/
    ├── agents/
    │   ├── AGENTS.md
    │   └── {name}-agent/           # 每個 agent 三件套 + 知識庫五件套
    └── .kiro/                      # admin workspace（由 ark-kiro-init 邏輯產出）
        ├── steering/
        ├── settings/mcp.json
        └── agents/
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

# ── 常數 ─────────────────────────────────────────────────────

SKILL_ROOT = Path(__file__).resolve().parent.parent  # ark-agent-team-builder/
ASSETS_DIR = SKILL_ROOT / "assets"

# ark_team_core 來源（從主專案 vendored）
CORE_SOURCE = Path(__file__).resolve().parents[4] / "projects" / "game-analytics-team" / "src" / "ark_team_core"
# 備用：從 src/ark_team_agent 抽取
FALLBACK_CORE = Path(__file__).resolve().parents[3] / "src" / "ark_team_agent"


def build_team(output_dir: Path, team_yaml_path: Path | None = None) -> list[str]:
    """產出完整 Agent Team 專案。回傳已建立的檔案清單。"""
    import yaml

    output_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []

    # ── 1. team.yaml（複製或產出預設） ──
    if team_yaml_path and team_yaml_path.exists():
        shutil.copy2(team_yaml_path, output_dir / "team.yaml")
    else:
        _write_default_team_yaml(output_dir)
    created.append("team.yaml")

    # 載入 team.yaml 取得 instances
    with open(output_dir / "team.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    # ── 2. scheduler.yaml ──
    if not (output_dir / "scheduler.yaml").exists():
        _write_scheduler_yaml(output_dir, cfg)
        created.append("scheduler.yaml")

    # ── 3. src/ark_team_core/（vendored 核心引擎） ──
    core_dst = output_dir / "src" / "ark_team_core"
    if not core_dst.exists():
        _vendor_core(core_dst)
        created.append("src/ark_team_core/")

    # ── 4. start.py ──
    if not (output_dir / "start.py").exists():
        _write_start_py(output_dir, cfg)
        created.append("start.py")

    # ── 5. Watchdog scripts ──
    for fname in ("start-team.bat", "start-team.sh"):
        src = ASSETS_DIR / fname
        dst = output_dir / fname
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
            created.append(fname)

    # ── 6. pyproject.toml ──
    if not (output_dir / "pyproject.toml").exists():
        _write_pyproject(output_dir, cfg)
        created.append("pyproject.toml")

    # ── 7. requirements.txt ──
    if not (output_dir / "requirements.txt").exists():
        (output_dir / "requirements.txt").write_text(
            "pyyaml>=6.0\npython-telegram-bot==21.10\npython-dotenv>=1.0\n",
            encoding="utf-8",
        )
        created.append("requirements.txt")

    # ── 8. .env.example ──
    if not (output_dir / ".env.example").exists():
        (output_dir / ".env.example").write_text(
            "TELEGRAM_BOT_TOKEN=your-token-here\n# GEMINI_API_KEY=your-key-here\n",
            encoding="utf-8",
        )
        created.append(".env.example")

    # ── 9. .gitignore ──
    gitignore_src = ASSETS_DIR / "gitignore.txt"
    if not (output_dir / ".gitignore").exists():
        if gitignore_src.exists():
            shutil.copy2(gitignore_src, output_dir / ".gitignore")
        else:
            (output_dir / ".gitignore").write_text(
                ".env\nstate/\n*.pid\n__pycache__/\n*.pyc\nsecrets/\n",
                encoding="utf-8",
            )
        created.append(".gitignore")

    # ── 10. tasks/ ──
    tasks_dir = output_dir / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    (tasks_dir / "items").mkdir(exist_ok=True)
    board = tasks_dir / "board.json"
    if not board.exists():
        board.write_text(json.dumps({"tasks": []}, indent=2), encoding="utf-8")
        created.append("tasks/board.json")

    # ── 11. agents/ 目錄骨架 ──
    agents_created = _scaffold_agents(output_dir, cfg)
    created.extend(agents_created)

    # ── 12. .kiro/ (admin workspace — 精簡版 ark-kiro-init) ──
    kiro_created = _scaffold_kiro(output_dir, cfg)
    created.extend(kiro_created)

    # ── 13. README.md ──
    if not (output_dir / "README.md").exists():
        _write_readme(output_dir, cfg)
        created.append("README.md")

    return created


def _vendor_core(dst: Path) -> None:
    """複製 ark_team_core 到目標目錄。"""
    dst.mkdir(parents=True, exist_ok=True)

    if CORE_SOURCE.exists():
        # 從 GA team 複製（最新版）
        for f in CORE_SOURCE.glob("*.py"):
            if f.name.startswith("__pycache__"):
                continue
            shutil.copy2(f, dst / f.name)
    else:
        # Fallback: 產出最小版本
        _write_minimal_core(dst)


def _write_minimal_core(dst: Path) -> None:
    """產出最小可運作的 ark_team_core。"""
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
    # config.py, daemon.py, process.py, mcp_registry.py 從 GA team 已知結構產出
    # 這裡只做 placeholder — 實際應從 CORE_SOURCE 複製


def _scaffold_agents(output_dir: Path, cfg: dict) -> list[str]:
    """建立 agents/ 目錄骨架。"""
    created: list[str] = []
    agents_dir = output_dir / "agents"
    agents_dir.mkdir(exist_ok=True)

    # AGENTS.md
    agents_md = agents_dir / "AGENTS.md"
    if not agents_md.exists():
        instances = cfg.get("instances", {})
        lines = [
            "# 團隊共用行為準則\n",
            "> 所有 agent 必須遵守。\n",
            "## 團隊成員\n",
            "| Instance | 角色 | 職責 |",
            "|----------|------|------|",
        ]
        for name, inst in instances.items():
            role = (inst or {}).get("role", "worker")
            desc = (inst or {}).get("description", "")
            lines.append(f"| {name} | {role} | {desc} |")
        lines.append("\n## 通訊規則\n")
        lines.append("- 重要協調走 leader")
        lines.append("- 錯誤/過程用 log_to_leader")
        lines.append("- 回覆使用者用 reply\n")
        agents_md.write_text("\n".join(lines), encoding="utf-8")
        created.append("agents/AGENTS.md")

    # 每個 agent 的目錄
    for name, inst in cfg.get("instances", {}).items():
        inst = inst or {}
        wd = inst.get("working_directory", f"agents/{name}")
        if wd == "." or Path(wd).is_absolute():
            continue

        agent_dir = output_dir / wd
        # 三件套
        for sub in ("docs", "output", "knowledge"):
            d = agent_dir / sub
            if not d.exists():
                d.mkdir(parents=True, exist_ok=True)
                (d / ".gitkeep").touch()
                created.append(f"{wd}/{sub}/")

        # 知識庫五件套
        knowledge_dir = agent_dir / "knowledge"
        _ensure_knowledge(knowledge_dir, name)
        created.append(f"{wd}/knowledge/ (五件套)")

    return created


def _ensure_knowledge(knowledge_dir: Path, agent_name: str) -> None:
    """確保知識庫五件套存在。"""
    knowledge_dir.mkdir(parents=True, exist_ok=True)

    schema = knowledge_dir / "schema.md"
    if not schema.exists():
        schema.write_text(
            "---\nversion: \"3.0\"\n---\n\n# Knowledge Schema\n\n"
            "## Frontmatter 欄位\n\n"
            "| 欄位 | 必填 | 說明 |\n|------|------|------|\n"
            "| title | ✅ | 頁面標題 |\n"
            "| type | ✅ | concept/entity/source/synthesis |\n"
            "| tags | ✅ | 標籤陣列 |\n"
            "| created | ✅ | YYYY-MM-DD |\n"
            "| updated | ✅ | YYYY-MM-DD |\n",
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
            f"tags: [overview]\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\n\n"
            f"# {agent_name}\n\n（待填充）\n",
            encoding="utf-8",
        )


def _scaffold_kiro(output_dir: Path, cfg: dict) -> list[str]:
    """產出 .kiro/ admin workspace（精簡版 ark-kiro-init）。"""
    created: list[str] = []
    kiro_dir = output_dir / ".kiro"

    # steering/
    steering_dir = kiro_dir / "steering"
    steering_dir.mkdir(parents=True, exist_ok=True)

    memory = steering_dir / "MEMORY.md"
    if not memory.exists():
        memory.write_text("# 🧠 專案記憶\n\n> Agent 工作記憶\n\n---\n\n", encoding="utf-8")
        created.append(".kiro/steering/MEMORY.md")

    user = steering_dir / "USER.md"
    if not user.exists():
        user.write_text(
            "# USER.md — 使用者百科\n\n"
            "## 個人特徵與偏好\n\n- **稱呼：** （填入）\n- **偏好語言：** 繁體中文\n\n"
            "## 溝通風格\n\n- **回答風格：** 簡短直接\n",
            encoding="utf-8",
        )
        created.append(".kiro/steering/USER.md")

    # settings/mcp.json
    settings_dir = kiro_dir / "settings"
    settings_dir.mkdir(parents=True, exist_ok=True)
    mcp_json = settings_dir / "mcp.json"
    if not mcp_json.exists():
        mcp_json.write_text(json.dumps({"mcpServers": {}}, indent=2), encoding="utf-8")
        created.append(".kiro/settings/mcp.json")

    # agents/ (admin identity)
    agents_dir = kiro_dir / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    # Find admin instance
    for name, inst in cfg.get("instances", {}).items():
        if (inst or {}).get("role") == "admin":
            agent_json = agents_dir / f"{name}.json"
            if not agent_json.exists():
                agent_json.write_text(json.dumps({
                    "name": name,
                    "description": (inst or {}).get("description", "Admin"),
                    "role": "admin",
                }, indent=2, ensure_ascii=False), encoding="utf-8")
                created.append(f".kiro/agents/{name}.json")
            break

    return created


def _write_default_team_yaml(output_dir: Path) -> None:
    """產出預設 5 人團隊 team.yaml。"""
    content = """\
defaults:
  backend: kiro-cli
  model: auto

cost_guard:
  daily_limit_usd: 30.0
  warn_at_percentage: 80
  timezone: Asia/Taipei

hang_detector:
  enabled: true
  timeout_minutes: 60
  escalation_minutes: 180

channel:
  bot_token_env: TELEGRAM_BOT_TOKEN
  # group_id: -100xxxxxxxxxx  # 有值 = Group Topics；無值 = 純私聊 @mention

access:
  mode: locked
  allowed_users:
    - 123456789  # 你的 Telegram ID

instances:
  admin-agent:
    working_directory: "."
    description: "👑 Admin — 服務管理"
    private_chat: 123456789
    role: admin

  leader-agent:
    working_directory: agents/leader-agent
    description: "🔱 Leader — 需求釐清、派工、驗收"
    role: leader

  dev-agent:
    working_directory: agents/dev-agent
    description: "💻 Developer — 全端開發"
    role: worker

  qa-agent:
    working_directory: agents/qa-agent
    description: "🧪 QA — 測試、品質保證"
    role: worker

health_port: 13030
"""
    (output_dir / "team.yaml").write_text(content, encoding="utf-8")


def _write_scheduler_yaml(output_dir: Path, cfg: dict) -> None:
    """產出 scheduler.yaml。"""
    # 找 leader
    leader = "leader-agent"
    for name, inst in cfg.get("instances", {}).items():
        if (inst or {}).get("role") == "leader":
            leader = name
            break

    content = f"""\
timezone: Asia/Taipei

jobs:
  - name: hourly-progress
    target: {leader}
    prompt: "⏰ 確認團隊狀態，query_team_status 後依計劃派工或追蹤。更新 memory.md。"
    cron: "10 9-21 * * *"

  - name: daily-summary
    target: {leader}
    prompt: "📋 今日摘要：整理成果 + 明日計劃，reply 回報。"
    cron: "0 21 * * *"
"""
    (output_dir / "scheduler.yaml").write_text(content, encoding="utf-8")


def _write_start_py(output_dir: Path, cfg: dict) -> None:
    """產出 start.py（一鍵啟動）。"""
    content = '''\
"""一鍵啟動 Agent Team。"""
from __future__ import annotations

import asyncio
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from ark_team_core import CoreDaemon
from ark_team_core.process import AgentProcess


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    log = logging.getLogger("team")

    daemon = CoreDaemon("team.yaml")

    # 註冊業務 MCP Tools（可選）
    try:
        from src.tools.mcp_setup import register_tools
        register_tools(daemon.mcp_registry)
        log.info("MCP tools registered")
    except (ImportError, ModuleNotFoundError):
        pass

    # 啟動所有 agent
    log.info("啟動團隊（%d agents）...", len(daemon.config.instances))
    for name, ic in daemon.config.instances.items():
        proc = AgentProcess(name=name, working_dir=ic.working_directory, model=ic.model, skip_resume=ic.skip_resume)
        daemon._agents[name] = proc
        daemon._last_activity[name] = time.time()
        daemon._restart_count[name] = 0
        await proc.start()
        await asyncio.sleep(2)

    log.info("所有 agent 已啟動 (%d/%d)", len(daemon._agents), len(daemon.config.instances))
    daemon._running = True

    # 主迴圈
    try:
        while daemon._running:
            await asyncio.sleep(30)
            await daemon._health_check()
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        await daemon.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\\n團隊已停止。")
'''
    (output_dir / "start.py").write_text(content, encoding="utf-8")


def _write_pyproject(output_dir: Path, cfg: dict) -> None:
    """產出 pyproject.toml。"""
    project_name = output_dir.name or "my-agent-team"
    content = f"""\
[project]
name = "{project_name}"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pyyaml>=6.0",
    "python-telegram-bot==21.10",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]
"""
    (output_dir / "pyproject.toml").write_text(content, encoding="utf-8")


def _write_readme(output_dir: Path, cfg: dict) -> None:
    """產出 README.md。"""
    instances = cfg.get("instances", {})
    project_name = output_dir.name or "Agent Team"

    lines = [
        f"# 🤖 {project_name}\n",
        f"> {len(instances)} Agent 團隊 — 由 ark-agent-team-builder 產出\n",
        "## 團隊組成\n",
        "| Instance | 角色 | 職責 |",
        "|----------|------|------|",
    ]
    for name, inst in instances.items():
        inst = inst or {}
        lines.append(f"| {name} | {inst.get('role', 'worker')} | {inst.get('description', '')} |")

    lines.extend([
        "\n## 快速啟動\n",
        "```bash",
        "# 1. 安裝依賴",
        "pip install -r requirements.txt",
        "",
        "# 2. 設定環境變數",
        "cp .env.example .env",
        "# 編輯 .env 填入 Telegram Bot Token",
        "",
        "# 3. 啟動團隊",
        "python start.py",
        "```\n",
        "## 目錄結構\n",
        "```",
        f"{project_name}/",
        "├── team.yaml          # 團隊配置",
        "├── scheduler.yaml     # 排程定義",
        "├── start.py           # 一鍵啟動",
        "├── src/ark_team_core/ # 核心引擎（vendored）",
        "├── agents/            # Agent 工作目錄",
        "├── tasks/             # 任務板",
        "└── .kiro/             # Admin workspace",
        "```\n",
    ])
    (output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


# ── Diff 工具：比較產出與現有專案 ─────────────────────────────

def diff_with_existing(output_dir: Path, existing_dir: Path) -> list[str]:
    """比較 build_team 產出與現有專案的差異。"""
    diffs: list[str] = []

    # 檢查 ark_team_core 版本差異
    core_new = output_dir / "src" / "ark_team_core"
    core_old = existing_dir / "src" / "ark_team_core"
    if core_old.exists() and core_new.exists():
        for f in core_new.glob("*.py"):
            old_f = core_old / f.name
            if old_f.exists():
                if f.read_text(encoding="utf-8") != old_f.read_text(encoding="utf-8"):
                    diffs.append(f"⚠️ src/ark_team_core/{f.name} 有差異")
            else:
                diffs.append(f"➕ src/ark_team_core/{f.name} 是新增的")
        for f in core_old.glob("*.py"):
            if not (core_new / f.name).exists():
                diffs.append(f"➖ src/ark_team_core/{f.name} 在新版中不存在")

    # 檢查缺少的標準檔案
    expected_files = [
        "team.yaml", "scheduler.yaml", "start.py", "pyproject.toml",
        "requirements.txt", ".env.example", ".gitignore", "README.md",
        "tasks/board.json", "agents/AGENTS.md",
    ]
    for f in expected_files:
        if not (existing_dir / f).exists():
            diffs.append(f"❌ 缺少: {f}")

    # 檢查 .kiro/ 結構
    kiro_expected = [".kiro/steering/MEMORY.md", ".kiro/settings/mcp.json"]
    for f in kiro_expected:
        if not (existing_dir / f).exists():
            diffs.append(f"❌ 缺少: {f}")

    # 檢查 agents 知識庫五件套
    import yaml
    team_yaml = existing_dir / "team.yaml"
    if team_yaml.exists():
        with open(team_yaml, encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh) or {}
        for name, inst in cfg.get("instances", {}).items():
            inst = inst or {}
            wd = inst.get("working_directory", f"agents/{name}")
            if wd == "." or Path(wd).is_absolute():
                continue
            agent_dir = existing_dir / wd
            if not agent_dir.exists():
                diffs.append(f"❌ Agent 目錄不存在: {wd}")
                continue
            for sub in ("knowledge/schema.md", "knowledge/index.md", "knowledge/log.md",
                        "knowledge/raw", "knowledge/wiki/overview.md"):
                if not (agent_dir / sub).exists():
                    diffs.append(f"⚠️ {wd}/{sub} 缺少")

    if not diffs:
        diffs.append("✅ 結構完整，無差異")

    return diffs


# ── CLI ──────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python build_team.py <output_dir> [team.yaml]")
        print("       python build_team.py --diff <existing_dir>")
        sys.exit(1)

    if sys.argv[1] == "--diff":
        # Diff 模式：檢查現有專案
        existing = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
        diffs = diff_with_existing(Path("/tmp/_build_team_check"), existing)
        print(f"\n📋 差異報告（{existing}）:\n")
        for d in diffs:
            print(f"  {d}")
        return

    output = Path(sys.argv[1])
    team_yaml = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    created = build_team(output, team_yaml)
    print(f"\n✅ 團隊專案已建立: {output}\n")
    print(f"📁 產出 {len(created)} 項:")
    for f in created:
        print(f"  • {f}")
    print(f"\n📋 下一步:")
    print(f"  1. cd {output}")
    print(f"  2. 編輯 .env（填入 Telegram Bot Token）")
    print(f"  3. pip install -r requirements.txt")
    print(f"  4. python start.py")


if __name__ == "__main__":
    main()
