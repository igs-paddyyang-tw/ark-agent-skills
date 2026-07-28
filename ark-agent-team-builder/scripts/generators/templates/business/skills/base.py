"""BaseSkill 插件系統核心。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SkillType(str, Enum):
    PYTHON = "python"
    LLM = "llm"
    EXTERNAL = "external"


class SkillParam:
    """Skill 輸入參數基底類別（輕量版，不依賴 pydantic）。"""

    @classmethod
    def validate(cls, params: dict) -> bool:
        return True


@dataclass
class SkillResult:
    """Skill 執行結果。"""
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict:
        return {"success": self.success, "data": self.data, "error": self.error}


class BaseSkill(ABC):
    """Skill 基底類別。所有 Skill 必須繼承此類。"""

    skill_id: str = ""
    skill_type: SkillType = SkillType.PYTHON
    description: str = ""
    version: str = "1.0.0"
    input_schema: type[SkillParam] | None = None

    def validate_params(self, params: dict) -> bool:
        """驗證參數。"""
        if not self.input_schema:
            return True
        try:
            return self.input_schema.validate(params)
        except Exception:
            return False

    def to_tool_definition(self) -> dict:
        """產生 tool definition（供 LLM function calling 使用）。"""
        return {
            "skill_id": self.skill_id,
            "description": self.description,
            "version": self.version,
            "type": self.skill_type.value,
        }

    @abstractmethod
    async def execute(self, params: dict) -> SkillResult:
        """執行 Skill。子類必須實作。"""
        ...


__all__ = ["BaseSkill", "SkillParam", "SkillResult", "SkillType"]
