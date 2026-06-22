---
author: paddyyang
name: ark-ai-bot-builder
description: |
  快速產出完整 AI Agent Bot Workspace（1~6 階段漸進式）。
  掛載 Agent CLI（Gemini/Kiro/Claude）為大腦，透過 Telegram 自然語言對話讓 Bot 做事。
  參考 ninja-bot 架構：BaseSkill 插件系統 + ConversationPlanner 意圖路由 +
  LLMRouter fallback chain + AgentOrchestrator 自進化 + MemorySearch 跨 Session 記憶。
  使用此 Skill 當使用者提及 ai-bot-builder、建立 AI Bot、產出 Bot workspace、
  快速建 Agent Bot、或任何需要從零建構 Telegram AI Agent Bot 的場景。
metadata:
  version: "2.0"
  updated: 2026-06-22
---

# ark-ai-bot-builder

> 快速產出 AI Agent Bot Workspace。核心：Agent CLI 為大腦 + Telegram 自然語言對話 + 自動產日報。

## 定位

使用者說話 → Bot 理解意圖 → Agent CLI 做事 → 回報結果。就這麼簡單。

```
使用者（Telegram）
    │ 自然語言
    ▼
Gateway（即時回饋 👀 + typing）
    │
    ▼
ConversationPlanner（六層意圖路由，零 LLM 消耗）
    │
    ├── L1: /reset → 重置
    ├── L2: /skill_id args → Skill 直接執行
    ├── L3: keyword 命中 → 本地 Skill
    │       「新聞」→ news_scraper → news_renderer
    │       「寫程式」→ llm_cli（codegen）
    ├── L4: keyword → 直達 team agent（測試→qa / 部署→admin）
    ├── L5: 深度關鍵字 → pm-agent 派工（規劃/分析/架構）
    └── L6: 預設 → Gemini API 快速回答（2-3s）
                ↓ 失敗
            → llm_cli CLI fallback（5-30s）
    │
    ▼
回覆 + 👍 Reaction
```

### 三級回應速度

| 級別 | 觸發 | 後端 | 延遲 |
|------|------|------|------|
| ⚡ 即時 | keyword / /cmd / Gemini API | Python Skill / Gemini REST | 1-5s |
| 🔄 標準 | 一般問答（API 不可用） | CLI subprocess（gemini/kiro/claude） | 5-30s |
| 🧠 深度 | 深度關鍵字 / @mention agent | kiro-cli multi-agent 派工 | 30-120s |

### 即時回饋機制

```
使用者發訊
 → [< 1 秒] 👀 Reaction（已收到）
 → [持續] typing...（每 4 秒重送，不斷線）
 → [完成]
   ├── 成功：👀 → 👍 + 回覆文字
   └── 失敗：👀 → 👎 + 錯誤摘要（不暴露 stack trace）

特點：
• 無「收到！正在處理...」中間訊息
• typing 不斷線（Telegram 5 秒超時 → 4 秒重送）
• 結案後 Timer 自動 cancel（無資源洩漏）
```

---

## 觸發條件

「ark-ai-bot-builder」、「建立 AI Bot」、「產出 Bot workspace」、「快速建 Agent Bot」、「ai-workspace」

## 輸入參數

| 參數 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `project_name` | `str` | ✅ | — | 專案名稱 |
| `output_dir` | `str` | ❌ | `"./output"` | 輸出目錄 |
| `stages` | `str` | ❌ | `"1-6"` | 階段範圍 |

---
## 最終產出結構

