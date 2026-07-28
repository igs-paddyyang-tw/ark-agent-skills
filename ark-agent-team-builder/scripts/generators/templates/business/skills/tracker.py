"""SkillTracker — 呼叫統計 + 演化偵測。"""
from __future__ import annotations

import logging
from coordinator.db.models import get_async_db, fetch_all, now_iso

log = logging.getLogger("skills.tracker")


class SkillTracker:
    """記錄每次 Skill 呼叫，提供統計與演化判斷。"""

    async def record(
        self,
        skill_id: str,
        agent: str = "system",
        success: bool = True,
        duration_ms: int = 0,
        params_hash: str = "",
    ) -> None:
        """記錄一次呼叫。"""
        conn = await get_async_db()
        try:
            await conn.execute(
                """INSERT INTO skill_calls (skill_id, agent, success, duration_ms, params_hash, called_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (skill_id, agent, int(success), duration_ms, params_hash, now_iso()),
            )
            await conn.commit()
        except Exception as e:
            log.warning("Failed to record skill call: %s", e)
        finally:
            await conn.close()

    async def get_stats(self, skill_id: str | None = None) -> list[dict]:
        """取得 Skill 統計。

        Args:
            skill_id: 指定 Skill（None = 全部）

        Returns:
            [{skill_id, call_count, success_count, avg_duration_ms, last_called}]
        """
        conn = await get_async_db()
        try:
            if skill_id:
                sql = """
                    SELECT skill_id,
                           COUNT(*) as call_count,
                           SUM(success) as success_count,
                           AVG(duration_ms) as avg_duration_ms,
                           MAX(called_at) as last_called
                    FROM skill_calls
                    WHERE skill_id = ?
                    GROUP BY skill_id
                """
                rows = await fetch_all(conn, sql, (skill_id,))
            else:
                sql = """
                    SELECT skill_id,
                           COUNT(*) as call_count,
                           SUM(success) as success_count,
                           AVG(duration_ms) as avg_duration_ms,
                           MAX(called_at) as last_called
                    FROM skill_calls
                    GROUP BY skill_id
                    ORDER BY call_count DESC
                """
                rows = await fetch_all(conn, sql)
        finally:
            await conn.close()

        return [
            {
                "skill_id": r["skill_id"],
                "call_count": r["call_count"],
                "success_count": r["success_count"] or 0,
                "success_rate": round((r["success_count"] or 0) / r["call_count"], 2) if r["call_count"] else 0,
                "avg_duration_ms": round(r["avg_duration_ms"] or 0),
                "last_called": r["last_called"],
            }
            for r in rows
        ]

    async def needs_evolution(self, skill_id: str, threshold: int = 50) -> bool:
        """判斷 Skill 是否需要演化（呼叫 ≥ threshold 且成功率 < 80%）。"""
        stats = await self.get_stats(skill_id)
        if not stats:
            return False
        s = stats[0]
        return s["call_count"] >= threshold and s["success_rate"] < 0.8
