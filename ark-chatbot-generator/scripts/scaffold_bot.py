#!/usr/bin/env python3
"""scaffold_bot.py — 確定性產出 Telegram Bot + 對話系統。

使用方式：
    python scaffold_bot.py <project_dir>

產出：
  src/bot/main.py           — create_app + graceful shutdown
  src/bot/handlers.py       — 指令 + 自然語言路由（走 Planner）
  src/conversation/session.py
  src/conversation/session_manager.py
  src/conversation/planner.py  — 三層路由（keyword 快速 → LLM → fallback）
  src/conversation/memory.py
  src/agent/orchestrator.py
  src/agent/delivery.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# ─── 檔案內容 ─────────────────────────────────────────────

BOT_INIT = '"""Bot 模組。"""\n'

BOT_MAIN = '''\
"""Telegram Bot 入口 — create_app + graceful shutdown。"""
from __future__ import annotations

import logging
import os
import signal
import sys

from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from src.bot.handlers import (
    cmd_start, cmd_help, cmd_status, cmd_skills, cmd_reset, cmd_agent,
    handle_message, init_components,
)
from src.skills.registry import SkillRegistry
from src.conversation.session_manager import SessionManager
from src.conversation.planner import ConversationPlanner
from src.conversation.memory import MemoryStore
from src.llm.llm_router import LLMRouter

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)


def create_app():
    """建立 Telegram Bot Application。"""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN 未設定")

    registry = SkillRegistry()
    registry.auto_discover("src.skills.internal")

    llm_router = LLMRouter()
    session_manager = SessionManager(db_path="data/sessions.db")
    planner = ConversationPlanner(skill_ids=[s["id"] for s in registry.list_skills()])
    memory_store = MemoryStore(base_dir="data/memory")

    init_components(
        registry=registry,
        session_manager=session_manager,
        planner=planner,
        memory_store=memory_store,
        llm_router=llm_router,
    )

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("skills", cmd_skills))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("agent", cmd_agent))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app


if __name__ == "__main__":
    bot_app = create_app()

    def _shutdown(*_):
        print("\\n正在關閉 Bot...")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    print("\\U0001f916 Bot started polling...")
    bot_app.run_polling(drop_pending_updates=True)
'''

BOT_HANDLERS = '''\
"""Telegram Bot handlers — 指令 + 自然語言路由。

