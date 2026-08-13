"""遙測模組 — 訊息計數、延遲、錯誤率。

泛化自 ninja-bot src/conversation/telemetry.py。
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class Metrics:
    total_messages: int = 0
    total_errors: int = 0
    latency_sum: float = 0.0
    latency_count: int = 0
    per_agent: dict = field(default_factory=lambda: defaultdict(int))

    @property
    def avg_latency(self) -> float:
        return self.latency_sum / self.latency_count if self.latency_count else 0

    @property
    def error_rate(self) -> float:
        return self.total_errors / self.total_messages if self.total_messages else 0


class Telemetry:
    """輕量遙測收集器。"""

    def __init__(self):
        self._metrics = Metrics()
        self._start_times: dict[str, float] = {}

    def on_message_in(self, message_id: str, agent: str = "") -> None:
        self._metrics.total_messages += 1
        self._metrics.per_agent[agent] += 1
        self._start_times[message_id] = time.time()

    def on_message_out(self, message_id: str) -> None:
        if start := self._start_times.pop(message_id, None):
            latency = time.time() - start
            self._metrics.latency_sum += latency
            self._metrics.latency_count += 1

    def on_error(self) -> None:
        self._metrics.total_errors += 1

    def snapshot(self) -> dict:
        return {
            "total_messages": self._metrics.total_messages,
            "avg_latency_ms": round(self._metrics.avg_latency * 1000, 1),
            "error_rate": round(self._metrics.error_rate, 4),
            "per_agent": dict(self._metrics.per_agent),
        }
