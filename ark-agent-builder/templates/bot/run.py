"""Bot 獨立進程入口 — TG Bot + Agent 常駐服務。"""
import asyncio
import os
import sys
from pathlib import Path

# 確保工作目錄正確
os.chdir(Path(__file__).resolve().parents[2])
sys.path.insert(0, str(Path.cwd()))

from dotenv import load_dotenv
load_dotenv()

from src.logging_config import setup_logging
setup_logging()


async def main():
    import logging
    log = logging.getLogger("bot.run")
    
    # 啟動 Agent 常駐服務
    from src.agent.cli import is_cli_available, start_all_agents
    if is_cli_available():
        count = await start_all_agents()
        log.info("Agent 服務: %d 個已啟動", count)
    
    # 啟動 TG Bot
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not tg_token:
        log.error("TELEGRAM_BOT_TOKEN 未設定")
        return
    
    from src.bot.main import create_app, BOT_COMMANDS
    bot_app = create_app()
    await bot_app.initialize()
    await bot_app.bot.delete_my_commands()
    await bot_app.bot.set_my_commands(BOT_COMMANDS)
    await bot_app.updater.start_polling(drop_pending_updates=True)
    await bot_app.start()
    log.info("TG Bot polling 已啟動")
    
    # 保持運行
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        await bot_app.updater.stop()
        await bot_app.stop()
        await bot_app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
