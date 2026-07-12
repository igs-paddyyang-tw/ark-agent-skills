"""BaseSkill 插件系統。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pydantic import BaseModel


class SkillType(str, Enum):
    PYTHON = "python"
    LLM = "llm"


class SkillParam(BaseModel):
    """Skill 輸入參數基底。"""
    pass


@dataclass
class SkillResult:
    """Skill 執行結果。"""
    success: bool
    data: dict = field(default_factory=dict)
    error: str = ""


class BaseSkill(ABC):
    """Skill 基底類別。所有 Skill 繼承此類。"""
    skill_id: str = ""
    skill_type: SkillType = SkillType.PYTHON
    description: str = ""
    version: str = "1.0.0"
    input_schema: type[SkillParam] | None = None

    def validate_params(self, params: dict) -> bool:
        """驗證參數。無 input_schema 時回傳 True。"""
        if not self.input_schema:
            return True
        try:
            self.input_schema(**params)
            return True
        except Exception:
            return False

    @abstractmethod
    async def execute(self, params: dict) -> SkillResult:
        """執行 Skill。子類別必須實作。"""
        ...
