"""Echo Skill — 測試用回音。"""
from business.skills.base import BaseSkill, SkillResult, SkillType


class EchoSkill(BaseSkill):
    skill_id = "echo"
    skill_type = SkillType.PYTHON
    description = "回音測試：原樣回傳輸入文字"
    version = "1.0.0"

    async def execute(self, params: dict) -> SkillResult:
        text = params.get("text", "")
        return SkillResult(success=True, data={"echo": text})
