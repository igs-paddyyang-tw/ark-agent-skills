"""Wiki Query Skill — 知識庫查詢。"""
from business.skills.base import BaseSkill, SkillResult, SkillType


class WikiQuerySkill(BaseSkill):
    skill_id = "wiki_query"
    skill_type = SkillType.PYTHON
    description = "查詢知識庫（四層搜尋）"
    version = "2.0.0"

    async def execute(self, params: dict) -> SkillResult:
        query = params.get("q", params.get("query", ""))
        if not query:
            return SkillResult(success=False, error="Missing query parameter 'q'")

        agent_id = params.get("agent_id")
        use_rag = params.get("use_rag", False)

        try:
            from coordinator.wiki.engine import WikiEngine
            engine = WikiEngine(agent_id=agent_id)
            result = await engine.query(query, use_rag=use_rag)
            return SkillResult(success=True, data=result)
        except ImportError:
            # WikiEngine 尚未安裝時 fallback
            return SkillResult(success=False, error="WikiEngine not available yet")
        except Exception as e:
            return SkillResult(success=False, error=str(e))
