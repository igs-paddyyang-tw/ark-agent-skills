"""SkillRegistry — 註冊、查詢、執行 Skills。"""
from __future__ import annotations

import importlib
import logging
import pkgutil
import sys
from src.skills.base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Skill 註冊表：auto_discover + invoke + hot_reload。"""

    def __init__(self) -> None:
        self._skills: dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        self._skills[skill.skill_id] = skill

    def get(self, skill_id: str) -> BaseSkill | None:
        return self._skills.get(skill_id)

    def list_skills(self) -> list[dict]:
        return [{"id": s.skill_id, "description": s.description} for s in self._skills.values()]

    async def invoke(self, skill_id: str, params: dict) -> SkillResult:
        """執行 Skill，統一錯誤處理。"""
        skill = self.get(skill_id)
        if not skill:
            return SkillResult(success=False, error=f"Skill not found: {skill_id}")
        if not skill.validate_params(params):
            return SkillResult(success=False, error=f"Invalid params: {skill_id}")
        try:
            return await skill.execute(params)
        except Exception as e:
            return SkillResult(success=False, error=str(e))

    def auto_discover(self, package_name: str) -> int:
        """掃描套件下所有 BaseSkill 子類別並註冊。"""
        count = 0
        try:
            pkg = importlib.import_module(package_name)
        except ImportError:
            return 0
        for _, module_name, _ in pkgutil.iter_modules(pkg.__path__):
            try:
                mod = importlib.import_module(f"{package_name}.{module_name}")
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if (isinstance(attr, type) and issubclass(attr, BaseSkill)
                            and attr is not BaseSkill and attr.skill_id):
                        self.register(attr())
                        count += 1
            except Exception as e:
                logger.warning("載入 %s 失敗: %s", module_name, e)
        return count

    def hot_reload(self, skill_id: str) -> bool:
        """動態重新載入指定 Skill。"""
        module_name = f"src.skills.internal.{skill_id}"
        if module_name in sys.modules:
            del sys.modules[module_name]
        try:
            mod = importlib.import_module(module_name)
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if (isinstance(attr, type) and issubclass(attr, BaseSkill)
                        and attr is not BaseSkill and attr.skill_id):
                    self.register(attr())
                    return True
        except Exception:
            pass
        return False
