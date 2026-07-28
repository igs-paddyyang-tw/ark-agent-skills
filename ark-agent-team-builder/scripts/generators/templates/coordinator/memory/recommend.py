"""Memory Recommend — 根據歷史記憶推薦相關 Skill。"""
from __future__ import annotations

import logging
from coordinator.db.models import get_async_db, fetch_all

log = logging.getLogger("memory.recommend")


async def recommend_skills(
    agent: str,
    context: str,
    k: int = 3,
) -> list[dict]:
    """根據當前 context 與歷史 skill_calls 推薦可能相關的 Skill。

    策略：
    1. 從 skill_calls 表找該 agent 最常用且成功率高的 Skill
    2. 比對 context 中的關鍵詞與 Skill tags

    Args:
        agent: Agent 名稱
        context: 當前任務描述
        k: 回傳筆數

    Returns:
        [{skill_id, call_count, success_rate, reason}]
    """
    conn = await get_async_db()
    try:
        # 查詢該 agent 的 Skill 使用統計
        rows = await fetch_all(
            conn,
            """SELECT skill_id,
                      COUNT(*) as call_count,
                      SUM(success) as success_count
               FROM skill_calls
               WHERE agent = ?
               GROUP BY skill_id
               ORDER BY call_count DESC
               LIMIT ?""",
            (agent, k * 2),
        )
    except Exception:
        # skill_calls 表可能還不存在
        return []
    finally:
        await conn.close()

    if not rows:
        return []

    # 計算推薦分數
    context_lower = context.lower()
    results: list[dict] = []

    for row in rows:
        skill_id = row["skill_id"]
        call_count = row["call_count"]
        success_count = row["success_count"] or 0
        success_rate = success_count / call_count if call_count > 0 else 0

        # 過濾成功率太低的
        if success_rate < 0.5 and call_count > 2:
            continue

        # 簡單關鍵詞比對加分
        relevance = 0.0
        skill_words = skill_id.replace("_", " ").split()
        for word in skill_words:
            if word in context_lower:
                relevance += 1.0

        results.append({
            "skill_id": skill_id,
            "call_count": call_count,
            "success_rate": round(success_rate, 2),
            "relevance": relevance,
            "reason": f"已使用 {call_count} 次，成功率 {success_rate:.0%}",
        })

    # 按 relevance + 使用頻率排序
    results.sort(key=lambda r: (r["relevance"], r["call_count"]), reverse=True)
    return results[:k]
