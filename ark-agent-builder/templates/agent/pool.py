"""Agent 池管理 — 啟動/停止/狀態查詢/負載均衡。

泛化自 ninja-bot src/agent/pool.py。
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class AgentInfo:
    """單一 agent 的運行資訊。"""
    name: str
    role: str  # admin / leader / worker
    status: str = "idle"  # idle / busy / offline
    pid: Optional[int] = None
    current_task: Optional[str] = None
    last_activity: float = 0.0


class AgentPool:
    """管理所有 agent 的生命週期與狀態。"""

    def __init__(self, agents_config: list[dict]):
        self._agents: dict[str, AgentInfo] = {}
        for cfg in agents_config:
            name = cfg["name"]
            self._agents[name] = AgentInfo(
                name=name,
                role=cfg.get("role", "worker"),
            )

    @property
    def available_workers(self) -> list[AgentInfo]:
        """回傳所有閒置 worker。"""
        return [a for a in self._agents.values()
                if a.role == "worker" and a.status == "idle"]

    def get(self, name: str) -> Optional[AgentInfo]:
        return self._agents.get(name)

    def set_busy(self, name: str, task_id: str) -> None:
        if agent := self._agents.get(name):
            agent.status = "busy"
            agent.current_task = task_id

    def set_idle(self, name: str) -> None:
        if agent := self._agents.get(name):
            agent.status = "idle"
            agent.current_task = None

    def all_status(self) -> dict[str, str]:
        return {name: a.status for name, a in self._agents.items()}
