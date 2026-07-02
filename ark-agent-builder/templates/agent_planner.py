"""Planner — 三層意圖路由。

路由策略（按優先順序）：
  1. 關鍵字快速路由（毫秒級，不呼叫 LLM）
  2. Skill 匹配（根據 SkillRegistry 的 description 模糊匹配）
  3. LLM fallback（Gemini 對話）

Workshop 01 教學重點：這就是 Agent「理解意圖」的核心。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class IntentType(StrEnum):
    """意圖分類。"""
    SKILL = "skill"          # 觸發特定 Skill
    WIKI = "wiki"            # 查詢知識庫
    CHAT = "chat"            # LLM 對話
    COMMAND = "command"       # 系統指令


@dataclass
class PlanResult:
    """路由結果。"""
    intent: IntentType
    skill_id: str = ""       # 若 intent=SKILL，指定哪個 skill
    confidence: float = 1.0  # 路由信心（1.0=關鍵字命中，0.5=模糊匹配）
    reason: str = ""


# ── 關鍵字路由表 ──

KEYWORD_ROUTES: dict[str, tuple[IntentType, str]] = {
    # 新聞相關
    "新聞": (IntentType.SKILL, "news"),
    "news": (IntentType.SKILL, "news"),
    "今天新聞": (IntentType.SKILL, "news"),
    "日報": (IntentType.SKILL, "news_renderer"),
    # Wiki 相關
    "wiki": (IntentType.WIKI, ""),
    "知識庫": (IntentType.WIKI, ""),
    "查知識": (IntentType.WIKI, ""),
    # 摘要
    "摘要": (IntentType.SKILL, "summarize"),
    "summarize": (IntentType.SKILL, "summarize"),
    # 翻譯
    "翻譯": (IntentType.SKILL, "translate"),
    "translate": (IntentType.SKILL, "translate"),
}


def route(message: str) -> PlanResult:
    """三層意圖路由。

    Args:
        message: 使用者原始訊息

    Returns:
        PlanResult 包含意圖類型和目標 Skill
    """
    text = message.strip().lower()

    # ── Layer 1: 關鍵字快速路由 ──
    for keyword, (intent, skill_id) in KEYWORD_ROUTES.items():
        if keyword in text:
            return PlanResult(
                intent=intent,
                skill_id=skill_id,
                confidence=1.0,
                reason=f"關鍵字命中: {keyword}",
            )

    # ── Layer 2: Skill description 模糊匹配 ──
    # （可擴充：用 LLM 做意圖分類）
    # 目前跳過，直接到 Layer 3

    # ── Layer 3: LLM 對話 fallback ──
    return PlanResult(
        intent=IntentType.CHAT,
        confidence=0.5,
        reason="無關鍵字命中，fallback 到 LLM 對話",
    )
