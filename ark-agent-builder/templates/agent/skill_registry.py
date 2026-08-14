"""Skill Registry — 管理所有已註冊的 Skill。"""
from __future__ import annotations

import logging
from typing import Any

from .skill_base import BaseSkill, SkillResult

log = logging.getLogger(__name__)


class SkillRegistry:
    """Skill 註冊中心。支援手動註冊與 auto-discover。"""

    def __init__(self) -> None:
        self._skills: dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        """註冊一個 Skill 實例。"""
        self._skills[skill.skill_id] = skill
        log.info("Registered skill: %s", skill.skill_id)

    def get(self, skill_id: str) -> BaseSkill | None:
        """取得 Skill。"""
        return self._skills.get(skill_id)

    def list_skills(self) -> list[str]:
        """列出所有已註冊的 Skill ID。"""
        return list(self._skills.keys())

    async def invoke(self, skill_id: str, params: dict) -> SkillResult:
        """呼叫指定 Skill。"""
        skill = self.get(skill_id)
        if not skill:
            return SkillResult(success=False, error=f"Skill not found: {skill_id}")
        if not skill.validate_params(params):
            return SkillResult(success=False, error=f"Invalid params for {skill_id}")
        try:
            return await skill.execute(params)
        except Exception as e:
            log.error("Skill %s execution failed: %s", skill_id, e)
            return SkillResult(success=False, error=str(e))
