"""Skill 自動推薦：任務結束後評估是否觸發 Skill 提案。"""
from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]

# 觸發門檻
MIN_TOOL_CALLS = 5


def should_recommend(
    tool_call_count: int,
    non_trivial: bool = False,
) -> bool:
    """評估是否應觸發 Skill 推薦。

    條件（滿足其一）：
    1. tool_call_count >= MIN_TOOL_CALLS
    2. non_trivial 標記為 True
    """
    if tool_call_count >= MIN_TOOL_CALLS:
        return True
    if non_trivial:
        return True
    return False


async def recommend_skill(
    agent_name: str,
    task_id: str,
    conversation: str,
    tool_call_count: int,
    non_trivial: bool = False,
    bot=None,
    admin_chat_id: int | None = None,
) -> dict | None:
    """完整推薦流程：評估 → 生成草稿 → 建立提案 → TG 推送。

    背景執行，不阻塞主回覆。回傳 proposal dict 或 None。
    """
    if not should_recommend(tool_call_count, non_trivial):
        return None

    log.info(
        "Skill recommend triggered for %s (calls=%d, non_trivial=%s)",
        agent_name, tool_call_count, non_trivial,
    )

    try:
        # 1. 生成草稿
        draft = await _generate_draft(agent_name, task_id, conversation)
        if not draft:
            log.info("Draft generation returned empty, skipping")
            return None

        # 2. 解析草稿
        skill_name = _extract_skill_name(draft) or f"ark-auto-{task_id[:8]}"
        gist = _extract_gist(draft) or f"自動沉澱自任務 {task_id}"

        # 3. 建立提案
        from src.memory.skill_manage import create_proposal
        proposal = create_proposal(
            agent=agent_name,
            skill_name=skill_name,
            skill_content=draft,
            gist=gist,
            source_task=task_id,
        )

        # 4. TG 推送審批卡片（如果有 bot instance）
        if bot and admin_chat_id:
            try:
                from src.memory.tg_handlers import send_approval_card
                await send_approval_card(bot, proposal, admin_chat_id)
            except Exception as e:
                log.warning("Failed to send approval card: %s", e)

        return proposal

    except Exception as e:
        log.error("Skill recommend failed for %s: %s", agent_name, e)
        return None


# ─── 草稿生成 ───

_DRAFT_PROMPT = """\
你是 Skill 沉澱專家。根據以下任務軌跡，判斷是否有可重用的流程。

規則：
1. 先判斷「可重用流程 vs 一次性任務」——後者輸出 SKIP（只輸出這五個字元）
2. 可重用時，產出 SKILL.md 格式的草稿
3. 步驟保留實際指令，不過度抽象化
4. Edge cases 只寫真實遇到的
5. description 用「推銷式」寫法：講做什麼 + 何時觸發 + 含具體關鍵詞

SKILL.md 格式：
```
---
name: ark-{kebab-case-name}
description: |
  {推銷式描述，60 字以內}
version: 0.1.0
metadata:
  ark:
    origin: auto
    scope: private
    source_task: {task_id}
---

# {標題}

## 何時不要用
（反向邊界）

## 步驟
1. ...

## Edge Cases
- ...

## 驗證
- ...
```

任務軌跡：
- Agent: {agent}
- Task ID: {task_id}
- 對話摘要：
{conversation}

請輸出 SKILL.md 草稿（或 SKIP）：
"""


async def _generate_draft(agent_name: str, task_id: str, conversation: str) -> str | None:
    """使用 LLM 生成 Skill 草稿。"""
    try:
        from src.llm.chat import simple_chat

        prompt = _DRAFT_PROMPT.format(
            agent=agent_name,
            task_id=task_id,
            conversation=conversation[:4000],
        )

        result = await simple_chat(
            prompt=prompt,
            system="你是 Skill 沉澱專家，只輸出 SKILL.md 草稿或 SKIP。不加任何其他說明。",
        )

        if not result:
            return None

        result = result.strip()

        # 如果是 SKIP 或太短
        if result == "SKIP" or len(result) < 50:
            log.info("LLM decided SKIP for %s/%s", agent_name, task_id)
            return None

        # 清理 markdown code block wrapper
        if result.startswith("```"):
            result = re.sub(r"^```\w*\n?", "", result)
            result = re.sub(r"\n?```$", "", result)

        return result

    except Exception as e:
        log.warning("Draft generation failed: %s", e)
        return None


def _extract_skill_name(draft: str) -> str | None:
    """從草稿 frontmatter 提取 skill name。"""
    match = re.search(r"^name:\s*(.+)", draft, re.MULTILINE)
    if match:
        return match.group(1).strip().strip("\"'")
    return None


def _extract_gist(draft: str) -> str | None:
    """從草稿 description 提取 gist（前 60 字）。"""
    match = re.search(r"^description:\s*\|?\s*\n?\s*(.+)", draft, re.MULTILINE)
    if match:
        desc = match.group(1).strip().strip("\"'")
        return desc[:60]
    return None
