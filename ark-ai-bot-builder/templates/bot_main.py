"""Telegram Bot 入口 — 支援獨立啟動或由 server/main.py 整合啟動。"""
from __future__ import annotations

import os
import signal
import sys

from dotenv import load_dotenv
from telegram import BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from src.bot.handlers import cmd_start, cmd_skills, cmd_daily, cmd_chat, cmd_help, cmd_run, cmd_invoke_skill, cmd_usage, cmd_trace, cmd_wiki, cmd_ask, cmd_retry, cmd_undo, cmd_new, handle_message, handle_callback, init_components
from src.skills.registry import SkillRegistry

load_dotenv()

# 模組層級：保持引用供 shutdown 使用
_schedule_engine = None


def create_app(registry: SkillRegistry | None = None):
    """建立 Telegram Bot Application。

    Args:
        registry: 外部注入的 SkillRegistry（整合模式）。None 時自行建立。
    """
    global _schedule_engine
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN 未設定")

    # Skill 系統：外部注入或自行初始化
    if registry is None:
        registry = SkillRegistry()
        count = registry.auto_discover("src.skills.internal")
        print(f"📦 Skills loaded: {count}")

    init_components(registry)

    app = ApplicationBuilder().token(token).post_init(_post_init).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("skills", cmd_skills))
    app.add_handler(CommandHandler("daily", cmd_daily))
    app.add_handler(CommandHandler("chat", cmd_chat))
    app.add_handler(CommandHandler("run", cmd_run))
    app.add_handler(CommandHandler("usage", cmd_usage))
    app.add_handler(CommandHandler("trace", cmd_trace))
    app.add_handler(CommandHandler("wiki", cmd_wiki))
    app.add_handler(CommandHandler("ask", cmd_ask))
    app.add_handler(CommandHandler("retry", cmd_retry))
    app.add_handler(CommandHandler("undo", cmd_undo))
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(CallbackQueryHandler(handle_callback))
    # catch-all：任何未知 /command 嘗試作為 Skill 執行
    app.add_handler(MessageHandler(filters.COMMAND, cmd_invoke_skill))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app


async def _post_init(application) -> None:
    """設定 Telegram Menu 指令。"""
    await application.bot.set_my_commands([
        BotCommand("chat", "Chatbot 快速模式"),
        BotCommand("daily", "產出科技日報"),
        BotCommand("wiki", "知識庫查詢 / distill"),
        BotCommand("ask", "知識庫問答"),
        BotCommand("run", "執行工作流"),
        BotCommand("skills", "列出 Skills"),
        BotCommand("usage", "今日 API 用量"),
        BotCommand("trace", "呼叫軌跡"),
        BotCommand("help", "模式說明"),
    ])


if __name__ == "__main__":
    from pathlib import Path
    from src.workflow.engine import WorkflowEngine
    from src.scheduler.engine import ScheduleEngine

    def _shutdown(*_):
        print("\n正在關閉 Bot...")
        if _schedule_engine:
            _schedule_engine.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)

    # 獨立模式：自行初始化 Workflow + Schedule
    registry = SkillRegistry()
    registry.auto_discover("src.skills.internal")

    wf_engine = WorkflowEngine(registry)
    wf_engine.load_dir(Path("workflows"))

    _schedule_engine = ScheduleEngine(wf_engine)
    _schedule_engine.load_schedules(Path("workflows/schedules"))
    _schedule_engine.start()

    print("🤖 AI Agent Bot started polling (standalone)...")
    create_app(registry=registry).run_polling(drop_pending_updates=True)
