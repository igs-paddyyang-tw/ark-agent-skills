"""Tool: dispatch_to_agent — 將任務派給專業 Agent 處理。"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


async def handle_dispatch_to_agent(args: dict) -> str:
    """派工給指定 Agent，回傳結果或確認。"""
    target_agent = args.get("target_agent", "").strip()
    task_description = args.get("task_description", "").strip()
    priority = args.get("priority", "normal")

    if not target_agent:
        return "Error: target_agent 不能為空"
    if not task_description:
        return "Error: task_description 不能為空"

    log.info("dispatch_to_agent: target=%s priority=%s task=%s",
             target_agent, priority, task_description[:80])

    # 嘗試透過 Agent CLI 送出任務
    try:
        from src.agent.cli import is_cli_available, agent_cli_chat

        if is_cli_available():
            # agent_cli_chat 的 agent_id 不含 "-agent" 後綴
            agent_id = target_agent.replace("-agent", "")
            result = await agent_cli_chat(task_description, agent_id=agent_id)
            if result:
                log.info("dispatch_to_agent: %s replied (%d chars)", target_agent, len(result))
                return f"✅ {target_agent} 回覆：\n\n{result}"
            else:
                return f"⚠️ {target_agent} 無回應（可能超時），任務已送出但未收到結果。"
        else:
            # CLI 不可用 → fallback Gemini（用對應 Agent 的 SOUL 作為 system prompt）
            from pathlib import Path
            from src.llm.chat import simple_chat

            agent_id = target_agent.replace("-agent", "")
            soul_path = Path(f"agents/{target_agent}/.kiro/steering/SOUL.md")
            if not soul_path.exists():
                soul_path = Path(f"agents/{agent_id}-agent/.kiro/steering/SOUL.md")

            soul = ""
            if soul_path.exists():
                soul = soul_path.read_text(encoding="utf-8")

            system = f"{soul}\n\n## 任務\n你收到一個派工任務，請完成後回報結果。"
            result = await simple_chat(task_description, system=system)

            if result:
                log.info("dispatch_to_agent (fallback): %s replied (%d chars)", target_agent, len(result))
                return f"✅ {target_agent}（Gemini fallback）回覆：\n\n{result}"
            else:
                return f"❌ {target_agent} 不可用（CLI 未安裝，Gemini fallback 也失敗）"

    except Exception as e:
        log.error("dispatch_to_agent failed: %s", e)
        return f"❌ 派工失敗：{e}"


def register_tools():
    from src.llm.tool_registry import Tool, registry
    from src.agent.cli import get_dispatchable_agents

    # 動態從 agents.yaml 取得可派工的 agent 列表
    dispatchable = get_dispatchable_agents()
    if not dispatchable:
        # fallback 硬編碼（agents.yaml 不存在時）
        dispatchable = [
            "coder-agent", "ai-dev-agent", "data-agent",
            "market-agent", "report-agent", "qa-agent", "admin-agent",
        ]

    registry.register(Tool(
        name="dispatch_to_agent",
        description=(
            "將任務派給專業 Agent 處理。用於需要特定領域專業知識的任務。"
            "簡單問答/聊天/查知識庫 → 你直接回覆，不要派工。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "target_agent": {
                    "type": "string",
                    "enum": dispatchable,
                    "description": "目標 Agent ID",
                },
                "task_description": {
                    "type": "string",
                    "description": "任務描述（含使用者原始需求 + 你的分析）",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "normal", "high"],
                    "description": "優先級（預設 normal）",
                },
            },
            "required": ["target_agent", "task_description"],
        },
        handler=handle_dispatch_to_agent,
    ))
