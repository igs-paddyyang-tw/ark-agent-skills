"""MemorySearch — 跨 Session 全文搜尋（SQLite FTS5）。"""
from __future__ import annotations

import logging
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

log = logging.getLogger(__name__)


class MemorySearch:
    """跨 Session 對話全文搜尋。索引所有對話，供 LLM 回答時召回。"""

    def __init__(self, db_path: str = "data/sessions.db") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_fts()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_fts(self) -> None:
        """建立 FTS5 虛擬表。"""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    session_id TEXT DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS conversation_fts
                USING fts5(content, content_rowid='id', tokenize='unicode61')
            """)

    def index_turn(self, user_id: int, role: str, content: str, session_id: str = "") -> None:
        """索引一則對話。"""
        if not content or not content.strip():
            return
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    "INSERT INTO conversation_history (user_id, role, content, timestamp, session_id) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (user_id, role, content, time.time(), session_id),
                )
                conn.execute(
                    "INSERT INTO conversation_fts (rowid, content) VALUES (?, ?)",
                    (cursor.lastrowid, content),
                )
        except Exception as e:
            log.warning("索引對話失敗: %s", e)

    def search(self, query: str, user_id: int | None = None, limit: int = 5) -> list[dict]:
        """全文搜尋歷史對話。"""
        if not query or not query.strip():
            return []
        fts_query = " ".join(query.strip().split())
        try:
            with self._connect() as conn:
                if user_id is not None:
                    rows = conn.execute("""
                        SELECT h.role, h.content, h.timestamp
                        FROM conversation_fts fts
                        JOIN conversation_history h ON h.id = fts.rowid
                        WHERE conversation_fts MATCH ? AND h.user_id = ?
                        ORDER BY fts.rank LIMIT ?
                    """, (fts_query, user_id, limit)).fetchall()
                else:
                    rows = conn.execute("""
                        SELECT h.role, h.content, h.timestamp
                        FROM conversation_fts fts
                        JOIN conversation_history h ON h.id = fts.rowid
                        WHERE conversation_fts MATCH ?
                        ORDER BY fts.rank LIMIT ?
                    """, (fts_query, limit)).fetchall()
                return [{"role": r["role"], "content": r["content"]} for r in rows]
        except Exception as e:
            log.warning("搜尋失敗: %s", e)
            return []

    def get_context_for_query(self, query: str, user_id: int, max_chars: int = 2000) -> str:
        """搜尋並格式化為可注入 LLM 的 context。"""
        results = self.search(query, user_id=user_id, limit=5)
        if not results:
            return ""
        lines = ["[歷史回憶]"]
        total = 0
        for r in results:
            snippet = r["content"][:200]
            line = f"- ({r['role']}) {snippet}"
            if total + len(line) > max_chars:
                break
            lines.append(line)
            total += len(line)
        return "\n".join(lines)