管線：Session -> Planner（三層路由）-> Skill 執行 / LLM 對話。
"""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.skills.registry import SkillRegistry
from src.conversation.session_manager import SessionManager
from src.conversation.planner import ConversationPlanner, PlanAction
from src.conversation.memory import MemoryStore
from src.agent.orchestrator import AgentOrchestrator
from src.agent.delivery import ResultDelivery

log = logging.getLogger(__name__)

_registry: SkillRegistry | None = None
_session_mgr: SessionManager | None = None
_planner: ConversationPlanner | None = None
_memory: MemoryStore | None = None
_llm_router = None
_orchestrator: AgentOrchestrator | None = None
_delivery: ResultDelivery = ResultDelivery()


def init_components(registry, session_manager=None, planner=None, memory_store=None, llm_router=None):
    """初始化共用元件（由 bot/main.py 呼叫）。"""
    global _registry, _session_mgr, _planner, _memory, _llm_router, _orchestrator
    _registry = registry
    _session_mgr = session_manager or SessionManager()
    _planner = planner or ConversationPlanner()
    _memory = memory_store or MemoryStore()
    _llm_router = llm_router
    _orchestrator = AgentOrchestrator(registry)
    _planner.set_skills([s["id"] for s in registry.list_skills()])


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "\\U0001f916 AI Bot 已就緒\\n\\n"
        "直接輸入訊息即可對話（自然語言路由）\\n\\n"
        "指令：/help /status /skills /reset /agent"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "/start — 歡迎訊息\\n"
        "/status — 系統狀態\\n"
        "/skills — 已載入 Skills\\n"
        "/reset — 重置對話\\n"
        "/agent <需求> — 自進化模式\\n\\n"
        "直接輸入文字即可對話"
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    n = len(_registry.list_skills()) if _registry else 0
    await update.message.reply_text("\\u2705 系統正常 | Skills: %d" % n)


async def cmd_skills(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    skills = _registry.list_skills() if _registry else []
    lines = ["\\u2022 %s \\u2014 %s" % (s["id"], s["description"][:40]) for s in skills]
    await update.message.reply_text("\\n".join(lines) or "（無）")


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if _session_mgr:
        _session_mgr.reset(update.effective_user.id)
    await update.message.reply_text("\\U0001f504 對話已重置")


async def cmd_agent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """自進化 Agent 模式。"""
    text = " ".join(context.args) if context.args else ""
    if not text or not _orchestrator:
        await update.message.reply_text("用法：/agent <需求描述>")
        return
    await update.message.reply_text("\\U0001f916 評估中...")
    result = await _orchestrator.process(text)
    if not result.success:
        await update.message.reply_text("\\u274c %s" % result.error[:500])
        return
    async def send_text(t): await update.message.reply_text(t)
    async def send_doc(p): await update.message.reply_document(document=open(p, "rb"))
    async def send_photo(p): await update.message.reply_photo(photo=open(p, "rb"))
    phases = " \\u2192 ".join(result.data.get("phases", []))
    await update.message.reply_text("\\u2705 完成（%s）" % phases)
    await _delivery.deliver(result.data.get("output"), send_text, send_doc, send_photo)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """自然語言訊息處理：Session -> Planner -> Skill/LLM。"""
    msg = update.effective_message
    if not msg or not msg.text:
        return

    user_id = update.effective_user.id
    text = msg.text.strip()

    session = _session_mgr.get_or_create(user_id)
    session.add_turn("user", text)

    plan = await _planner.plan(session, text)

    if plan.action == PlanAction.RESET:
        _session_mgr.reset(user_id)
        await msg.reply_text("\\U0001f504 對話已重置")
        return

    if plan.action == PlanAction.EXECUTE:
        result = await _registry.invoke(plan.skill_id, plan.params)
        reply = str(result.data) if result.success else "\\u274c %s" % result.error
        session.add_turn("assistant", reply[:200])
        _session_mgr.save(user_id)
        await msg.reply_text(reply[:4096])
        return

    if plan.action == PlanAction.CLARIFY:
        session.add_turn("assistant", plan.clarify_question)
        _session_mgr.save(user_id)
        await msg.reply_text("\\u2753 %s" % plan.clarify_question)
        return

    # ANSWER — LLM 對話
    if _llm_router:
        result = await _llm_router.generate(prompt=text, system="你是智能助理，用繁體中文回答。")
        reply = result["text"] or text
    else:
        reply = text
    session.add_turn("assistant", reply[:200])
    _session_mgr.save(user_id)
    await msg.reply_text(reply[:4096])
'''

CONV_INIT = '"""對話管理模組。"""\n'

SESSION_PY = '''\
"""Session 與 Turn 資料結構。"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class Turn:
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class Session:
    user_id: int = 0
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    turns: list[Turn] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def add_turn(self, role: str, content: str) -> Turn:
        t = Turn(role=role, content=content)
        self.turns.append(t)
        if len(self.turns) > 20:
            self.turns = self.turns[-20:]
        self.updated_at = time.time()
        return t

    def get_recent_turns(self, n: int = 5) -> list[Turn]:
        return self.turns[-n:]

    def is_expired(self, ttl: int = 1800) -> bool:
        return (time.time() - self.updated_at) > ttl
'''

SESSION_MANAGER_PY = '''\
"""SessionManager — 記憶體 Session 管理。"""
from __future__ import annotations

from pathlib import Path

from .session import Session


class SessionManager:
    def __init__(self, db_path: str = "data/sessions.db", ttl: int = 1800) -> None:
        self._sessions: dict[int, Session] = {}
        self._ttl = ttl
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    def get_or_create(self, user_id: int) -> Session:
        s = self._sessions.get(user_id)
        if s and not s.is_expired(self._ttl):
            return s
        s = Session(user_id=user_id)
        self._sessions[user_id] = s
        return s

    def reset(self, user_id: int) -> None:
        self._sessions.pop(user_id, None)

    def save(self, user_id: int) -> None:
        pass  # in-memory for now
