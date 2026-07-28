"""Chat Trace Log — 對話摘要軌跡追蹤。

只存摘要重點：誰問了什麼 → 誰處理 → 路徑 → 結果。
SQLite 儲存，7 天自動清理。
"""
from __future__ import annotations

import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class TraceEntry:
    """單筆對話軌跡。"""
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    timestamp: float = field(default_factory=time.time)
    user_input_summary: str = ""
    target_agent: str = ""
    route_path: str = ""
    reply_summary: str = ""
    success: bool | None = None  # None=進行中, True=成功, False=失敗


class ChatTraceStore:
    """SQLite-backed trace 儲存。"""

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            db_path = Path("state") / "chat_trace.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS traces (
                trace_id TEXT PRIMARY KEY,
                timestamp REAL NOT NULL,
                user_input_summary TEXT DEFAULT '',
                target_agent TEXT DEFAULT '',
                route_path TEXT DEFAULT '',
                reply_summary TEXT DEFAULT '',
                success INTEGER DEFAULT NULL
            )
        """)
        self._conn.commit()

    def create(self, user_input: str, target_agent: str) -> str:
        """建立新 trace，回傳 trace_id。"""
        trace_id = uuid.uuid4().hex[:8]
        self._conn.execute(
            "INSERT INTO traces (trace_id, timestamp, user_input_summary, target_agent) VALUES (?, ?, ?, ?)",
            (trace_id, time.time(), user_input[:50], target_agent),
        )
        self._conn.commit()
        return trace_id

    def append_route(self, trace_id: str, hop: str) -> None:
        """追加路徑（如 pm→coder）。"""
        row = self._conn.execute(
            "SELECT route_path FROM traces WHERE trace_id=?", (trace_id,)
        ).fetchone()
        if not row:
            return
        current = row["route_path"] or ""
        new_path = f"{current}→{hop}" if current else hop
        self._conn.execute(
            "UPDATE traces SET route_path=? WHERE trace_id=?",
            (new_path, trace_id),
        )
        self._conn.commit()

    def complete(self, trace_id: str, reply_summary: str, success: bool = True) -> None:
        """標記完成。"""
        self._conn.execute(
            "UPDATE traces SET reply_summary=?, success=? WHERE trace_id=?",
            (reply_summary[:80], 1 if success else 0, trace_id),
        )
        self._conn.commit()

    def fail(self, trace_id: str, reason: str = "超時") -> None:
        """標記失敗。"""
        self._conn.execute(
            "UPDATE traces SET reply_summary=?, success=0 WHERE trace_id=?",
            (reason[:80], trace_id),
        )
        self._conn.commit()

    def recent(self, limit: int = 20) -> list[dict]:
        """取最近 N 筆。"""
        rows = self._conn.execute(
            "SELECT * FROM traces ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def cleanup(self, max_age_days: int = 7) -> int:
        """清理超過 N 天的紀錄。"""
        cutoff = time.time() - max_age_days * 86400
        cur = self._conn.execute("DELETE FROM traces WHERE timestamp < ?", (cutoff,))
        self._conn.commit()
        return cur.rowcount

    def close(self) -> None:
        self._conn.close()


# ── 全域 singleton ──

_store: ChatTraceStore | None = None


def get_trace_store() -> ChatTraceStore:
    global _store
    if _store is None:
        _store = ChatTraceStore()
    return _store
