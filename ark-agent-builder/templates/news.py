"""新聞爬蟲 Skill — 抓取 Hacker News 首頁標題。

科技日報貫穿案例的起點：
  01: 此 Skill 手動觸發
  02: 由 market-agent 調用
  04: 用 Spec-Driven 重構
  05: 產出結果 ingest 到 Wiki
"""
from __future__ import annotations

from typing import Any

import httpx
from pydantic import Field

from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType


class NewsParams(SkillParam):
    """新聞爬蟲參數。"""

    max_items: int = Field(default=5, description="最多抓取幾則新聞")
    source: str = Field(default="hackernews", description="新聞來源 (hackernews)")


class NewsSkill(BaseSkill):
    """抓取 Hacker News 首頁新聞標題與連結。"""

    skill_id = "news"
    skill_type = SkillType.PYTHON
    description = "科技新聞爬蟲 — 抓取 Hacker News 首頁標題"
    version = "1.0.0"
    input_schema = NewsParams

    async def execute(self, params: dict) -> SkillResult:
        validated = NewsParams(**params)

        try:
            articles = await self._fetch_hackernews(validated.max_items)
            return SkillResult(
                success=True,
                data={
                    "source": "Hacker News",
                    "count": len(articles),
                    "articles": articles,
                },
            )
        except Exception as e:
            return SkillResult(success=False, error=f"爬取失敗: {e}")

    async def _fetch_hackernews(self, max_items: int) -> list[dict[str, Any]]:
        """使用 HN API 抓取首頁新聞。"""
        async with httpx.AsyncClient(timeout=10) as client:
            # Hacker News 官方 API：取得首頁 story IDs
            resp = await client.get(
                "https://hacker-news.firebaseio.com/v0/topstories.json"
            )
            resp.raise_for_status()
            story_ids: list[int] = resp.json()[:max_items]

            # 批次取得每則新聞的詳情
            articles: list[dict[str, Any]] = []
            for story_id in story_ids:
                detail_resp = await client.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                )
                if detail_resp.status_code == 200:
                    item = detail_resp.json()
                    if item and item.get("title"):
                        articles.append(
                            {
                                "title": item["title"],
                                "url": item.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                                "score": item.get("score", 0),
                            }
                        )

            return articles