'''

PLANNER_PY = '''\
"""ConversationPlanner — 三層路由（keyword 快速 -> LLM intent -> keyword fallback）。"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum

from .session import Session

log = logging.getLogger(__name__)


class PlanAction(str, Enum):
    EXECUTE = "execute"
    CLARIFY = "clarify"
    ANSWER = "answer"
    RESET = "reset"


@dataclass
class ExecutionPlan:
    action: PlanAction
    skill_id: str = ""
    params: dict = field(default_factory=dict)
    clarify_question: str = ""
    answer_text: str = ""


INTENT_LIST = ["skill_call", "chat", "codegen", "news", "system_status", "reset", "unknown"]

_KEYWORD_MAP: list[tuple[list[str], str, str]] = [
    (["新聞", "news", "今日新聞", "daily"], "skill_call", "news_scraper"),
    (["程式", "code", "寫", "產出", "generate"], "codegen", ""),
    (["狀態", "status", "健康"], "system_status", ""),
    (["取消", "重來", "reset", "重新開始"], "reset", ""),
    (["echo", "回音"], "skill_call", "echo"),
]


def _keyword_fallback(text: str) -> dict:
    """LLM 不可用時的關鍵字匹配。"""
    lower = text.lower()
    for keywords, intent, skill_id in _KEYWORD_MAP:
        if any(k in lower for k in keywords):
            result = {"intent": intent, "confidence": 0.6}
            if skill_id:
                result["skill_id"] = skill_id
            return result
    return {"intent": "chat", "confidence": 0.3}


_QUICK_ROUTE: list[tuple[list[str], str, str]] = [
    (["抓新聞", "爬蟲", "scrape news", "今日新聞", "daily news"], "news_scraper", "chat"),
    (["產出日報", "日報", "render", "html 報表"], "news_renderer", "chat"),
    (["程式", "code", "寫一個", "generate", "codegen"], "llm_cli", "codegen"),
    (["echo", "回音"], "echo", "chat"),
]


def _keyword_quick_route(text: str, skill_ids: list[str]) -> ExecutionPlan | None:
    """keyword 快速路由，命中時不呼叫 LLM。"""
    lower = text.lower()
    for keywords, skill_id, mode in _QUICK_ROUTE:
        if skill_id in skill_ids and any(kw in lower for kw in keywords):
            return ExecutionPlan(
                action=PlanAction.EXECUTE,
                skill_id=skill_id,
                params={"prompt": text, "mode": mode},
            )
    return None


_INTENT_PROMPT = """你是意圖分類器。分析用戶訊息，回傳純 JSON。
可用意圖：{intents}
可用 Skills：{skills}
回傳：{{"intent": "...", "skill_id": "...", "params": {{}}, "confidence": 0.0-1.0}}
對話歷史：{history}
用戶訊息：{message}
只回傳 JSON。"""


async def _llm_parse_intent(message: str, history: str, skills: list[str]) -> dict | None:
    """透過 LLM 解析意圖。失敗回傳 None。"""
    from src.skills.internal.llm_cli import LlmCliSkill

    prompt = _INTENT_PROMPT.format(
        intents=", ".join(INTENT_LIST),
        skills=", ".join(skills) if skills else "（無）",
        history=history or "（無）",
        message=message,
    )
    skill = LlmCliSkill()
    try:
        result = await skill.execute({"prompt": prompt, "mode": "evaluate", "timeout": 30})
        if result.success and result.data and "intent" in result.data:
            return result.data
    except Exception as e:
        log.warning("LLM intent parse failed: %s", e)
    return None


class ConversationPlanner:
    """三層路由對話規劃器。"""

    def __init__(self, skill_ids: list[str] | None = None) -> None:
        self._skill_ids = skill_ids or []

    def set_skills(self, skill_ids: list[str]) -> None:
        self._skill_ids = skill_ids

    async def plan(self, session: Session, message: str) -> ExecutionPlan:
        # 1. Reset
        if re.match(r"^(取消|重來|重新開始|/reset)$", message.strip(), re.I):
            return ExecutionPlan(action=PlanAction.RESET)

        # 2. /skill_id 指令
        cmd_match = re.match(r"^/(\\w+)\\s*(.*)", message.strip())
        if cmd_match:
            sid = cmd_match.group(1)
            if sid in self._skill_ids:
                return ExecutionPlan(
                    action=PlanAction.EXECUTE,
                    skill_id=sid,
                    params={"input": cmd_match.group(2).strip()} if cmd_match.group(2) else {},
                )

        # 3. keyword 快速路由（不呼叫 LLM）
        quick = _keyword_quick_route(message, self._skill_ids)
        if quick:
            return quick

        # 4. 組裝歷史
        recent = session.get_recent_turns(5)
        history = "\\n".join(
            "%s：%s" % ("用戶" if t.role == "user" else "助理", t.content[:100])
            for t in recent[:-1]
        )

        # 5. LLM 意圖解析
        intent_result = await _llm_parse_intent(message, history, self._skill_ids)
        if not intent_result:
            intent_result = _keyword_fallback(message)

        intent = intent_result.get("intent", "chat")

        if intent == "reset":
            return ExecutionPlan(action=PlanAction.RESET)
        if intent == "skill_call":
            skill_id = intent_result.get("skill_id", "")
            if skill_id and skill_id in self._skill_ids:
                return ExecutionPlan(action=PlanAction.EXECUTE, skill_id=skill_id, params=intent_result.get("params", {}))
            return ExecutionPlan(action=PlanAction.ANSWER)
        if intent == "codegen":
            return ExecutionPlan(action=PlanAction.EXECUTE, skill_id="llm_cli", params={"prompt": message, "mode": "codegen"})

        return ExecutionPlan(action=PlanAction.ANSWER)
'''

MEMORY_PY = '''\
"""MemoryStore — 使用者記憶。"""
from __future__ import annotations

from pathlib import Path


class MemoryStore:
    def __init__(self, base_dir: str = "data/memory") -> None:
        self._dir = Path(base_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def get_context(self, user_id: int) -> str:
        f = self._dir / ("%d.txt" % user_id)
        return f.read_text(encoding="utf-8") if f.exists() else ""

    def save(self, user_id: int, context: str) -> None:
        (self._dir / ("%d.txt" % user_id)).write_text(context, encoding="utf-8")
'''

ORCHESTRATOR_PY = '''\
"""AgentOrchestrator — 自進化 Agent 流程控制。"""
from __future__ import annotations

import importlib
import logging
import sys

from src.skills.base import BaseSkill, SkillResult
from src.skills.registry import SkillRegistry

log = logging.getLogger(__name__)


class AgentOrchestrator:
    def __init__(self, registry: SkillRegistry) -> None:
        self._registry = registry
        self._gen_count = 0

    async def process(self, user_message: str) -> SkillResult:
        """處理使用者訊息，回傳 SkillResult。"""
        eval_result = await self._evaluate(user_message)
        action = eval_result.get("action", "answer")
        phases = ["evaluate"]

        if action == "answer":
            output = eval_result.get("raw") or await self._direct_answer(user_message)
            return SkillResult(success=True, data={"output": output, "action": action, "phases": phases})

        if action == "invoke":
            skill_id = eval_result.get("skill_id", "")
            result = await self._registry.invoke(skill_id, eval_result.get("params", {}))
            phases.append("execute")
            if result.success:
                return SkillResult(success=True, data={"output": result.data, "action": action, "skill_id": skill_id, "phases": phases})
            return SkillResult(success=False, error=result.error, data={"action": action, "phases": phases})

        if action == "generate":
            if self._gen_count >= 3:
                return SkillResult(success=False, error="Skill 產出達上限")
            spec = eval_result.get("spec", {})
            skill_id = spec.get("id", "generated_skill")
            gen_result = await self._generate_skill(skill_id, spec.get("description", user_message))
            phases.append("generate")
            if not gen_result.success:
                return SkillResult(success=False, error=gen_result.error, data={"phases": phases})
            self._gen_count += 1
            self._hot_reload(skill_id)
            result = await self._registry.invoke(skill_id, spec.get("params", {}))
            phases.append("execute")
            return SkillResult(success=result.success, data={"output": result.data, "action": action, "skill_id": skill_id, "phases": phases}, error=result.error)

        output = await self._direct_answer(user_message)
        return SkillResult(success=True, data={"output": output, "action": "answer", "phases": phases})

    async def _evaluate(self, message: str) -> dict:
        llm = self._registry.get("llm_cli") or self._registry.get("gemini_cli")
        if not llm:
            return {"action": "answer", "raw": ""}
        result = await llm.execute({"prompt": message, "mode": "evaluate"})
        return result.data if result.success else {"action": "answer", "raw": ""}

    async def _direct_answer(self, message: str) -> str:
        llm = self._registry.get("llm_cli") or self._registry.get("gemini_cli")
        if not llm:
            return message
        result = await llm.execute({"prompt": message, "mode": "chat"})
        return result.data.get("output", "") if result.success else result.error

    async def _generate_skill(self, skill_id: str, description: str) -> SkillResult:
        llm = self._registry.get("llm_cli") or self._registry.get("gemini_cli")
        if not llm:
            return SkillResult(success=False, error="無可用 LLM")
        return await llm.execute({"prompt": description, "mode": "skill_gen", "skill_id": skill_id, "output_path": "src/skills/internal/%s.py" % skill_id})

    def _hot_reload(self, skill_id: str) -> bool:
        module_name = "src.skills.internal.%s" % skill_id
        if module_name in sys.modules:
            del sys.modules[module_name]
        try:
            mod = importlib.import_module(module_name)
            for attr_name in dir(mod):
                cls = getattr(mod, attr_name)
                if isinstance(cls, type) and issubclass(cls, BaseSkill) and cls is not BaseSkill and getattr(cls, "skill_id", ""):
                    self._registry.register(cls())
                    return True
        except Exception as e:
            log.error("Hot reload failed: %s", e)
        return False
'''

DELIVERY_PY = '''\
"""ResultDelivery — 結果交付（文字/檔案/圖片）。"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Awaitable


