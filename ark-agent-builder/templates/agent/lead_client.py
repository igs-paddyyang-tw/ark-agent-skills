"""Lead → Worker 通訊協定。

負責：發送任務、接收回報、狀態同步。
泛化自 ninja-bot src/agent/lead_client.py。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)


class LeadClient:
    """Leader agent 與 worker 之間的通訊層。"""

    def __init__(self, send_fn: Callable, pool: Any):
        """
        Args:
            send_fn: 發送訊息的 async callable(agent_name, message) -> response
            pool: AgentPool 實例
        """
        self._send = send_fn
        self._pool = pool
        self._pending: dict[str, asyncio.Future] = {}

    async def dispatch(self, agent_name: str, task: dict) -> str:
        """派工給指定 agent，回傳 task_id。"""
        task_id = task.get("id", f"task-{id(task)}")
        self._pool.set_busy(agent_name, task_id)
        log.info("Dispatching %s to %s", task_id, agent_name)
        await self._send(agent_name, {
            "type": "task_assign",
            "task": task,
        })
        return task_id

    async def receive_report(self, agent_name: str, report: dict) -> None:
        """收到 worker 回報。"""
        task_id = report.get("task_id")
        log.info("Report from %s for %s", agent_name, task_id)
        self._pool.set_idle(agent_name)
        if task_id and task_id in self._pending:
            self._pending[task_id].set_result(report)

    async def wait_for(self, task_id: str, timeout: float = 300) -> Optional[dict]:
        """等待指定任務完成。"""
        fut = asyncio.get_event_loop().create_future()
        self._pending[task_id] = fut
        try:
            return await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            log.warning("Task %s timed out", task_id)
            return None
        finally:
            self._pending.pop(task_id, None)
