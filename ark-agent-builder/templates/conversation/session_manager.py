"""SessionManager — 多用戶 Session 生命週期管理 + SQLite 持久化。

功能：
- 記憶體快取 + SQLite 雙層儲存
- TTL 自動過期（預設 30 分鐘）
- get_or_create 自動載入/建立
- save 持久化到 SQLite
- reset 清除單一使用者 session
- cleanup 批量清除過期 session

用法：
  manager = SessionManager(db_path="data/sessions.db", ttl=1800)
  session = manager.get_or_create(user_id=12345)
  session.add_turn("user", "你好")
  manager.save(user_id=12345)
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Iterator

from .session import Session, Turn, SessionState

log = logging.getLogger(__name__)


class SessionManager:
    """Per-user Session 管理，記憶體快取 + SQLite 持久化。"""

    def __init__(self, db_path: str = "data/sessions.db", ttl: int = 1800) -> None:
        """初始化。

        參數：
          db_path — SQLite 路徑
          ttl — Session 過期秒數（預設 1800 = 30 分鐘）
        """
        self._sessions: dict[int, Session] = {}
        self.ttl = ttl
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """建立 sessions 表（如不存在）。"""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    user_id INTEGER PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    turns TEXT NOT NULL DEFAULT '[]',
                    state TEXT NOT NULL DEFAULT 'idle',
                    context TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """SQLite 連線 context manager。"""
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def get_or_create(self, user_id: int) -> Session:
        """取得或建立 Session。過期則重建。"""
        s = self._sessions.get(user_id)
        if s and not s.is_expired(self.ttl):
            return s
        # 嘗試從 DB 載入
        s = self._load(user_id)
        if s and not s.is_expired(self.ttl):
            self._sessions[user_id] = s
            return s
        # 建立新 Session
        s = Session(user_id=user_id)
        self._sessions[user_id] = s
        return s

    def save(self, user_id: int) -> None:
        """持久化 Session 到 SQLite。"""
        s = self._sessions.get(user_id)
        if not s:
            return
        turns_json = json.dumps([asdict(t) for t in s.turns], ensure_ascii=False)
        ctx_json = json.dumps(s.context, ensure_ascii=False)
        try:
            with self._connect() as conn:
                conn.execute("""
                    INSERT INTO sessions (user_id, session_id, turns, state, context, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        session_id=excluded.session_id, turns=excluded.turns,
                        state=excluded.state, context=excluded.context,
                        updated_at=excluded.updated_at
                """, (user_id, s.session_id, turns_json, s.state.value, ctx_json, s.created_at, s.updated_at))
        except Exception as e:
            log.warning("Session save failed for user %s: %s", user_id, e)

    def reset(self, user_id: int) -> None:
        """清除使用者 session（記憶體 + DB）。"""
        self._sessions.pop(user_id, None)
        try:
            with self._connect() as conn:
                conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        except Exception:
            pass

    def cleanup(self) -> int:
        """清除所有過期 session，回傳清除數量。"""
        now = time.time()
        cutoff = now - self.ttl
        expired = [uid for uid, s in self._sessions.items() if s.updated_at < cutoff]
        for uid in expired:
            del self._sessions[uid]
        try:
            with self._connect() as conn:
                cursor = conn.execute("DELETE FROM sessions WHERE updated_at < ?", (cutoff,))
                return cursor.rowcount + len(expired)
        except Exception:
            return len(expired)

    def _load(self, user_id: int) -> Session | None:
        """從 SQLite 載入 session。"""
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM sessions WHERE user_id = ?", (user_id,)
                ).fetchone()
        except Exception:
            return None
        if not row:
            return None
        turns = [Turn(**t) for t in json.loads(row["turns"] or "[]")]
        return Session(
            session_id=row["session_id"],
            user_id=user_id,
            turns=turns,
            state=SessionState(row["state"]),
            context=json.loads(row["context"] or "{}"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
