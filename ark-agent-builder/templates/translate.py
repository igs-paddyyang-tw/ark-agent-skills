"""TranslateSkill — 模擬翻譯（回傳 mock 結果）。"""
from __future__ import annotations

from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType


class TranslateParams(SkillParam):
    """translate 輸入參數。"""
    text: str
    target_lang: str = "en"


class TranslateSkill(BaseSkill):
    skill_id = "translate"
    skill_type = SkillType.PYTHON
    description = "模擬翻譯 — 回傳 mock 結果"
    version = "1.0.0"
    input_schema = TranslateParams

    async def execute(self, params: dict) -> SkillResult:
        validated = TranslateParams(**params)
        mock_result = f"[{validated.target_lang}] {validated.text}"
        return SkillResult(
            success=True,
            data={"translated": mock_result, "source_lang": "auto", "target_lang": validated.target_lang},
        )
