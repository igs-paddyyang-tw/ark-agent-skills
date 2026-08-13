"""超時催促 / 自省引擎（Nudge）— 定期分析近期活動，產出行動建議。

排程觸發後分析最近 N 小時的對話記錄，判斷：
  1. 重複需求但沒有對應 Skill → CREATE_SKILL
  2. 新的使用者偏好 → UPDATE_MEMORY
  3. 持續失敗的 Skill → EVOLVE_SKILL
  4. 無需行動 → NOOP

使用方式：
  nudge = Nudge(memory_search, memory_store, skill_tracker, registry, llm)
  actions = await nudge.run()
  results = await nudge.execute_actions(actions)
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

log = logging.getLogger(__name__)


# ── 依賴介面（Protocol）─────────────────────────────────────
# 使用 Protocol 解耦，實作者自行注入具體類別。


class MemorySearchProtocol(Protocol):
    """對話記錄搜尋介面。"""
    def search_recent(self, hours: int = 24, limit: int = 50) -> list[dict]: ...


class MemoryStoreProtocol(Protocol):
    """使用者記憶寫入介面。"""
    def write(self, user_id: int, key: str, value: str) -> None: ...


class SkillTrackerProtocol(Protocol):
    """Skill 追蹤介面。"""
    def get_evolution_candidates(self) -> list[Any]: ...
    def mark_evolved(self, skill_id: str) -> None: ...


class SkillRegistryProtocol(Protocol):
    """Skill 列表查詢介面。"""
    def list_skills(self) -> list[dict]: ...


class LLMProtocol(Protocol):
    """LLM 呼叫介面。"""
    async def generate(self, prompt: str, system: str = "") -> str: ...


# ── 行動類型 ──────────────────────────────────────────────


class NudgeActionType(Enum):
    """Nudge 產出的行動類型。"""
    CREATE_SKILL = "create_skill"
    UPDATE_MEMORY = "update_memory"
    EVOLVE_SKILL = "evolve_skill"
    NOOP = "noop"


@dataclass
class NudgeAction:
    """Nudge 產出的單一行動。"""
    type: NudgeActionType
    skill_id: str = ""
    description: str = ""
    user_id: int = 0
    key: str = ""
    value: str = ""
    reason: str = ""


# ── Prompt 模板 ───────────────────────────────────────────

ANALYZE_PROMPT = """你是 AI Agent 的自省模組。分析以下資訊後，判斷需要什麼行動。

## 近期對話摘要
{conversations}

## 持續失敗的 Skills
{failing_skills}

## 目前已有的 Skills
{existing_skills}

## 判斷規則（JSON 陣列格式回傳）：

1. 重複問類似問題但沒有對應 Skill？
   → {{"type": "create_skill", "skill_id": "xxx", "description": "一句話描述"}}

2. 偵測到新的使用者偏好？
   → {{"type": "update_memory", "user_id": 123, "key": "偏好欄位", "value": "值"}}

3. 持續失敗的 Skill 需要改進？
   → {{"type": "evolve_skill", "skill_id": "xxx", "reason": "改進原因"}}

4. 沒有需要行動
   → {{"type": "noop"}}

