"""健康監控 — 定期檢查 agent 狀態，自動重啟。

泛化自 ninja-bot src/bot/health_monitor.py。
"""
from __future__ import annotations

import asyncio
import logging
import time

log = logging.getLogger(__name__)


class HealthMonitor:
    """定期 ping 各 agent，偵測無回應並觸發重啟。"""

    def __init__(self, pool, check_interval: int = 60, timeout: int = 300):
        self._pool = pool
        self._interval = check_interval
        self._timeout = timeout
        self._running = False

    async def start(self) -> None:
        self._running = True
        asyncio.create_task(self._loop())
        log.info("HealthMonitor started (interval=%ds)", self._interval)

    async def stop(self) -> None:
        self._running = False

    async def _loop(self) -> None:
        while self._running:
            await asyncio.sleep(self._interval)
            now = time.time()
            for name, agent in self._pool._agents.items():
                if agent.status == "busy" and (now - agent.last_activity) > self._timeout:
                    log.warning("Agent %s unresponsive (%.0fs), triggering restart",
                                name, now - agent.last_activity)
                    # 觸發重啟（由上層實作）
                    agent.status = "offline"
