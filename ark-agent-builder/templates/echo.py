"""echo — 回聲測試 Skill（驗證系統運作）。"""
from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType


class EchoParams(SkillParam):
    """echo 輸入參數。"""
    message: str = "Hello"


class EchoSkill(BaseSkill):
    skill_id = "echo"
    skill_type = SkillType.PYTHON
    description = "回聲測試 — 回傳輸入訊息"
    version = "1.0.0"
    input_schema = EchoParams

    async def execute(self, params: dict) -> SkillResult:
        p = EchoParams(**params)
        return SkillResult(success=True, data={"echo": p.message})