只回傳 JSON 陣列，不要其他文字。
"""


# ── 主類別 ────────────────────────────────────────────────


class Nudge:
    """定時自省引擎：分析近期活動，產出行動建議。

    設計為可獨立排程執行：
      actions = await nudge.run()          # 分析
      results = await nudge.execute_actions(actions)  # 執行
    """

    def __init__(
        self,
        memory_search: MemorySearchProtocol,
        memory_store: MemoryStoreProtocol,
        skill_tracker: SkillTrackerProtocol,
        registry: SkillRegistryProtocol,
        llm: LLMProtocol,
    ) -> None:
        self._search = memory_search
        self._memory = memory_store
        self._tracker = skill_tracker
        self._registry = registry
        self._llm = llm
        self._last_run: float = 0

    async def run(self, hours: int = 24) -> list[NudgeAction]:
        """執行自省流程，回傳行動清單。

        Args:
            hours: 分析最近幾小時的活動（預設 24）
        """
        self._last_run = time.time()

        # 1. 取得近期對話
        conversations = self._search.search_recent(hours=hours)
        if not conversations:
            log.info("Nudge: 近 %dh 無對話，跳過", hours)
            return [NudgeAction(type=NudgeActionType.NOOP)]

        conversations_text = "\n".join(
            f"- ({r.get('role', '?')}) {str(r.get('content', ''))[:150]}"
            for r in conversations[:30]
        )

        # 2. 取得失敗 Skill 清單
        failing = self._tracker.get_evolution_candidates()
        failing_text = "\n".join(
            f"- {getattr(s, 'skill_id', '?')}：連續失敗 {getattr(s, 'consecutive_fails', 0)} 次"
            for s in failing
        ) or "（無）"

        # 3. 現有 Skills
        existing = ", ".join(s.get("id", "") for s in self._registry.list_skills())

        # 4. 送 LLM 分析
        prompt = ANALYZE_PROMPT.format(
            conversations=conversations_text,
            failing_skills=failing_text,
            existing_skills=existing,
        )
        result_text = await self._llm.generate(prompt=prompt, system="你是 JSON 分析助手，只回傳有效 JSON。")

        # 5. 解析行動
        actions = self._parse_actions(result_text)
        log.info("Nudge 分析完成，產出 %d 個行動", len(actions))
        return actions

    async def execute_actions(self, actions: list[NudgeAction]) -> list[str]:
        """執行行動清單，回傳結果摘要字串。

        注意：CREATE_SKILL / EVOLVE_SKILL 需要搭配 Orchestrator 使用，
        此處僅處理 UPDATE_MEMORY，其他行動回傳建議字串。
        """
        results: list[str] = []

        for action in actions:
            if action.type == NudgeActionType.NOOP:
                continue
            elif action.type == NudgeActionType.UPDATE_MEMORY:
                if action.user_id and action.key and action.value:
                    self._memory.write(action.user_id, action.key, action.value)
                    results.append(f"✅ 更新記憶: {action.key}={action.value}")
            elif action.type == NudgeActionType.CREATE_SKILL:
                results.append(f"📝 建議建立 Skill: {action.skill_id} — {action.description}")
            elif action.type == NudgeActionType.EVOLVE_SKILL:
                self._tracker.mark_evolved(action.skill_id)
                results.append(f"📝 建議改進 Skill: {action.skill_id} — {action.reason}")

        return results or ["✅ 無需行動"]

    # ── 解析輔助 ─────────────────────────────────────────

    def _parse_actions(self, text: str) -> list[NudgeAction]:
        """解析 LLM 回傳的 JSON 行動清單。"""
        text = text.strip()
        # 移除 code block 包裹
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(l for l in lines if not l.startswith("```"))

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # 嘗試找 [ ... ] 範圍
            start = text.find("[")
            end = text.rfind("]")
            if start != -1 and end != -1:
                try:
                    data = json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    log.warning("Nudge 解析失敗: %s", text[:200])
                    return [NudgeAction(type=NudgeActionType.NOOP)]
            else:
                return [NudgeAction(type=NudgeActionType.NOOP)]

        if not isinstance(data, list):
            data = [data]

        actions: list[NudgeAction] = []
        for item in data:
            action_type = item.get("type", "noop")
            try:
                nt = NudgeActionType(action_type)
            except ValueError:
                nt = NudgeActionType.NOOP

            actions.append(NudgeAction(
                type=nt,
                skill_id=item.get("skill_id", ""),
                description=item.get("description", ""),
                user_id=item.get("user_id", 0),
                key=item.get("key", ""),
                value=item.get("value", ""),
                reason=item.get("reason", ""),
            ))

        return actions or [NudgeAction(type=NudgeActionType.NOOP)]
