"""SQLite 對話記錄：用 TG message_id 為 PK，支援上下文注入。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "chat_history.db"


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            message_id  INTEGER PRIMARY KEY,
            chat_id     INTEGER NOT NULL,
            user_id     INTEGER NOT NULL,
            role        TEXT NOT NULL,
            content     TEXT NOT NULL,
            reply_to_id INTEGER,
            created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now','localtime'))
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_messages_chat_time
        ON chat_messages(chat_id, created_at DESC)
    """)
    conn.commit()
    return conn


_conn: sqlite3.Connection | None = None


def _db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = _get_conn()
    return _conn


def save_user_message(message_id: int, chat_id: int, user_id: int, content: str) -> None:
    _db().execute(
        "INSERT OR IGNORE INTO chat_messages (message_id, chat_id, user_id, role, content) VALUES (?,?,?,?,?)",
        (message_id, chat_id, user_id, "user", content),
    )
    _db().commit()


def save_bot_message(message_id: int, chat_id: int, bot_id: int, content: str, reply_to_id: int | None = None) -> None:
    _db().execute(
        "INSERT OR IGNORE INTO chat_messages (message_id, chat_id, user_id, role, content, reply_to_id) VALUES (?,?,?,?,?,?)",
        (message_id, chat_id, bot_id, "assistant", content, reply_to_id),
    )
    _db().commit()


def get_context(chat_id: int, rounds: int = 3) -> str:
    """取最近 N 輪對話，格式化為注入 Agent CLI 的上下文字串。"""
    rows = _db().execute(
        "SELECT role, content FROM chat_messages WHERE chat_id = ? ORDER BY created_at DESC, message_id DESC LIMIT ?",
        (chat_id, rounds * 2),
    ).fetchall()
    if not rows:
        return ""
    lines = [f"[{r['role']}] {r['content']}" for r in reversed(rows)]
    return "\n".join(lines)