class ResultDelivery:
    async def deliver(
        self,
        output: Any,
        send_text: Callable[[str], Awaitable],
        send_doc: Callable[[str], Awaitable],
        send_photo: Callable[[str], Awaitable],
    ) -> None:
        if output is None:
            await send_text("\\u26a0\\ufe0f 無結果")
            return
        if isinstance(output, str):
            if Path(output).exists() and Path(output).suffix in (".html", ".pdf", ".docx"):
                await send_doc(output)
            elif Path(output).exists() and Path(output).suffix in (".png", ".jpg"):
                await send_photo(output)
            else:
                await send_text(output[:4096])
            return
        if isinstance(output, dict):
            text = output.get("output") or output.get("text") or str(output)
            await send_text(str(text)[:4096])
            return
        await send_text(str(output)[:4096])
'''

# ─── Scaffold 邏輯 ────────────────────────────────────────

FILES: dict[str, str] = {
    "src/bot/__init__.py": BOT_INIT,
    "src/bot/main.py": BOT_MAIN,
    "src/bot/handlers.py": BOT_HANDLERS,
    "src/conversation/__init__.py": CONV_INIT,
    "src/conversation/session.py": SESSION_PY,
    "src/conversation/session_manager.py": SESSION_MANAGER_PY,
    "src/conversation/planner.py": PLANNER_PY,
    "src/conversation/memory.py": MEMORY_PY,
    "src/agent/__init__.py": "",
    "src/agent/orchestrator.py": ORCHESTRATOR_PY,
    "src/agent/delivery.py": DELIVERY_PY,
}


def scaffold(project_dir: Path) -> list[str]:
    """產出 Bot + 對話系統檔案。回傳已產出清單。"""
    created: list[str] = []
    for rel, content in FILES.items():
        full = project_dir / rel
        if full.exists():
            continue
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        created.append(rel)
    return created


def main() -> None:
    if len(sys.argv) < 2:
        print("使用方式: python scaffold_bot.py <project_dir>")
        sys.exit(1)

    project_dir = Path(sys.argv[1])
    project_dir.mkdir(parents=True, exist_ok=True)
    created = scaffold(project_dir)

    if created:
        print("✅ 產出 %d 個檔案：" % len(created))
        for f in created:
            print("   • %s" % f)
    else:
        print("✅ 所有檔案已存在。")


if __name__ == "__main__":
    main()
