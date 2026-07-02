"""Agent Session 管理 — 每個 user 一次只能跟一個 Agent 對話。

功能：
  - 追蹤每個 user_id 的 current_agent
  - 保留最近 N 輪對話歷史（多輪記憶）
  - 切換 Agent 時清空歷史（新對話）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ConversationTurn:
    """單輪對話。"""

    role: str  # "user" | "agent"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class UserSession:
    """單一使用者的 Session。"""

    user_id: int
    current_agent: str = "admin"
    history: list[ConversationTurn] = field(default_factory=list)
    max_turns: int = 10
    last_active: str = field(default_factory=lambda: datetime.now().isoformat())

    def add_turn(self, role: str, content: str) -> None:
        """新增一輪對話，超過上限時移除最舊的。"""
        self.history.append(ConversationTurn(role=role, content=content))
        if len(self.history) > self.max_turns:
            self.history = self.history[-self.max_turns:]
        self.last_active = datetime.now().isoformat()

    def get_context(self) -> str:
        """取得對話歷史作為 context 字串（注入 LLM）。"""
        if not self.history:
            return ""
        lines = ["## 近期對話歷史\n"]
        for turn in self.history:
            prefix = "👤 User" if turn.role == "user" else "🤖 Agent"
            lines.append(f"{prefix}: {turn.content}")
        return "\n".join(lines)

    def clear_history(self) -> None:
        """清空對話歷史（切換 Agent 時）。"""
        self.history = []


class SessionManager:
    """管理所有使用者 Session。"""

    def __init__(self) -> None:
        self._sessions: dict[int, UserSession] = {}

    def get_or_create(self, user_id: int) -> UserSession:
        """取得或建立 Session。"""
        if user_id not in self._sessions:
            self._sessions[user_id] = UserSession(user_id=user_id)
        return self._sessions[user_id]

    def switch_agent(self, user_id: int, agent_id: str) -> UserSession:
        """切換 Agent（清空歷史，開始新對話）。"""
        session = self.get_or_create(user_id)
        if session.current_agent != agent_id:
            session.current_agent = agent_id
            session.clear_history()
        session.last_active = datetime.now().isoformat()
        return session

    def get_current_agent(self, user_id: int) -> str:
        """取得當前 Agent ID。"""
        return self.get_or_create(user_id).current_agent


# Module-level 實例
session_manager = SessionManager()
