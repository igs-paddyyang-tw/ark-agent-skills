"""Memory recall：FTS5 查詢 + 時間衰減排序。"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.memory.indexer import get_connection

log = logging.getLogger(__name__)


@dataclass
class RecallResult:
    """單筆 recall 結果。"""
    agent: str
    source: str
    date: str
    title: str
    body: str
    tags: str
    score: float

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "source": self.source,
            "date": self.date,
            "title": self.title,
            "body": self.body,
            "tags": self.tags,
            "score": round(self.score, 4),
        }


def recall(
    agent: str,
    query: str,
    k: int = 5,
    include_shared: bool = True,
) -> list[RecallResult]:
    """查詢 memory FTS5 索引，回傳 top-k 結果（含時間衰減）。

    Args:
        agent: Agent 名稱（查自己的 + shared）
        query: 查詢字串
        k: 回傳筆數
        include_shared: 是否包含 _shared wiki

    Returns:
        排序後的 RecallResult 列表
    """
    if not query.strip():
        return []

    conn = get_connection()

    # FTS5 MATCH 查詢
    # 同時查自己的記憶和 shared wiki
    agents_filter = f"(agent = '{agent}'"
    if include_shared:
        agents_filter += " OR agent = '_shared'"
    agents_filter += ")"

    try:
        # 使用 bm25() 內建函式取得相關性分數
        sql = f"""
            SELECT agent, source, date, title, body, tags, bm25(mem_fts)
            FROM mem_fts
            WHERE mem_fts MATCH ? AND {agents_filter}
            ORDER BY bm25(mem_fts)
            LIMIT ?
        """
        # FTS5 match query：用空格分隔的關鍵詞（OR 語意）
        fts_query = _build_fts_query(query)
        rows = conn.execute(sql, (fts_query, k * 3)).fetchall()
    except Exception as e:
        log.warning("FTS5 query failed: %s (query=%s)", e, query)
        conn.close()
        return []

    conn.close()

    # 時間衰減重排
    results = []
    now = datetime.now()
    for row in rows:
        agent_name, source, date_str, title, body, tags, bm25_score = row
        # bm25() 回傳負值（越小越相關），取絕對值
        raw_score = abs(bm25_score) if bm25_score else 0.0

        # 時間衰減：score / (1 + days_ago / 30)
        days_ago = _days_since(date_str, now)
        decayed_score = raw_score / (1 + days_ago / 30)

        results.append(RecallResult(
            agent=agent_name,
            source=source,
            date=date_str,
            title=title,
            body=body[:500],  # 截斷回傳
            tags=tags,
            score=decayed_score,
        ))

    # 按衰減後分數排序（降序）
    results.sort(key=lambda r: r.score, reverse=True)
    return results[:k]


def _build_fts_query(query: str) -> str:
    """將使用者查詢轉為 FTS5 MATCH 語法。

    簡單策略：用空格分隔，各 token 之間 OR。
    """
    tokens = query.strip().split()
    if not tokens:
        return query
    # 對每個 token 用引號包起來避免特殊字元問題
    escaped = []
    for t in tokens:
        # 移除 FTS5 特殊字元
        clean = t.replace('"', '').replace("'", "").replace("*", "")
        if clean:
            escaped.append(f'"{clean}"')
    if not escaped:
        return f'"{query}"'
    return " OR ".join(escaped)


def _days_since(date_str: str, now: datetime) -> float:
    """計算日期距今天數。"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return max(0, (now - dt).days)
    except (ValueError, TypeError):
        return 30  # 無法解析時假設 30 天前
