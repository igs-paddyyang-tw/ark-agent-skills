"""scaffold_bot.py — 一鍵產出 Telegram Bot + 對話系統。

用法：python scripts/scaffold_bot.py [project_dir]
產出：src/bot/ + src/conversation/（共 10 個檔案）
"""
import sys
from pathlib import Path

FILES: dict[str, str] = {}

FILES["src/bot/__init__.py"] = ""

FILES["src/bot/main.py"] = '''"""Telegram Bot 入口。"""

import logging
import os

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


def create_app():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN 未設定")

    registry = SkillRegistry()
    registry.auto_discover("src.skills.internal")

    llm_router = LLMRouter()
    session_manager = SessionManager(db_path="data/sessions.db")
    planner = ConversationPlanner(skill_ids=[s["id"] for s in registry.list_skills()])
    memory_store = MemoryStore(base_dir="data/memory")

    init_components(registry=registry, session_manager=session_manager, planner=planner, memory_store=memory_store, llm_router=llm_router)

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
    print("🤖 Bot started polling...")
    bot_app.run_polling(drop_pending_updates=True)
'''

FILES["src/bot/handlers.py"] = '''"""Telegram Bot handlers + 自然語言路由。"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from src.skills.registry import SkillRegistry
from src.conversation.session_manager import SessionManager
from src.conversation.planner import ConversationPlanner, PlanAction
from src.conversation.memory import MemoryStore
from src.agent.orchestrator import AgentOrchestrator
from src.agent.delivery import ResultDelivery

logger = logging.getLogger(__name__)

_registry: SkillRegistry | None = None
_session_mgr: SessionManager | None = None
_planner: ConversationPlanner | None = None
_memory: MemoryStore | None = None
_llm_router = None
_orchestrator: AgentOrchestrator | None = None
_delivery: ResultDelivery = ResultDelivery()


def init_components(registry, session_manager=None, planner=None, memory_store=None, llm_router=None):
    global _registry, _session_mgr, _planner, _memory, _llm_router, _orchestrator
    _registry = registry
    _session_mgr = session_manager or SessionManager()
    _planner = planner or ConversationPlanner()
    _memory = memory_store or MemoryStore()
    _llm_router = llm_router
    _orchestrator = AgentOrchestrator(registry)
    _planner.set_skills([s["id"] for s in registry.list_skills()])


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 AI Bot 已就緒\\n直接輸入訊息即可對話\\n/help — 指令說明")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("/start /status /skills /reset /agent <需求>")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    n = len(_registry.list_skills()) if _registry else 0
    await update.message.reply_text(f"✅ 系統正常 | Skills: {n}")

async def cmd_skills(update: Update, context: ContextTypes.DEFAULT_TYPE):
    skills = _registry.list_skills() if _registry else []
    lines = [f"• {s['id']} — {s['description'][:40]}" for s in skills]
    await update.message.reply_text("\\n".join(lines) or "（無）")

async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if _session_mgr:
        _session_mgr.reset(update.effective_user.id)
    await update.message.reply_text("🔄 對話已重置")

async def cmd_agent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = " ".join(context.args) if context.args else ""
    if not text or not _orchestrator:
        await update.message.reply_text("用法：/agent <需求描述>")
        return
    await update.message.reply_text("🤖 評估中...")
    result = await _orchestrator.process(text)
    if result.error:
        await update.message.reply_text(f"❌ {result.error[:500]}")
        return
    async def send_text(t): await update.message.reply_text(t)
    async def send_doc(p): await update.message.reply_document(document=open(p, "rb"))
    async def send_photo(p): await update.message.reply_photo(photo=open(p, "rb"))
    await _delivery.deliver(result.output, send_text, send_doc, send_photo)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text:
        return
    user_id = update.effective_user.id
    text = msg.text.strip()
    session = _session_mgr.get_or_create(user_id)
    session.add_turn("user", text)
    plan = await _planner.plan(session, text)
    if plan.action == PlanAction.EXECUTE:
        result = await _registry.invoke(plan.skill_id, plan.params)
        reply = str(result.data) if result.success else f"❌ {result.error}"
    else:
        reply = text  # fallback echo
    session.add_turn("assistant", reply[:200])
    _session_mgr.save(user_id)
    await msg.reply_text(reply[:4096])
'''

