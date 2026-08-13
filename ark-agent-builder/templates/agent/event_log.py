"""結構化事件紀錄 — append-only JSON Lines。

泛化自 ninja-bot src/agent/event_log.py。
"""
from __future__ import annotations

import json
import time
from pathlib import Path


class EventLog:
    """Append-only 事件日誌。"""

    def __init__(self, log_path: str | Path = "data/events.jsonl"):
        self._path = Path(log_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event_type: str, **kwargs) -> None:
        """寫入一筆事件。"""
        record = {
            "ts": time.time(),
            "type": event_type,
            **kwargs,
        }
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def tail(self, n: int = 20) -> list[dict]:
        """讀取最後 n 筆。"""
        if not self._path.exists():
            return []
        lines = self._path.read_text(encoding="utf-8").splitlines()
        return [json.loads(l) for l in lines[-n:]]
