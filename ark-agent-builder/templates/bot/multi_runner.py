"""多 Bot 並行運行器。

支援同時運行多個 TG bot（如主 bot + admin bot），
共用同一個 event loop。
泛化自 ninja-bot src/bot/multi_runner.py。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

log = logging.getLogger(__name__)


class BotRunner:
    """單一 bot 的封裝。"""
    def __init__(self, name: str, app: Any):
        self.name = name
        self.app = app

    async def start(self) -> None:
        log.info("Starting bot: %s", self.name)
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)

    async def stop(self) -> None:
        log.info("Stopping bot: %s", self.name)
        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()


class MultiRunner:
    """並行管理多個 TG bot。"""

    def __init__(self):
        self._bots: list[BotRunner] = []

    def add(self, name: str, app: Any) -> None:
        self._bots.append(BotRunner(name, app))

    async def run_all(self) -> None:
        """啟動所有 bot 並保持運行。"""
        for bot in self._bots:
            await bot.start()
        log.info("All %d bots started", len(self._bots))
        try:
            await asyncio.Event().wait()  # 永久等待
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            for bot in reversed(self._bots):
                await bot.stop()
