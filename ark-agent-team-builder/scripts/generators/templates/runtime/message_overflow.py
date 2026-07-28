"""訊息溢出持久化 — SQLite fallback，backpressure 時保存未送達訊息。"""
from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path

log = logging.getLogger(__name__)


class MessageOverflow:
    """Stores messages that couldn't be delivered due to backpressure."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS overflow (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instance TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at REAL NOT NULL,
                delivered INTEGER DEFAULT 0
            )
        """)
        self._conn.commit()

    def store(self, instance: str, message: str) -> None:
        """Store a message that couldn't be delivered."""
        self._conn.execute(
            "INSERT INTO overflow (instance, message, created_at) VALUES (?, ?, ?)",
            (instance, message, time.time()),
        )
        self._conn.commit()
        log.debug("Overflow stored for %s (%d chars)", instance, len(message))

    def pending(self, instance: str, limit: int = 10) -> list[tuple[int, str]]:
        """Get pending messages for an instance."""
        cur = self._conn.execute(
            "SELECT id, message FROM overflow WHERE instance = ? AND delivered = 0 ORDER BY id LIMIT ?",
            (instance, limit),
        )
        return cur.fetchall()

    def mark_delivered(self, msg_id: int) -> None:
        """Mark a message as delivered."""
        self._conn.execute("UPDATE overflow SET delivered = 1 WHERE id = ?", (msg_id,))
        self._conn.commit()

    def cleanup(self, max_age_hours: int = 24) -> int:
        """Remove old delivered messages."""
        cutoff = time.time() - max_age_hours * 3600
        cur = self._conn.execute(
            "DELETE FROM overflow WHERE delivered = 1 OR created_at < ?", (cutoff,)
        )
        self._conn.commit()
        return cur.rowcount

    def count_pending(self, instance: str) -> int:
        """Count pending messages for an instance."""
        cur = self._conn.execute(
            "SELECT COUNT(*) FROM overflow WHERE instance = ? AND delivered = 0",
            (instance,),
        )
        return cur.fetchone()[0]

    def close(self) -> None:
        self._conn.close()