```
{project_name}/
├── start.py                        # 入口（~20 行）
├── src/
│   ├── bootstrap.py                # 啟動邏輯（四層順序）
│   ├── gateway/                    # 入口層
│   │   ├── telegram/handlers/      #   messages.py（六層路由 + 即時回饋）
│   │   ├── api/                    #   FastAPI（agents/issues/costs/schedules）
│   │   └── gemini_chat.py          #   Gemini API 快速路徑
│   ├── coordinator/                # 協調層
│   │   ├── db/                     #   SQLite + migrations
│   │   ├── events/                 #   EventBus pub/sub
│   │   ├── services/              #   cost_tracker + audit_logger
│   │   └── a2a/                   #   Agent 協作（router/graph/memory）
│   ├── runtime/                    # 執行層
│   │   ├── process.py              #   AgentProcess（kiro/gemini/claude）
│   │   ├── config.py              #   team.yaml 解析（含 backend）
│   │   └── scheduler.py           #   APScheduler
│   └── business/                   # 業務 Skills
│       ├── news_scraper.py
│       └── news_renderer.py
├── agents/                         # Agent 工作空間（各有 .kiro/）
├── skills/                         # 共用 Skills（git clone）
├── team.yaml                       # 團隊配置（含 backend 欄位）
├── scheduler.yaml                  # 排程定義
├── data/                           # SQLite DBs
├── .env.example
└── requirements.txt
```
```

---

## 產出階段

| Stage | 產出 | 一句話 |
|-------|------|--------|
| 1 | 四層目錄結構 | gateway + coordinator + runtime + business |
| 2 | Runtime 層 | process.py 多後端（kiro/gemini/claude fallback） |
| 3 | Gateway 六層路由 | Planner 零 LLM + Gemini API 快速路徑 |
| 4 | Telegram Bot + 即時回饋 | 👀/typing/👍 + 12 slash commands |
| 5 | Coordinator | EventBus + DB + A2A Router + Scheduler |
| 6 | 業務 Skills | news_scraper + news_renderer + team.yaml |

### Output 清洗（必做）

所有 CLI output 送到使用者前必須清洗：

```python
# 1. Strip ANSI escape codes
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
text = _ANSI_RE.sub("", raw)

# 2. 過濾工具執行日誌
_TOOL_PREFIXES = ("Searching the web", "Reading content", "Fetching",
                  "✓ Found", "- Completed in", "(using tool:")

# 3. 提取結論（_extract_conclusion）
# 策略：[DONE] marker → reply() 提取 → 尾部反向掃描非工具行

