"""Session 與 Turn 資料結構。"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum


class SessionState(Enum):
    IDLE = "idle"
    EXECUTING = "executing"


@dataclass
class Turn:
    role: str       # "user" | "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class Session:
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    user_id: int = 0
    turns: list[Turn] = field(default_factory=list)
    state: SessionState = SessionState.IDLE
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def add_turn(self, role: str, content: str) -> Turn:
        """新增一輪對話。最多保留 20 輪。"""
        t = Turn(role=role, content=content)
        self.turns.append(t)
        if len(self.turns) > 20:
            self.turns = self.turns[-20:]
        self.updated_at = time.time()
        return t

    def get_recent_turns(self, n: int = 10) -> list[Turn]:
        return self.turns[-n:]

    def is_expired(self, ttl: int = 1800) -> bool:
        return (time.time() - self.updated_at) > ttl
