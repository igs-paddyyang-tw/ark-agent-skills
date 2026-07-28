"""News Scraper Skill — 從多來源抓取科技新聞。"""
from business.skills.base import BaseSkill, SkillResult, SkillType


class NewsScraperSkill(BaseSkill):
    skill_id = "news_scraper"
    skill_type = SkillType.PYTHON
    description = "從設定的來源抓取科技新聞"
    version = "1.0.0"

    async def execute(self, params: dict) -> SkillResult:
        limit = params.get("limit", 10)
        config_path = params.get("config_path", "config/news_sources.yaml")

        try:
            from business.news_scraper import scrape_news
            articles = await scrape_news(config_path=config_path, limit=limit)
            return SkillResult(success=True, data={"articles": articles, "count": len(articles)})
        except Exception as e:
            return SkillResult(success=False, error=str(e))
