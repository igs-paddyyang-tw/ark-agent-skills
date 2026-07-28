"""News Renderer Skill — 渲染新聞為 HTML 日報。"""
from business.skills.base import BaseSkill, SkillResult, SkillType


class NewsRendererSkill(BaseSkill):
    skill_id = "news_renderer"
    skill_type = SkillType.PYTHON
    description = "將新聞列表渲染為 HTML 日報"
    version = "1.0.0"

    async def execute(self, params: dict) -> SkillResult:
        articles = params.get("articles", [])
        output_path = params.get("output_path", "")

        if not articles:
            return SkillResult(success=False, error="No articles provided")

        try:
            from business.news_renderer import render_daily
            path = await render_daily(articles, output_path=output_path)
            return SkillResult(success=True, data={"output": path})
        except Exception as e:
            return SkillResult(success=False, error=str(e))
