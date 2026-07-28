"""Chat Trace — 記錄每次對話的路由軌跡。

SQLite 儲存於 state/chat_trace.db，保留 7 天自動清理。
"""
from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "state" / "chat_trace.db"
RETENTION_DAYS = 7


@dataclass
class TraceRecord:
    """單筆 Trace 資料。"""
    trace_id: str
    timestamp: str
    user_input_summary: str = ""
    ark_decision: str = ""
    target_agent: str | None = None
    route_path: str = ""
    reply_summary: str = ""
    success: bool | None = None


def _get_conn() -> sqlite3.Connection:
    """取得 DB 連線（自動建表）。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS traces (
            trace_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            user_input_summary TEXT DEFAULT '',
            ark_decision TEXT DEFAULT '',
            target_agent TEXT,
            route_path TEXT DEFAULT '',
            reply_summary TEXT DEFAULT '',
            success INTEGER
        )
    """)
    conn.commit()
    return conn


def create_trace(user_input: str) -> str:
    """建立新 trace（handle_message 收到訊息時呼叫）。

    Returns:
        trace_id (UUID)
    """
    trace_id = str(uuid.uuid4())[:8]
    timestamp = datetime.now().isoformat(timespec="seconds")
    summary = user_input[:50]

    try:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO traces (trace_id, timestamp, user_input_summary) VALUES (?, ?, ?)",
            (trace_id, timestamp, summary),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log.warning("create_trace failed: %s", e)

    return trace_id


def update_trace_decision(trace_id: str, ark_decision: str, target_agent: str | None = None, route_path: str = "") -> None:
    """更新 trace 的決策欄位（Ark Agent 判斷後呼叫）。"""
    try:
        conn = _get_conn()
        conn.execute(
            "UPDATE traces SET ark_decision=?, target_agent=?, route_path=? WHERE trace_id=?",
            (ark_decision, target_agent, route_path, trace_id),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log.warning("update_trace_decision failed: %s", e)


def complete_trace(trace_id: str, reply_summary: str, success: bool = True) -> None:
    """標記 trace 完成（回覆送出後呼叫）。"""
    summary = reply_summary[:80]
    try:
        conn = _get_conn()
        conn.execute(
            "UPDATE traces SET reply_summary=?, success=? WHERE trace_id=?",
            (summary, int(success), trace_id),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log.warning("complete_trace failed: %s", e)


def fail_trace(trace_id: str, reason: str = "timeout") -> None:
    """標記 trace 失敗。"""
    try:
        conn = _get_conn()
        conn.execute(
            "UPDATE traces SET reply_summary=?, success=0 WHERE trace_id=?",
            (reason[:80], trace_id),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        log.warning("fail_trace failed: %s", e)


def get_recent_traces(limit: int = 50) -> list[dict]:
    """取得最近的 traces（API 用）。"""
    try:
        conn = _get_conn()
        cursor = conn.execute(
            "SELECT trace_id, timestamp, user_input_summary, ark_decision, "
            "target_agent, route_path, reply_summary, success "
            "FROM traces ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        columns = [desc[0] for desc in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        log.warning("get_recent_traces failed: %s", e)
        return []


def cleanup_old_traces() -> int:
    """清理超過 RETENTION_DAYS 的 traces。回傳刪除數量。"""
    cutoff = (datetime.now() - timedelta(days=RETENTION_DAYS)).isoformat(timespec="seconds")
    try:
        conn = _get_conn()
        cursor = conn.execute("DELETE FROM traces WHERE timestamp < ?", (cutoff,))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        if deleted > 0:
            log.info("cleanup_old_traces: deleted %d records older than %s", deleted, cutoff)
        return deleted
    except Exception as e:
        log.warning("cleanup_old_traces failed: %s", e)
        return 0
