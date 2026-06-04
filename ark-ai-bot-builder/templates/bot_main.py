"""Telegram Bot 入口 — 一行啟動。"""
import os
import signal
import sys

from dotenv import load_dotenv
from telegram import BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from src.bot.handlers import cmd_start, cmd_skills, cmd_daily, handle_message, init_components
from src.skills.registry import SkillRegistry

load_dotenv()


def create_app():
    """建立 Telegram Bot Application。"""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN 未設定")

    # 初始化 Skill 系統
    registry = SkillRegistry()
    count = registry.auto_discover("src.skills.internal")
    print(f"📦 Skills loaded: {count}")

    init_components(registry)

    app = ApplicationBuilder().token(token).post_init(_post_init).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("skills", cmd_skills))
    app.add_handler(CommandHandler("daily", cmd_daily))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app


async def _post_init(application) -> None:
    """設定 Telegram Menu 指令。"""
    await application.bot.set_my_commands([
        BotCommand("start", "歡迎 + 功能介紹"),
        BotCommand("skills", "列出已載入 Skills"),
        BotCommand("daily", "產出科技日報"),
    ])


if __name__ == "__main__":
    def _shutdown(*_):
        print("\n正在關閉 Bot...")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)

    print("🤖 AI Agent Bot started polling...")
    create_app().run_polling(drop_pending_updates=True)
