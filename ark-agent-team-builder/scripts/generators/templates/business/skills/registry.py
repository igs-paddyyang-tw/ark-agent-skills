"""SkillRegistry — 註冊、查詢、執行 Skills。"""
from __future__ import annotations

import importlib
import logging
import pkgutil
import sys
import time
from typing import TYPE_CHECKING

from .base import BaseSkill, SkillResult

if TYPE_CHECKING:
    from .tracker import SkillTracker

log = logging.getLogger("skills.registry")


class SkillRegistry:
    """Skill 註冊表：auto_discover + invoke + hot_reload。"""

    def __init__(self, tracker: "SkillTracker | None" = None) -> None:
        self._skills: dict[str, BaseSkill] = {}
        self._tracker = tracker

    @property
    def tracker(self) -> "SkillTracker | None":
        return self._tracker

    @tracker.setter
    def tracker(self, t: "SkillTracker") -> None:
        self._tracker = t

    def register(self, skill: BaseSkill) -> None:
        """註冊一個 Skill。"""
        self._skills[skill.skill_id] = skill
        log.debug("Registered skill: %s (v%s)", skill.skill_id, skill.version)

    def get(self, skill_id: str) -> BaseSkill | None:
        """取得 Skill（不存在回 None）。"""
        return self._skills.get(skill_id)

    def list_skills(self) -> list[dict]:
        """列出所有已註冊 Skill。"""
        return [
            {
                "skill_id": s.skill_id,
                "description": s.description,
                "version": s.version,
                "type": s.skill_type.value,
            }
            for s in self._skills.values()
        ]

    async def invoke(self, skill_id: str, params: dict, agent: str = "system") -> SkillResult:
        """執行 Skill，統一錯誤處理 + 統計。"""
        skill = self.get(skill_id)
        if not skill:
            return SkillResult(success=False, error=f"Skill not found: {skill_id}")
        if not skill.validate_params(params):
            return SkillResult(success=False, error=f"Invalid params for: {skill_id}")

        start = time.monotonic()
        try:
            result = await skill.execute(params)
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            if self._tracker:
                await self._tracker.record(skill_id, agent, success=False, duration_ms=duration_ms)
            return SkillResult(success=False, error=str(e))

        duration_ms = int((time.monotonic() - start) * 1000)
        if self._tracker:
            await self._tracker.record(skill_id, agent, success=result.success, duration_ms=duration_ms)
        return result

    def auto_discover(self, package_name: str) -> int:
        """掃描套件下所有 BaseSkill 子類別並註冊。

        Args:
            package_name: 如 "business.skills.internal"

        Returns:
            新註冊的 Skill 數量
        """
        count = 0
        try:
            pkg = importlib.import_module(package_name)
        except ImportError as e:
            log.warning("Cannot import package %s: %s", package_name, e)
            return 0

        for _, module_name, _ in pkgutil.iter_modules(pkg.__path__):
            try:
                mod = importlib.import_module(f"{package_name}.{module_name}")
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BaseSkill)
                        and attr is not BaseSkill
                        and getattr(attr, "skill_id", "")
                    ):
                        self.register(attr())
                        count += 1
            except Exception as e:
                log.warning("Failed to load skill module %s: %s", module_name, e)

        log.info("Auto-discovered %d skills from %s", count, package_name)
        return count

    def hot_reload(self, skill_id: str) -> bool:
        """動態重新載入指定 Skill。"""
        module_name = f"business.skills.internal.{skill_id}"
        if module_name in sys.modules:
            del sys.modules[module_name]
        try:
            mod = importlib.import_module(module_name)
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseSkill)
                    and attr is not BaseSkill
                    and getattr(attr, "skill_id", "")
                ):
                    self.register(attr())
                    return True
        except Exception as e:
            log.warning("Hot reload failed for %s: %s", skill_id, e)
        return False
