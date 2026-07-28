"""Memory Recall — FTS5 查詢 + 時間衰減排序。"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from coordinator.db.models import get_async_db

log = logging.getLogger("memory.recall")


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


async def recall(
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
        include_shared: 是否包含 _shared 知識

    Returns:
        排序後的 RecallResult 列表
    """
    if not query.strip():
        return []

    conn = await get_async_db()
    try:
        # 組合 agent 篩選條件
        agents = [agent]
        if include_shared:
            agents.append("_shared")
        placeholders = ",".join(["?"] * len(agents))

        # 策略：先嘗試 FTS5 MATCH，失敗則 fallback 到 LIKE
        fts_query = _build_fts_query(query)
        rows = []
        try:
            sql = f"""
                SELECT agent, source, date, title, body, tags, bm25(mem_fts) as score
                FROM mem_fts
                WHERE mem_fts MATCH ? AND agent IN ({placeholders})
                ORDER BY bm25(mem_fts)
                LIMIT ?
            """
            cursor = await conn.execute(sql, (fts_query, *agents, k * 3))
            rows = await cursor.fetchall()
        except Exception:
            pass

        # FTS5 對中文效果不佳時 fallback 到 LIKE 搜尋
        if not rows:
            like_pattern = f"%{query}%"
            sql = f"""
                SELECT agent, source, date, title, body, tags, 1.0 as score
                FROM memory_entries
                WHERE (title LIKE ? OR body LIKE ? OR tags LIKE ?)
                  AND agent IN ({placeholders})
                ORDER BY date DESC
                LIMIT ?
            """
            cursor = await conn.execute(
                sql, (like_pattern, like_pattern, like_pattern, *agents, k * 3)
            )
            rows = await cursor.fetchall()
    except Exception as e:
        log.warning("Memory recall failed: %s (query=%s)", e, query)
        return []
    finally:
        await conn.close()

    # 時間衰減重排
    results: list[RecallResult] = []
    now = datetime.now()

    for row in rows:
        agent_name = row[0]
        source = row[1]
        date_str = row[2]
        title = row[3]
        body = row[4]
        tags = row[5]
        bm25_score = row[6]

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
            body=body[:500],
            tags=tags,
            score=decayed_score,
        ))

    # 按衰減後分數排序（降序）
    results.sort(key=lambda r: r.score, reverse=True)
    return results[:k]


def _build_fts_query(query: str) -> str:
    """將使用者查詢轉為 FTS5 MATCH 語法。

    策略：各 token OR 連接 + 中文 bigram 補充。
    """
    tokens = query.strip().split()
    if not tokens:
        return f'"{query}"'

    escaped: list[str] = []
    for t in tokens:
        # 移除 FTS5 特殊字元
        clean = t.replace('"', "").replace("'", "").replace("*", "").replace("(", "").replace(")", "")
        if clean:
            escaped.append(f'"{clean}"')
        # 中文 bigram 補充
        cjk_chars = [c for c in t if "\u4e00" <= c <= "\u9fff"]
        if len(cjk_chars) >= 2:
            for i in range(len(cjk_chars) - 1):
                bigram = cjk_chars[i] + cjk_chars[i + 1]
                escaped.append(f'"{bigram}"')

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


def _escape(s: str) -> str:
    """簡單 SQL 字串轉義（保留供其他用途）。"""
    return s.replace("'", "''")
