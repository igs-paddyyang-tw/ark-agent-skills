"""Telegram Bot 入口 — 含 Inline Button 回調。"""
from __future__ import annotations

import os

from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from src.bot.handlers import (
    callback_switch_agent,
    cmd_agents,
    cmd_help,
    cmd_history,
    cmd_mode,
    cmd_start,
    handle_message,
)


def create_app():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN 未設定")

    app = ApplicationBuilder().token(token).build()

    # 指令
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("agents", cmd_agents))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("history", cmd_history))

    # Inline Button 回調
    app.add_handler(CallbackQueryHandler(callback_switch_agent, pattern="^switch_agent:"))

    # 自然語言
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app
