"""Session 與 Turn 資料結構。

提供對話的基本資料模型：
- Turn：單輪對話（role + content + metadata）
- Session：完整對話 session（多輪 + 狀態 + context）
- SessionState：session 生命週期狀態
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


class SessionState(Enum):
    """Session 生命週期狀態。"""

    IDLE = "idle"
    CLARIFYING = "clarifying"
    EXECUTING = "executing"


@dataclass
class Turn:
    """單輪對話。"""

    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


@dataclass
class Session:
    """使用者對話 session。

    - 自動截斷超過 max_turns 的歷史
    - 支援 TTL 過期判斷
    - context dict 用於跨輪次狀態傳遞
    """

    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    user_id: int = 0
    turns: list[Turn] = field(default_factory=list)
    state: SessionState = SessionState.IDLE
    context: dict = field(default_factory=dict)
    clarify_count: int = 0
    max_clarify: int = 3
    max_turns: int = 20
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def add_turn(self, role: str, content: str, **metadata) -> Turn:
        """新增一輪對話，超過 max_turns 自動截斷。"""
        t = Turn(role=role, content=content, metadata=metadata)
        self.turns.append(t)
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]
        self.updated_at = time.time()
        return t

    def get_recent_turns(self, n: int = 10) -> list[Turn]:
        """取得最近 N 輪。"""
        return self.turns[-n:]

    def is_expired(self, ttl: int = 1800) -> bool:
        """Session 是否已過期。"""
        return (time.time() - self.updated_at) > ttl