# 4. Strip kiro-cli '> ' prompt 前綴
```

---

## ★ 核心範例程式碼

以下是完整可運行的程式碼，直接複製即可使用。

---

### 1. `src/skills/base.py` — Skill 介面

```python
"""BaseSkill 插件系統。"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pydantic import BaseModel


class SkillType(str, Enum):
    PYTHON = "python"
    LLM = "llm"


class SkillParam(BaseModel):
    """Skill 輸入參數基底。"""
    pass


@dataclass
class SkillResult:
    """Skill 執行結果。"""
    success: bool
    data: dict = field(default_factory=dict)
    error: str = ""


class BaseSkill(ABC):
    """Skill 基底類別。"""
    skill_id: str = ""
    skill_type: SkillType = SkillType.PYTHON
    description: str = ""
    version: str = "1.0.0"
    input_schema: type[SkillParam] | None = None

    def validate_params(self, params: dict) -> bool:
        if not self.input_schema:
            return True
        try:
            self.input_schema(**params)
            return True
        except Exception:
            return False

    @abstractmethod
    async def execute(self, params: dict) -> SkillResult:
        ...
```

---

### 2. `src/skills/registry.py` — Skill 管理

```python
"""SkillRegistry — 註冊、查詢、執行。"""
import importlib
import pkgutil
import logging
import sys
from src.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        self._skills[skill.skill_id] = skill

    def get(self, skill_id: str) -> BaseSkill | None:
        return self._skills.get(skill_id)

    def list_skills(self) -> list[dict]:
        return [{"id": s.skill_id, "description": s.description} for s in self._skills.values()]

    async def invoke(self, skill_id: str, params: dict) -> SkillResult:
        skill = self.get(skill_id)
        if not skill:
            return SkillResult(success=False, error=f"Skill not found: {skill_id}")
        if not skill.validate_params(params):
            return SkillResult(success=False, error=f"Invalid params: {skill_id}")
        try:
            return await skill.execute(params)
        except Exception as e:
            return SkillResult(success=False, error=str(e))

    def auto_discover(self, package_name: str) -> int:
        count = 0
        try:
            pkg = importlib.import_module(package_name)
        except ImportError:
            return 0
        for _, module_name, _ in pkgutil.iter_modules(pkg.__path__):
            try:
                mod = importlib.import_module(f"{package_name}.{module_name}")
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if isinstance(attr, type) and issubclass(attr, BaseSkill) and attr is not BaseSkill and attr.skill_id:
                        self.register(attr())
                        count += 1
            except Exception as e:
                logger.warning("Failed to load %s: %s", module_name, e)
        return count

    def hot_reload(self, skill_id: str) -> bool:
        module_name = f"src.skills.internal.{skill_id}"
        if module_name in sys.modules:
            del sys.modules[module_name]
        try:
            mod = importlib.import_module(module_name)
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if isinstance(attr, type) and issubclass(attr, BaseSkill) and attr is not BaseSkill and attr.skill_id:
                    self.register(attr())
                    return True
        except Exception:
            pass
        return False
```

---

### 3. `src/skills/internal/llm_cli.py` — ★ Agent CLI 大腦（完整版）

```python
"""llm_cli — Agent CLI 封裝（Gemini/Kiro/Claude/Antigravity）。"""
import asyncio
import json
import os
import re
from pathlib import Path
from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType


class LlmCliParams(SkillParam):
    prompt: str
    mode: str = "chat"           # chat / codegen / evaluate / skill_gen
    model: str = "gemini-2.5-flash"
    timeout: int = 120
    backend: str = ""            # gemini / kiro / claude（空=自動偵測）
    output_path: str = ""
    skill_id: str = ""


class LlmCliSkill(BaseSkill):
    skill_id = "llm_cli"
    skill_type = SkillType.PYTHON
    description = "Agent CLI 大腦 — 對話、CodeGen、Skill 產出（Gemini/Kiro/Claude）"
    version = "2.0.0"
    input_schema = LlmCliParams

    # 後端設定：每個 CLI 的指令格式
    BACKENDS = {
        "gemini": {
            "cmd_env": "GEMINI_CLI_CMD",
            "cmd_default": "gemini.cmd" if os.name == "nt" else "gemini",
            "args": lambda p, m: ["-p", p, "-m", m, "--skip-trust"],
        },
        "kiro": {
            "cmd_env": "KIRO_CLI_CMD",
            "cmd_default": "kiro-cli",
            "args": lambda p, m: ["chat", "--no-interactive", "-a", "--legacy-ui", "--model", m, p],
        },
        "claude": {
            "cmd_env": "CLAUDE_CLI_CMD",
            "cmd_default": "claude",
            "args": lambda p, m: ["-p", p, "--model", m],
        },
    }

    @classmethod
    def is_available(cls, backend: str) -> bool:
        """檢查 CLI 是否已安裝。"""
        import shutil
        cfg = cls.BACKENDS.get(backend)
        if not cfg:
            return False
        cmd = os.getenv(cfg["cmd_env"], cfg["cmd_default"])
        return shutil.which(cmd) is not None

    async def execute(self, params: dict) -> SkillResult:
        p = LlmCliParams(**params)
        match p.mode:
            case "chat":     return await self._chat(p)
            case "codegen":  return await self._codegen(p)
            case "evaluate": return await self._evaluate(p)
            case "skill_gen": return await self._skill_gen(p)
            case _:          return SkillResult(success=False, error=f"不支援: {p.mode}")

    def _resolve_backend(self, preferred: str) -> str:
        """Fallback chain: preferred → gemini → kiro → claude。"""
        if preferred and self.is_available(preferred):
            return preferred
        for b in ("gemini", "kiro", "claude"):
            if self.is_available(b):
                return b
        return "gemini"

    async def _run_cli(self, prompt: str, model: str, timeout: int, backend: str) -> tuple[str, str, int]:
        """執行 CLI subprocess。"""
        resolved = self._resolve_backend(backend)
        cfg = self.BACKENDS[resolved]
        cmd_path = os.getenv(cfg["cmd_env"], cfg["cmd_default"])
        args = cfg["args"](prompt, model)

        import subprocess as _sp
        cmd_str = _sp.list2cmdline([cmd_path] + args)
        cwd = os.getenv("AI_BOT_WORKSPACE", str(Path(__file__).resolve().parents[3]))

        try:
            process = await asyncio.create_subprocess_shell(
                cmd_str,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            return (
                stdout.decode("utf-8").strip() if stdout else "",
                stderr.decode("utf-8").strip() if stderr else "",
                process.returncode,
            )
        except asyncio.TimeoutError:
            return ("", f"超時（{timeout}s）", 124)
        except FileNotFoundError:
            return ("", f"{cmd_path} 未安裝", 127)

    async def _chat(self, p: LlmCliParams) -> SkillResult:
        prompt = f"直接回答，不要自我介紹：{p.prompt}"
        out, err, code = await self._run_cli(prompt, p.model, p.timeout, p.backend)
        if out:
            return SkillResult(success=True, data={"output": out, "backend": self._resolve_backend(p.backend)})
        return SkillResult(success=False, error=f"CLI 失敗: {err[:300]}")

    async def _codegen(self, p: LlmCliParams) -> SkillResult:
        prompt = f"只輸出程式碼，不要解釋。需求：{p.prompt}"
        out, err, code = await self._run_cli(prompt, p.model, p.timeout, p.backend)
        if code != 0:
            return SkillResult(success=False, error=err[:300])
        source = self._extract_code(out)
        if p.output_path:
            Path(p.output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(p.output_path).write_text(source, encoding="utf-8")
        return SkillResult(success=True, data={"code": source, "path": p.output_path})

    async def _evaluate(self, p: LlmCliParams) -> SkillResult:
        prompt = (
            f'分析意圖，回傳純 JSON：{{"action":"answer|invoke|generate","skill_id":"..."}}\n'
            f"用戶：{p.prompt}\n只回傳 JSON。"
        )
        out, _, code = await self._run_cli(prompt, p.model, p.timeout, p.backend)
        parsed = self._extract_json(out)
        return SkillResult(success=True, data=parsed or {"action": "answer", "raw": out})

    async def _skill_gen(self, p: LlmCliParams) -> SkillResult:
        sid = p.skill_id or "generated_skill"
        prompt = (
            f"產出 Python Skill，繼承 BaseSkill（from src.skills.base import ...），"
            f'skill_id="{sid}"，需求：{p.prompt}\n只輸出程式碼。'
        )
        out, err, code = await self._run_cli(prompt, p.model, p.timeout, p.backend)
        if code != 0:
            return SkillResult(success=False, error=err[:300])
        source = self._extract_code(out)
        path = p.output_path or f"src/skills/internal/{sid}.py"
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(source, encoding="utf-8")
        return SkillResult(success=True, data={"skill_id": sid, "path": path})

    @staticmethod
    def _extract_code(output: str) -> str:
        match = re.search(r"```(?:python)?\n(.*?)```", output, re.DOTALL)
        return match.group(1).strip() if match else output

    @staticmethod
    def _extract_json(output: str) -> dict:
        match = re.search(r"\{.*\}", output, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return {}
        return {}
```

---

### 4. `src/conversation/planner.py` — ★ 三層意圖路由

```python
"""ConversationPlanner — 自然語言 → 做什麼。"""
import re
from dataclasses import dataclass, field
from enum import Enum


class PlanAction(Enum):
    EXECUTE = "execute"   # 執行 Skill
    ANSWER = "answer"     # LLM 回答
    RESET = "reset"       # 重置


@dataclass
class ExecutionPlan:
    action: PlanAction
    skill_id: str = ""
    params: dict = field(default_factory=dict)


# ── keyword 快速路由（毫秒級，不呼叫 LLM）──
_QUICK_ROUTE = [
    (["新聞", "日報", "news", "daily"], "news_scraper", {"config_path": "config/news_sources.yaml"}),
    (["程式", "code", "寫一個", "generate"], "llm_cli", {"mode": "codegen"}),
    (["echo", "回音"], "echo", {}),
]


class ConversationPlanner:
    def __init__(self, skill_ids: list[str] | None = None) -> None:
        self._skill_ids = skill_ids or []

    def set_skills(self, skill_ids: list[str]) -> None:
        self._skill_ids = skill_ids

    async def plan(self, text: str) -> ExecutionPlan:
        # 1. /reset
        if re.match(r"^(取消|重來|reset)$", text.strip(), re.I):
            return ExecutionPlan(action=PlanAction.RESET)

        # 2. /skill_id 指令
        cmd = re.match(r"^/(\w+)\s*(.*)", text.strip())
        if cmd and cmd.group(1) in self._skill_ids:
            return ExecutionPlan(action=PlanAction.EXECUTE, skill_id=cmd.group(1),
                                params={"prompt": cmd.group(2)} if cmd.group(2) else {})

        # 3. keyword 快速路由
        lower = text.lower()
        for keywords, skill_id, extra_params in _QUICK_ROUTE:
            if skill_id in self._skill_ids and any(k in lower for k in keywords):
                params = {**extra_params, "prompt": text}
                return ExecutionPlan(action=PlanAction.EXECUTE, skill_id=skill_id, params=params)

        # 4. 預設：LLM 回答
        return ExecutionPlan(action=PlanAction.ANSWER)
```

---

### 5. `src/bot/handlers.py` — Telegram 自然語言入口

```python
"""Telegram Bot handlers — 自然語言進 CLI。"""
import os
from telegram import Update
from telegram.ext import ContextTypes
from src.skills.registry import SkillRegistry
from src.conversation.planner import ConversationPlanner, PlanAction

_registry: SkillRegistry | None = None
_planner: ConversationPlanner | None = None


def init_components(registry: SkillRegistry) -> None:
    global _registry, _planner
    _registry = registry
    _planner = ConversationPlanner(skill_ids=[s["id"] for s in registry.list_skills()])


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤖 AI Agent Bot 就緒！\n\n"
        "直接打字跟我說話，我會用 Agent CLI 幫你做事。\n\n"
        "試試看：\n"
        "• 「今天有什麼科技新聞」→ 自動抓取產日報\n"
        "• 「幫我寫一個計算機 Skill」→ 自動產出程式碼\n"
        "• 任何問題 → Agent CLI 深度回答\n\n"
        "/daily — 手動觸發日報\n"
        "/skills — 列出已載入 Skills"
    )


async def cmd_skills(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    skills = _registry.list_skills() if _registry else []
    lines = [f"📦 {len(skills)} 個 Skills\n"]
    for s in skills:
        lines.append(f"  • {s['id']} — {s['description'][:40]}")
    await update.message.reply_text("\n".join(lines))


async def cmd_daily(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """手動觸發日報：scrape → render → 發送。"""
    await update.message.reply_text("📡 抓取新聞中...")
    # Step 1: 抓取
    result = await _registry.invoke("news_scraper", {"config_path": "config/news_sources.yaml"})
    if not result.success:
        await update.message.reply_text(f"❌ 抓取失敗：{result.error[:200]}")
        return
    # Step 2: 渲染
    articles = []
    for cat, items in result.data.get("categories", {}).items():
        for item in items[:3]:
            articles.append({
                "topic": cat, "title": item["title"],
                "what": item.get("description", item["title"]),
                "why": "", "summary": item["title"][:30],
                "tags": [], "source": "auto", "emoji": "📰",
            })
    render_result = await _registry.invoke("news_renderer", {"articles": articles[:5]})
    if render_result.success:
        path = render_result.data["path"]
        await update.message.reply_document(document=open(path, "rb"), filename=path.split("/")[-1])
    else:
        await update.message.reply_text(f"❌ 渲染失敗：{render_result.error[:200]}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """自然語言主流程：text → Planner → 做事。"""
    msg = update.effective_message
    if not msg or not msg.text:
        return
    text = msg.text.strip()

    # 意圖路由
    plan = await _planner.plan(text)

    if plan.action == PlanAction.RESET:
        await msg.reply_text("🔄 已重置")
        return

    if plan.action == PlanAction.EXECUTE:
        # 執行 Skill
        result = await _registry.invoke(plan.skill_id, plan.params)
        if result.success:
            output = result.data.get("output") or result.data.get("code") or str(result.data)
            if len(output) > 4000:
                output = output[:3900] + "\n\n📎 已截斷"
            await msg.reply_text(output)
        else:
            await msg.reply_text(f"❌ {plan.skill_id} 失敗：{result.error[:200]}")
        return

    # ANSWER — 直接走 Agent CLI
    wait_msg = await msg.reply_text("🤖 思考中...")
    result = await _registry.invoke("llm_cli", {"prompt": text, "mode": "chat"})
    if result.success:
        reply = result.data.get("output", "")
        if len(reply) > 4000:
            reply = reply[:3900] + "\n\n📎 已截斷"
        await wait_msg.edit_text(reply or "🤔 沒有回應")
    else:
        await wait_msg.edit_text(f"❌ {result.error[:300]}")
```

---

### 6. `src/bot/main.py` — Bot 入口

```python
"""Telegram Bot 入口。"""
import os
from dotenv import load_dotenv
from telegram import BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from src.bot.handlers import cmd_start, cmd_skills, cmd_daily, handle_message, init_components
from src.skills.registry import SkillRegistry

load_dotenv()


def create_app():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN 未設定")

    registry = SkillRegistry()
    registry.auto_discover("src.skills.internal")
    init_components(registry)

    app = ApplicationBuilder().token(token).post_init(_post_init).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("skills", cmd_skills))
    app.add_handler(CommandHandler("daily", cmd_daily))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app


async def _post_init(application) -> None:
    await application.bot.set_my_commands([
        BotCommand("start", "歡迎"),
        BotCommand("skills", "列出 Skills"),
        BotCommand("daily", "產出日報"),
    ])


if __name__ == "__main__":
    print("🤖 Bot started...")
    create_app().run_polling(drop_pending_updates=True)
```

---

### 7. `src/skills/internal/news_scraper.py` — 爬蟲（精簡版）

```python
"""news_scraper — httpx + BeautifulSoup 爬蟲。"""
import asyncio
import logging
from pathlib import Path
import httpx
import yaml
from bs4 import BeautifulSoup
from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType

logger = logging.getLogger(__name__)
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0.0.0"}


class NewsScraperParams(SkillParam):
    url: str = ""
    config_path: str = ""
    max_items: int = 5


class NewsScraperSkill(BaseSkill):
    skill_id = "news_scraper"
    skill_type = SkillType.PYTHON
    description = "科技新聞抓取（httpx + BS4 併發）"
    version = "2.0.0"
    input_schema = NewsScraperParams

    async def execute(self, params: dict) -> SkillResult:
        p = NewsScraperParams(**params)
        if p.config_path:
            return await self._from_config(p.config_path)
        if p.url:
            items = await self._fetch(p.url, "a", p.max_items)
            return SkillResult(success=True, data={"items": items, "count": len(items)})
        return SkillResult(success=False, error="需提供 url 或 config_path")

    async def _from_config(self, config_path: str) -> SkillResult:
        cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
        sources = cfg.get("sources", [])
        max_items = cfg.get("output", {}).get("max_items_per_source", 5)
        sem = asyncio.Semaphore(3)
        all_data: dict[str, list] = {}

        async def _fetch_one(src):
            async with sem:
                try:
                    items = await self._fetch(src["url"], src.get("selector", "a"), max_items)
                    return src.get("category", "news"), items
                except Exception as e:
                    logger.warning("抓取 %s 失敗: %s", src.get("name"), e)
                    return src.get("category", "news"), []

        results = await asyncio.gather(*[_fetch_one(s) for s in sources])
        for cat, items in results:
            all_data.setdefault(cat, []).extend(items)

        return SkillResult(success=True, data={
            "categories": all_data,
            "total": sum(len(v) for v in all_data.values()),
        })

    async def _fetch(self, url: str, selector: str, max_items: int) -> list[dict]:
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        items = []
        for el in soup.select(selector)[:max_items * 3]:
            title = el.get_text(strip=True)
            link = el.get("href", "")
            if title and len(title) > 8 and len(title) < 200:
                items.append({"title": title, "link": link})
            if len(items) >= max_items:
                break
        return items
```

---

### 8. `src/skills/internal/news_renderer.py` — HTML 日報渲染

```python
"""news_renderer — 結構化新聞 → 精美 HTML 卡片。"""
from datetime import datetime
from pathlib import Path
from jinja2 import Template
from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType

# 模板直接內嵌（見下方 templates/tech-daily.html）
CARD_TEMPLATE = Path("templates/tech-daily.html").read_text(encoding="utf-8") if Path("templates/tech-daily.html").exists() else "<html><body>{% for a in articles %}<h2>{{a.title}}</h2>{% endfor %}</body></html>"


class NewsRendererParams(SkillParam):
    articles: list[dict] = []
    output_path: str = ""


class NewsRendererSkill(BaseSkill):
    skill_id = "news_renderer"
    skill_type = SkillType.PYTHON
    description = "結構化新聞渲染為精美 HTML 日報"
    version = "2.0.0"
    input_schema = NewsRendererParams

    async def execute(self, params: dict) -> SkillResult:
        p = NewsRendererParams(**params)
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")

        for art in p.articles:
            art.setdefault("emoji", "📰")
            art.setdefault("source", "auto")
            art.setdefault("what", art.get("title", ""))
            art.setdefault("why", "")
            art.setdefault("summary", art.get("title", "")[:30])
            art.setdefault("tags", [])

        template = Template(CARD_TEMPLATE)
        html = template.render(articles=p.articles, date_display=now.strftime("%Y.%m.%d"))

        output_path = p.output_path or f"output/news/daily_{date_str}.html"
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(html, encoding="utf-8")

        return SkillResult(success=True, data={"path": output_path, "count": len(p.articles)})
```

---

### 9. `src/llm/gemini_chat.py` — Gemini API 即時對話（選配）

```python
"""Gemini API 即時對話（1-5 秒）。"""
import os

_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return _client


def is_available() -> bool:
    return bool(os.getenv("GEMINI_API_KEY"))


async def chat(message: str, system_prompt: str = "") -> str:
    """單輪 Gemini API 對話。"""
    client = _get_client()
    config = {"system_instruction": system_prompt} if system_prompt else None
    response = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        contents=message,
        config=config,
    )
    return response.text or ""
```

---

## ★ 設定檔樣板

### `config/news_sources.yaml`

```yaml
sources:
  - name: "Hacker News"
    url: "https://news.ycombinator.com/"
    type: html
    selector: ".titleline a"
    category: tech_general

  - name: "TechCrunch AI"
    url: "https://techcrunch.com/category/artificial-intelligence/feed/"
    type: rss
    category: ai_focus

schedule:
  cron: "0 9 * * *"
  timezone: "Asia/Taipei"

output:
  max_items_per_source: 5
```

### `config/llm_prompts.yaml`

```yaml
default_system_prompt: |
  你是資深 AI 工程師，使用繁體中文回答。
  結論先行，簡潔有力，附帶程式碼範例。
  回覆套用 Markdown 格式（標題/粗體/程式碼區塊）。

agent_system_prompt: |
  你是資深 AI 工程師，擅長深度分析與程式碼產出。
  使用繁體中文，複雜問題先列步驟再給結論。
```

### `.env.example`

```bash
TELEGRAM_BOT_TOKEN=your_token
GEMINI_API_KEY=your_key              # 選配，有就用 API 即時對話
GEMINI_CLI_CMD=gemini.cmd            # Windows: gemini.cmd / Linux: gemini
AI_BOT_WORKSPACE=.
```

### `requirements.txt`

```
python-telegram-bot[ext]>=21.0
google-genai>=1.0.0
httpx>=0.27.0
beautifulsoup4>=4.12.0
jinja2>=3.1.0
pyyaml>=6.0.0
python-dotenv>=1.0.0
```

### `start.bat`

```bat
@echo off
chcp 65001 >nul
echo 🤖 AI Agent Bot 啟動中...
py -m src.bot.main
pause
```

---

## 啟動步驟

```bash
# 1. 產出
「ark-ai-bot-builder，專案名稱 my-bot」

# 2. 設定
cd output/my-bot
cp .env.example .env
# 填入 TELEGRAM_BOT_TOKEN（必要）+ GEMINI_API_KEY（選配）

# 3. 安裝
pip install -r requirements.txt

# 4. 啟動
start.bat
# 或 python -m src.bot.main
```

## 使用

```
📱 Telegram 對話：
  「今天有什麼科技新聞」 → 自動抓取 + 渲染 HTML 日報
  「幫我寫一個 HTTP 健康檢查 Skill」 → Agent CLI 產出 .py
  「什麼是 Vector Database」 → Agent CLI 深度回答
  /daily → 手動觸發完整日報
  /skills → 列出已載入 Skills
```

---

---

## 附帶資源結構

```
ark-ai-bot-builder/
├── SKILL.md                      # 本文件（執行計畫）
├── assets/                       # 直接複製到目標的靜態資源
│   ├── news_sources.yaml         # → config/news_sources.yaml
│   ├── llm_prompts.yaml          # → config/llm_prompts.yaml
│   ├── requirements.txt          # → requirements.txt
│   ├── start.bat                 # → start.bat
│   ├── env.example               # → .env.example
│   └── gitignore.txt             # → .gitignore
├── templates/                    # 程式碼樣板（複製為 .py）
│   ├── base.py                   # → src/skills/base.py
│   ├── registry.py               # → src/skills/registry.py
│   ├── echo.py                   # → src/skills/internal/echo.py
│   ├── llm_cli.py                # → src/skills/internal/llm_cli.py（見 SKILL.md 範例）
│   ├── news_scraper.py           # → src/skills/internal/news_scraper.py（見 SKILL.md 範例）
│   ├── news_renderer.py          # → src/skills/internal/news_renderer.py（見 SKILL.md 範例）
│   ├── session.py                # → src/conversation/session.py
│   ├── planner.py                # → src/conversation/planner.py
│   ├── memory_search.py          # → src/conversation/memory_search.py（見 ninja-bot）
│   ├── gemini_chat.py            # → src/llm/gemini_chat.py
│   ├── bot_main.py              # → src/bot/main.py
│   ├── handlers.py               # → src/bot/handlers.py
│   └── tech-daily.html           # → templates/tech-daily.html（見 ninja-bot）
└── scripts/                      # 產出 + 驗證腳本
    ├── build_bot.py              # 一鍵產出整個專案
    └── validate_bot.py           # 驗證結構完整性
```

### scripts/ 使用方式

```bash
# 一鍵產出專案
python .kiro/skills/ark-ai-bot-builder/scripts/build_bot.py ./output/my-bot

# 驗證已有專案
python .kiro/skills/ark-ai-bot-builder/scripts/validate_bot.py ./output/my-bot
```

### assets/ 規則

| 檔案 | 目標路徑 | 說明 |
|------|---------|------|
| `news_sources.yaml` | `config/` | 新聞來源（HN + TechCrunch + Ars） |
| `llm_prompts.yaml` | `config/` | 系統提詞（修改不需改程式碼） |
| `requirements.txt` | 根目錄 | pip 依賴 |
| `start.bat` | 根目錄 | Windows 一鍵啟動 |
| `env.example` | `.env.example` | 環境變數範本 |
| `gitignore.txt` | `.gitignore` | Git 忽略 |

### templates/ 規則

| 檔案 | 目標路徑 | 核心功能 |
|------|---------|----------|
| `base.py` | `src/skills/base.py` | BaseSkill 介面 |
| `registry.py` | `src/skills/registry.py` | auto_discover + hot_reload |
| `echo.py` | `src/skills/internal/echo.py` | 測試 Skill |
| `llm_cli.py` | `src/skills/internal/llm_cli.py` | Agent CLI 大腦 |
| `planner.py` | `src/conversation/planner.py` | 三層意圖路由 |
| `handlers.py` | `src/bot/handlers.py` | 自然語言入口 |
| `bot_main.py` | `src/bot/main.py` | Bot 啟動 |
| `gemini_chat.py` | `src/llm/gemini_chat.py` | Gemini API 即時對話 |

---

## 設計原則

- **自然語言進 CLI** — 不用記指令，說話就好
- **Agent CLI 為大腦** — Gemini/Kiro/Claude 自動偵測 + fallback
- **Skill 即功能** — 新功能 = 新 .py 放入 internal/ 即自動載入
- **零配置啟動** — 只需 TELEGRAM_BOT_TOKEN 就能跑（CLI 自己有授權）
- **資源即程式碼** — `assets/` 直接複製、`templates/` 就是最終 .py

---
metadata:
  version: "2.0"
  updated: 2026-06-22

## 踩坑紀錄（2026-06-22 驗證通過）

### Telegram Reaction 支援清單

`✅` `❌` 不在 Telegram 支援的 Reaction emoji 中。可用：
- 👍 👎 ❤️ 🔥 🎉 😢 👀 🤔 💯

已驗證方案：👀（收到）→ 👍（完成）/ 👎（失敗）

### EventBus 單一實例

FastAPI `lifespan` 會建立自己的 EventBus 覆蓋 `app.state.bus`。
必須在 lifespan 前設定 `app.state.bus = bus` + `app.state._external_bus = True`。

### kiro-cli output 帶 `> ` 前綴

所有 kiro-cli 回覆以 `\x1b[38;5;141m> \x1b[0m` 開頭。
`_extract_conclusion` 不能把 `> ` 當成工具行過濾。

### agent.send() + on_output 重複回覆

`AgentProcess.send()` 內部呼叫 `on_output` callback（觸發 _tg_reply），
同時 handle_message 拿到 return value 又 reply 一次。
解法：`_tg_handled_agents` set 標記正在被 TG handler 處理的 agent。

### filters.COMMAND 攔截 /skill_id

`MessageHandler(filters.TEXT & ~filters.COMMAND)` 會過濾掉 `/` 開頭訊息。
未註冊的 `/echo hello` 不會進入 handle_message。
解法：加 `MessageHandler(filters.COMMAND, handle_message)` 作為 fallback。

### DB agents 表需同步 team.yaml

`start.py` 啟動時必須把 team.yaml instances 寫入 SQLite `agents` 表，
否則 `/api/agents` 回傳空陣列 → TG handler 報「無可用 Agent」。

### typing action 語言

`send_chat_action(action="typing")` 顯示的「正在輸入...」由 Telegram 客戶端語言決定，
Bot 端無法控制。使用者需將 TG App 設為繁中才會顯示中文。
