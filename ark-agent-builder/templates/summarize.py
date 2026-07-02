"""SummarizeSkill — 模擬摘要（截斷實作，不呼叫 LLM）。"""
from __future__ import annotations

from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType


class SummarizeParams(SkillParam):
    """summarize 輸入參數。"""
    content: str
    max_length: int = 100


class SummarizeSkill(BaseSkill):
    skill_id = "summarize"
    skill_type = SkillType.PYTHON
    description = "模擬摘要 — 截斷文字前 N 字元"
    version = "1.0.0"
    input_schema = SummarizeParams

    async def execute(self, params: dict) -> SkillResult:
        validated = SummarizeParams(**params)
        text = validated.content
        truncated = text[: validated.max_length]
        if len(text) > validated.max_length:
            truncated += "..."
        return SkillResult(success=True, data={"summary": truncated, "original_length": len(text)})
