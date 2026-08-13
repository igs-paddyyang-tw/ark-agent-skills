"""UserProfiler — 從對話中自動萃取使用者偏好。

功能：
- 每 N 輪對話觸發一次 LLM 分析
- 萃取使用者偏好 key-value 寫入 memory
- 可自訂允許的 field 名稱
- 支援中英文 key: value 解析

用法：
  profiler = UserProfiler(memory=memory_store, llm_fn=my_llm_chat)
  if profiler.should_profile(user_id, session):
      prefs = await profiler.profile(user_id, session)
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Awaitable

from .session import Session

log = logging.getLogger(__name__)

# ── 設定 ──────────────────────────────────────────────────
PROFILE_INTERVAL = 10  # 每 N 輪觸發一次

ALLOWED_FIELDS: set[str] = {
    "偏好語言", "常用指令", "關注主題", "預設模型",
    "工作風格", "回覆格式", "時區", "暱稱",
    "常用 Skill", "專案背景", "技術棧", "備註",
    "上次互動", "對話摘要",
}

EXTRACT_PROMPT = """分析以下對話，萃取使用者的偏好和習慣。
只回傳 key: value 格式，每行一個，可用的 key 有：
偏好語言、常用指令、關注主題、工作風格、回覆格式、時區、暱稱、常用 Skill、專案背景、技術棧、備註

對話內容：
{conversation}

只輸出有把握的偏好（至少出現 2 次以上的模式），不要猜測。格式範例：
偏好語言: 繁體中文
關注主題: AI、遊戲開發
"""


class UserProfiler:
    """自動萃取使用者偏好。

    參數：
      memory — 需實作 write(user_id, key, value) 方法
      llm_fn — async LLM 呼叫函式，簽名 (prompt, system_prompt) -> str
      interval — 每幾輪觸發一次（預設 10）
    """

    def __init__(
        self,
        memory: Any,
        llm_fn: Callable[[str, str], Awaitable[str | tuple]],
        interval: int = PROFILE_INTERVAL,
    ) -> None:
        self._memory = memory
        self._llm_fn = llm_fn
        self._interval = interval
        self._turn_counts: dict[int, int] = {}

    def should_profile(self, user_id: int, session: Session) -> bool:
        """判斷是否該觸發 profiling。"""
        count = len(session.turns)
        last_count = self._turn_counts.get(user_id, 0)
        return (count - last_count) >= self._interval

    async def profile(self, user_id: int, session: Session) -> dict[str, str]:
        """執行 profiling：從對話萃取偏好，寫入 memory。

        回傳萃取到的 {key: value}。
        """
        self._turn_counts[user_id] = len(session.turns)

        # 取最近 20 輪對話
        recent_turns = session.turns[-20:]
        conversation = "\n".join(
            f"{'用戶' if t.role == 'user' else '助理'}: {t.content[:150]}"
            for t in recent_turns
        )

        prompt = EXTRACT_PROMPT.format(conversation=conversation)

        try:
            raw_result = await self._llm_fn(prompt, "你是分析助手，只輸出結構化結果。")
            text = raw_result[0] if isinstance(raw_result, tuple) else raw_result
        except Exception as e:
            log.warning("UserProfiler LLM 呼叫失敗: %s", e)
            return {}

        if not text:
            return {}

        extracted = self._parse_result(text)

        # 寫入 memory
        for key, value in extracted.items():
            self._memory.write(user_id, key, value)

        if extracted:
            log.info("使用者 %d profiling 完成，萃取 %d 項偏好", user_id, len(extracted))

        return extracted

    def _parse_result(self, text: str) -> dict[str, str]:
        """解析 LLM 回傳的 key: value 格式。"""
        result = {}
        for line in text.strip().splitlines():
            line = line.strip().lstrip("- ")
            if ":" in line:
                sep = line.index(":")
                key = line[:sep].strip()
                value = line[sep + 1:].strip()
                if key in ALLOWED_FIELDS and value:
                    result[key] = value
            elif "：" in line:
                sep = line.index("：")
                key = line[:sep].strip()
                value = line[sep + 1:].strip()
                if key in ALLOWED_FIELDS and value:
                    result[key] = value
        return result
