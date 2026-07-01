"""reaction_manager.py — Telegram 表情反應 + Typing 生命週期管理。

使用 Telegram 合法 Reaction emoji：👀→🔥→👍/💔
不可用 ✅❌（不在官方支援清單）。

用法：
    rm = ReactionManager(bot)
    await rm.mark_received(chat_id, msg_id)
    rm.start_typing("main", chat_id)
    await rm.mark_processing(chat_id, msg_id)
    # ... 執行 ...
    await rm.mark_done(chat_id, msg_id, success=True)
    rm.stop_typing("main")
"""
from __future__ import annotations

import asyncio
import logging
from typing import Literal

from telegram import Bot, ReactionTypeEmoji
from telegram.constants import ChatAction

log = logging.getLogger(__name__)

# Telegram 合法 Reaction emoji
REACTION_RECEIVED = "👀"
REACTION_PROCESSING = "🔥"
REACTION_DELEGATING = "⚡"
REACTION_SUCCESS = "👍"
REACTION_FAILURE = "💔"

# Typing action 類型
TypingAction = Literal["typing", "upload_photo", "upload_document"]


class ReactionManager:
    """管理 Telegram 訊息 reaction 生命週期 + typing indicator。"""

    def __init__(self, bot: Bot) -> None:
        self._bot = bot
        self._typing_tasks: dict[str, asyncio.Task] = {}

    # ── Reaction ──────────────────────────────────────────

    async def mark_received(self, chat_id: int, msg_id: int) -> None:
        """收到訊息 → 👀。"""
        await self._set_reaction(chat_id, msg_id, REACTION_RECEIVED)

    async def mark_processing(self, chat_id: int, msg_id: int) -> None:
        """開始處理 → 🔥。"""
        await self._set_reaction(chat_id, msg_id, REACTION_PROCESSING)

    async def mark_delegating(self, chat_id: int, msg_id: int) -> None:
        """派工中 → ⚡。"""
        await self._set_reaction(chat_id, msg_id, REACTION_DELEGATING)

    async def mark_done(self, chat_id: int, msg_id: int, success: bool = True) -> None:
        """完成 → 👍 或 💔。"""
        emoji = REACTION_SUCCESS if success else REACTION_FAILURE
        await self._set_reaction(chat_id, msg_id, emoji)

    async def _set_reaction(self, chat_id: int, msg_id: int, emoji: str) -> None:
        """底層 API 呼叫，失敗靜默（群組可能禁用 reaction）。"""
        try:
            await self._bot.set_message_reaction(
                chat_id=chat_id,
                message_id=msg_id,
                reaction=[ReactionTypeEmoji(emoji=emoji)],
                is_big=False,
            )
        except Exception as e:
            log.debug("set_reaction failed (chat=%d, msg=%d): %s", chat_id, msg_id, e)

    # ── Typing Indicator ──────────────────────────────────

    def start_typing(
        self,
        key: str,
        chat_id: int,
        thread_id: int | None = None,
        action: TypingAction = "typing",
    ) -> None:
        """啟動 typing indicator loop（4 秒一次）。"""
        self.stop_typing(key)
        self._typing_tasks[key] = asyncio.create_task(
            self._typing_loop(chat_id, thread_id, action)
        )

    def stop_typing(self, key: str) -> None:
        """停止 typing indicator。"""
        task = self._typing_tasks.pop(key, None)
        if task and not task.done():
            task.cancel()

    async def _typing_loop(
        self, chat_id: int, thread_id: int | None, action: TypingAction
    ) -> None:
        """每 4 秒送出 chat action（低於 Telegram 5s 超時）。"""
        action_map = {
            "typing": ChatAction.TYPING,
            "upload_photo": ChatAction.UPLOAD_PHOTO,
            "upload_document": ChatAction.UPLOAD_DOCUMENT,
        }
        chat_action = action_map.get(action, ChatAction.TYPING)
        try:
            while True:
                try:
                    kwargs: dict = {"chat_id": chat_id, "action": chat_action}
                    if thread_id:
                        kwargs["message_thread_id"] = thread_id
                    await self._bot.send_chat_action(**kwargs)
                except Exception:
                    pass
                await asyncio.sleep(4)
        except asyncio.CancelledError:
            pass

    # ── 清理 ─────────────────────────────────────────────

    def stop_all(self) -> None:
        """停止所有 typing tasks（shutdown 時呼叫）。"""
        for key in list(self._typing_tasks.keys()):
            self.stop_typing(key)


def get_reaction_manager(context) -> "ReactionManager":
    """從 bot_data 取得 ReactionManager instance。"""
    if "reaction_manager" not in context.bot_data:
        context.bot_data["reaction_manager"] = ReactionManager(context.bot)
    return context.bot_data["reaction_manager"]