FILES["src/conversation/__init__.py"] = '''from src.conversation.session import Session, Turn
from src.conversation.session_manager import SessionManager
from src.conversation.planner import ConversationPlanner, PlanAction
'''

FILES["src/conversation/session.py"] = '''"""Session + Turn dataclass。"""
from dataclasses import dataclass, field
from time import time


@dataclass
class Turn:
    role: str
    content: str
    timestamp: float = field(default_factory=time)


@dataclass
class Session:
    user_id: int
    turns: list[Turn] = field(default_factory=list)

    def add_turn(self, role: str, content: str) -> None:
        self.turns.append(Turn(role=role, content=content))

    def get_recent_turns(self, n: int = 5) -> list[Turn]:
        return self.turns[-n:]
'''

FILES["src/conversation/session_manager.py"] = '''"""SessionManager — TTL + 生命週期管理。"""
from pathlib import Path
from src.conversation.session import Session


class SessionManager:
    def __init__(self, db_path: str = "data/sessions.db"):
        self._sessions: dict[int, Session] = {}
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    def get_or_create(self, user_id: int) -> Session:
        if user_id not in self._sessions:
            self._sessions[user_id] = Session(user_id=user_id)
        return self._sessions[user_id]

    def reset(self, user_id: int) -> None:
        self._sessions.pop(user_id, None)

    def save(self, user_id: int) -> None:
        pass  # in-memory for now
'''

FILES["src/conversation/planner.py"] = '''"""ConversationPlanner — 意圖路由。"""
from dataclasses import dataclass, field
from enum import Enum


class PlanAction(str, Enum):
    ANSWER = "answer"
    EXECUTE = "execute"
    CLARIFY = "clarify"
    RESET = "reset"


@dataclass
class Plan:
    action: PlanAction = PlanAction.ANSWER
    skill_id: str = ""
    params: dict = field(default_factory=dict)
    clarify_question: str = ""


class ConversationPlanner:
    def __init__(self, skill_ids: list[str] | None = None):
        self._skills = skill_ids or []

    def set_skills(self, skill_ids: list[str]) -> None:
        self._skills = skill_ids

    async def plan(self, session, text: str) -> Plan:
        if text.startswith("/"):
            parts = text[1:].split(" ", 1)
            sid = parts[0]
            if sid in self._skills:
                return Plan(action=PlanAction.EXECUTE, skill_id=sid, params={"message": parts[1] if len(parts) > 1 else ""})
        if any(kw in text for kw in ["重置", "reset", "清除"]):
            return Plan(action=PlanAction.RESET)
        return Plan(action=PlanAction.ANSWER)
'''

FILES["src/conversation/memory.py"] = '''"""MemoryStore — 使用者記憶。"""
from pathlib import Path


class MemoryStore:
    def __init__(self, base_dir: str = "data/memory"):
        self._dir = Path(base_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def get_context(self, user_id: int) -> str:
        f = self._dir / f"{user_id}.txt"
        return f.read_text(encoding="utf-8") if f.exists() else ""

    def save(self, user_id: int, context: str) -> None:
        (self._dir / f"{user_id}.txt").write_text(context, encoding="utf-8")
'''

FILES["src/conversation/progress.py"] = '''"""Progress — 進度回報。"""


class ProgressReporter:
    async def report(self, chat_id: int, text: str) -> None:
        pass  # 由 Bot handler 實作
'''


def scaffold(project_dir: Path) -> list[str]:
    created = []
    for rel_path, content in FILES.items():
        full = project_dir / rel_path
        if full.exists():
            continue
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        created.append(str(rel_path))
    return created


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    files = scaffold(target)
    print(f"✅ scaffold_bot: 產出 {len(files)} 個檔案到 {target}")
    for f in files:
        print(f"   {f}")
