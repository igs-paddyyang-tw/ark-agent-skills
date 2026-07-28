"""ProgressStack — 堆疊式進度訊息，透過 edit_message 原地更新。"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class ProgressStack:
    """堆疊式進度訊息。

    使用者看到一條不斷更新的進度訊息，清楚知道目前在哪一步。
    透過 TG edit_message_text 原地更新，不發多條通知。

    狀態符號：
        ⏳ 進行中
        ✅ 完成
        ❌ 失敗
    """

    def __init__(self, chat_id: int, bot):
        self.chat_id = chat_id
        self.bot = bot
        self.message_id: int | None = None
        self.steps: list[str] = []

    async def init(self, first_step: str) -> None:
        """發送第一條進度訊息，記錄 message_id。"""
        self.steps.append(f"⏳ {first_step}")
        try:
            msg = await self.bot.send_message(self.chat_id, self._render())
            self.message_id = msg.message_id
        except Exception as e:
            log.warning("ProgressStack.init failed: %s", e)

    async def update(self, step: str, complete_previous: bool = True) -> None:
        """標記上一步完成 + 新增下一步。"""
        if complete_previous and self.steps:
            last = self.steps[-1]
            if last.startswith("⏳"):
                self.steps[-1] = last.replace("⏳", "✅", 1)
        self.steps.append(f"⏳ {step}")
        await self._edit()

    async def complete(self, final_text: str) -> None:
        """標記全部完成 + 附上最終回覆。"""
        if self.steps and self.steps[-1].startswith("⏳"):
            self.steps[-1] = self.steps[-1].replace("⏳", "✅", 1)
        separator = "───────────────────────"
        # 截斷以避免超過 TG 4096 字元限制
        max_final = 3500 - len(self._render()) - len(separator) - 10
        if len(final_text) > max_final:
            final_text = final_text[:max_final] + "\n\n⚠️ 回覆已截斷"
        full = self._render() + f"\n{separator}\n{final_text}"
        await self._edit(full)

    async def fail(self, error: str) -> None:
        """標記當前步驟失敗。"""
        if self.steps and self.steps[-1].startswith("⏳"):
            self.steps[-1] = self.steps[-1].replace("⏳", "❌", 1)
        self.steps.append(f"⚠️ {error}")
        await self._edit()

    def _render(self) -> str:
        """渲染進度文字。"""
        return "🚀 [Ark Agent]\n\n" + "\n".join(self.steps)

    async def _edit(self, text: str | None = None) -> None:
        """編輯進度訊息。靜默處理錯誤（訊息未變更時 TG 會拋錯）。"""
        if not self.message_id:
            return
        try:
            await self.bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=self.message_id,
                text=text or self._render(),
            )
        except Exception:
            pass  # 訊息未變更或 rate limit，忽略
