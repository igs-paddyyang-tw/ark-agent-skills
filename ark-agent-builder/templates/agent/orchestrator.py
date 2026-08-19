"""派工引擎（Orchestrator）— 收到任務 → 評估意圖 → 選擇/產出 Skill → 執行 → 回傳結果。

四階段流程：
  Phase 1: evaluate  → 判斷需求（直接回答 / invoke 已有 Skill / 產出新 Skill）
  Phase 2: generate  → 呼叫 LLM 產出新 Skill（動態擴充能力）
  Phase 3: execute   → Hot reload + invoke
  Phase 4: deliver   → 回傳結果

使用方式：
  orchestrator = Orchestrator(registry=skill_registry)
  result = await orchestrator.process("幫我做 X")
"""
from __future__ import annotations

import importlib
import logging
import sys
from typing import Any

from .skill_base import BaseSkill, SkillResult
from .skill_registry import SkillRegistry

log = logging.getLogger(__name__)

# 每個 session 最多自動產出幾個 Skill（防止無限生成）
MAX_SKILL_GEN_PER_SESSION = 3


class Orchestrator:
    """四階段自進化 Agent 流程控制器。

    職責：
    - 收到使用者訊息，判斷應直接回答、呼叫現有 Skill、或產出新 Skill
    - 管理 Skill 生成配額（防止無限 loop）
    - Hot reload 新 Skill 到 registry
    """

    def __init__(self, registry: SkillRegistry) -> None:
        self._registry = registry
        self._gen_count = 0

    async def process(self, user_message: str) -> SkillResult:
        """處理使用者訊息，走完四階段流程。

        回傳 SkillResult，其中 result.data 包含：
          - output: Any          — 最終輸出
          - action: str          — answer / invoke / generate
          - skill_id: str        — 執行的 Skill ID（若有）
          - phases: list[str]    — 完成的階段
        """
        # Phase 1: 評估意圖
        eval_result = await self._evaluate(user_message)
        action = eval_result.get("action", "answer")
        phases: list[str] = ["evaluate"]

        # ── 直接回答 ──
        if action == "answer":
            output = eval_result.get("raw") or await self._direct_answer(user_message)
            return SkillResult(success=True, data={
                "output": output, "action": action, "skill_id": "", "phases": phases,
            })

        # ── 呼叫現有 Skill ──
        if action == "invoke":
            skill_id = eval_result.get("skill_id", "")
            invoke_result = await self._registry.invoke(skill_id, eval_result.get("params", {}))
            phases.append("execute")
            if invoke_result.success:
                return SkillResult(success=True, data={
                    "output": invoke_result.data, "action": action,
                    "skill_id": skill_id, "phases": phases,
                })
            return SkillResult(success=False, error=invoke_result.error, data={
                "action": action, "skill_id": skill_id, "phases": phases,
            })

        # ── 產出新 Skill ──
        if action == "generate":
            if self._gen_count >= MAX_SKILL_GEN_PER_SESSION:
                return SkillResult(
                    success=False,
                    error="本次 session 已產出 %d 個 Skill，達上限" % self._gen_count,
                    data={"action": action, "phases": phases},
                )

            spec = eval_result.get("spec", {})
            skill_id = spec.get("id", "generated_skill")

            gen_result = await self._generate_skill(skill_id, spec.get("description", user_message))
            phases.append("generate")

            if not gen_result.success:
                return SkillResult(success=False, error=gen_result.error,
                                   data={"action": action, "skill_id": skill_id, "phases": phases})
            self._gen_count += 1

            # Phase 3: Hot reload + 執行
            reloaded = self._hot_reload(skill_id)
            if not reloaded:
                return SkillResult(success=False, error="Hot reload 失敗: %s" % skill_id,
                                   data={"action": action, "skill_id": skill_id, "phases": phases})

            invoke_result = await self._registry.invoke(skill_id, spec.get("params", {}))
            phases.append("execute")
            if invoke_result.success:
                return SkillResult(success=True, data={
                    "output": invoke_result.data, "action": action,
                    "skill_id": skill_id, "phases": phases,
                })
            return SkillResult(success=False, error=invoke_result.error,
                               data={"action": action, "skill_id": skill_id, "phases": phases})

        # fallback：未知 action，直接回答
        output = await self._direct_answer(user_message)
        return SkillResult(success=True, data={
            "output": output, "action": "answer", "skill_id": "", "phases": phases,
        })

    # ── 內部方法 ─────────────────────────────────────────

    async def _evaluate(self, message: str) -> dict:
        """Phase 1: 呼叫 LLM evaluate 模式判斷意圖。

        回傳 dict 包含 action（answer/invoke/generate）+ 相關參數。
        """
        llm = self._registry.get("llm_cli")
        if not llm:
            return {"action": "answer", "raw": ""}

        result = await llm.execute({"prompt": message, "mode": "evaluate"})
        if result.success:
            return result.data
        return {"action": "answer", "raw": ""}

    async def _direct_answer(self, message: str) -> str:
        """直接用 LLM chat 模式回答（不走 Skill）。"""
        llm = self._registry.get("llm_cli")
        if not llm:
            return message

        result = await llm.execute({"prompt": message, "mode": "chat"})
        return result.data.get("output", "") if result.success else result.error

    async def _generate_skill(self, skill_id: str, description: str) -> SkillResult:
        """Phase 2: 呼叫 LLM skill_gen 模式產出新 Skill .py 檔。"""
        llm = self._registry.get("llm_cli")
        if not llm:
            return SkillResult(success=False, error="無可用 LLM Skill")

        return await llm.execute({
            "prompt": description,
            "mode": "skill_gen",
            "skill_id": skill_id,
            "output_path": "skills/internal/%s.py" % skill_id,
        })

    def _hot_reload(self, skill_id: str) -> bool:
        """Phase 3: 動態載入新產出的 Skill 到 Registry。

        從 skills.internal 模組載入，找到 BaseSkill 子類並註冊。
        """
        module_name = "skills.internal.%s" % skill_id
        # 清除快取，確保載入最新版本
        if module_name in sys.modules:
            del sys.modules[module_name]
        try:
            mod = importlib.import_module(module_name)
            for attr_name in dir(mod):
                cls = getattr(mod, attr_name)
                if (
                    isinstance(cls, type)
                    and issubclass(cls, BaseSkill)
                    and cls is not BaseSkill
                    and getattr(cls, "skill_id", "")
                ):
                    self._registry.register(cls())
                    log.info("Hot reloaded skill: %s", skill_id)
                    return True
        except Exception as e:
            log.error("Hot reload failed for %s: %s", skill_id, e)
        return False
