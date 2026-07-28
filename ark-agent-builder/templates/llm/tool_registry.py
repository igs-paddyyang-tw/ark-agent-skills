"""Tool Registry：註冊、dispatch、schema 生成。"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

log = logging.getLogger(__name__)


@dataclass
class Tool:
    """單一 Tool 定義。"""
    name: str
    description: str
    parameters: dict  # JSON Schema（Gemini function_declarations 格式）
    handler: Callable  # async def handler(args: dict) -> str
    requires_approval: bool = False

    def to_schema(self) -> dict:
        """轉換為 LLM function declaration 格式（統一格式）。"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class ToolRegistry:
    """Tool 註冊與 dispatch。"""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """註冊一個 Tool。"""
        self._tools[tool.name] = tool
        log.debug("Tool registered: %s", tool.name)

    def get(self, name: str) -> Tool | None:
        """取得指定 Tool。"""
        return self._tools.get(name)

    def all_schemas(self) -> list[dict]:
        """回傳所有 Tool 的 function declaration schema。"""
        return [t.to_schema() for t in self._tools.values()]

    def all_names(self) -> list[str]:
        """回傳所有 Tool 名稱。"""
        return list(self._tools.keys())

    def list_descriptions(self) -> str:
        """回傳所有 Tool 的 name + description（用於 system prompt）。"""
        lines = []
        for t in self._tools.values():
            lines.append(f"- {t.name}: {t.description}")
        return "\n".join(lines)

    async def dispatch(self, name: str, args: dict) -> str:
        """Dispatch tool call → 執行 handler → 回傳結果字串。"""
        tool = self._tools.get(name)
        if not tool:
            return f"Error: Tool '{name}' not found. Available: {self.all_names()}"

        try:
            result = await tool.handler(args)
            log.info("Tool %s executed successfully", name)
            return result
        except Exception as e:
            log.error("Tool %s failed: %s", name, e)
            return f"Error executing {name}: {e}"


# Module-level 實例
registry = ToolRegistry()
