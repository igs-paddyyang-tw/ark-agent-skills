"""ConversationPlanner — 自然語言 → 意圖路由（三層降級）。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class PlanAction(Enum):
    EXECUTE = "execute"   # 執行 Skill
    ANSWER = "answer"     # LLM 回答
    RESET = "reset"       # 重置


@dataclass
class ExecutionPlan:
    action: PlanAction
    skill_id: str = ""
    params: dict = field(default_factory=dict)


# ── keyword 快速路由（毫秒級，不呼叫 LLM）──
_QUICK_ROUTE: list[tuple[list[str], str, dict]] = [
    (["程式", "code", "寫一個", "generate", "codegen"], "llm_cli", {"mode": "codegen"}),
    (["echo", "回音", "測試"], "echo", {}),
]

# 觸發完整 daily 流程的關鍵字（由 handlers 特殊處理）
DAILY_KEYWORDS = ["新聞", "日報", "news", "daily", "科技日報"]


class ConversationPlanner:
    """三層降級意圖路由：keyword → /指令 → LLM 回答。"""

    def __init__(self, skill_ids: list[str] | None = None) -> None:
        self._skill_ids = skill_ids or []

    def set_skills(self, skill_ids: list[str]) -> None:
        self._skill_ids = skill_ids

    async def plan(self, text: str) -> ExecutionPlan:
        """解析意圖，回傳執行計畫。"""
        # 1. /reset
        if re.match(r"^(取消|重來|reset|/reset)$", text.strip(), re.I):
            return ExecutionPlan(action=PlanAction.RESET)

        # 2. /skill_id 指令格式
        cmd = re.match(r"^/(\w+)\s*(.*)", text.strip())
        if cmd and cmd.group(1) in self._skill_ids:
            return ExecutionPlan(
                action=PlanAction.EXECUTE,
                skill_id=cmd.group(1),
                params={"prompt": cmd.group(2).strip()} if cmd.group(2).strip() else {},
            )

        # 3. keyword 快速路由
        lower = text.lower()
        for keywords, skill_id, extra_params in _QUICK_ROUTE:
            if skill_id in self._skill_ids and any(k in lower for k in keywords):
                params = {**extra_params, "prompt": text}
                return ExecutionPlan(action=PlanAction.EXECUTE, skill_id=skill_id, params=params)

        # 4. 預設：Agent CLI 回答
        return ExecutionPlan(action=PlanAction.ANSWER)
