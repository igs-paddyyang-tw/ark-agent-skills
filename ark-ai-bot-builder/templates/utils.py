"""Bot 工具：進度回報、訊息分段、Trace 記錄。"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path


class ProgressReporter:
    """edit_message 進度更新（節流 1.5s）。"""

    STAGES = ["🤖 分析問題中...", "🤖 搜尋相關資料...", "🤖 組織回答..."]

    def __init__(self, message):
        self._msg = message
        self._last_edit = 0
        self._stage = 0

    async def next(self) -> None:
        if self._stage < len(self.STAGES):
            now = time.time()
            if now - self._last_edit > 1.5:
                try:
                    await self._msg.edit_text(self.STAGES[self._stage])
                except Exception:
                    pass
                self._last_edit = now
            self._stage += 1


def split_message(text: str, max_len: int = 4000) -> list:
    """按段落邊界切分長文。"""
    if len(text) <= max_len:
        return [text]
    chunks = []
    while len(text) > max_len:
        cut = text.rfind("\n\n", 0, max_len)
        if cut == -1:
            cut = text.rfind("\n", 0, max_len)
        if cut == -1:
            cut = max_len
        chunks.append(text[:cut])
        text = text[cut:].lstrip()
    if text:
        chunks.append(text)
    return chunks


class TraceLogger:
    """JSONL trace 記錄。"""

    DIR = Path("data/traces")

    def __init__(self):
        self.DIR.mkdir(parents=True, exist_ok=True)

    def log(self, user_id: int, mode: str, backend: str, duration: float, success: bool, prompt_len: int, reply_len: int) -> None:
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "user_id": user_id,
            "mode": mode,
            "backend": backend,
            "duration_s": round(duration, 1),
            "success": success,
            "prompt_len": prompt_len,
            "reply_len": reply_len,
            "tokens_est": (prompt_len + reply_len) // 4,
        }
        path = self.DIR / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_today_usage(self) -> dict:
        path = self.DIR / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        if not path.exists():
            return {"calls": 0, "tokens_est": 0, "total_duration": 0}
        calls = 0
        tokens = 0
        duration = 0.0
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entry = json.loads(line)
                calls += 1
                tokens += entry.get("tokens_est", 0)
                duration += entry.get("duration_s", 0)
        return {"calls": calls, "tokens_est": tokens, "total_duration": round(duration, 1)}

    def get_recent(self, n: int = 5) -> list:
        path = self.DIR / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        return [json.loads(l) for l in lines[-n:]]
