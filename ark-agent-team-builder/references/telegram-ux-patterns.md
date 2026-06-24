# Telegram UX Patterns — Reaction + Typing 整合指南

> 產出 Agent Team Bot 時的 Telegram 使用者回饋模式。
> 來源：ninja-bot 實戰驗證（2026-06-24）。

---

## 設計原則

1. **即時回饋**：使用者發訊 < 1 秒內必須看到 👀
2. **狀態可見**：處理中有 typing indicator，不讓使用者等待無回應
3. **完成明確**：結束時 reaction 切換為成功/失敗
4. **靜默降級**：群組禁用 reaction 時不報錯

---

## Reaction 生命週期

```
使用者發訊
  → 👀 mark_received（第一時間，Planner 之前）
  → ⏳ mark_processing（確認目標 agent 後）
  → 🔄 mark_delegating（派工給子 Agent 時，team-builder 專用）
  → 👍/👎 mark_done（完成或失敗）
```

**關鍵規則：** `mark_received` 必須在任何路由/判斷邏輯之前觸發。

**Telegram 支援的 Reaction emoji（完整清單）：**
- 👍 👎 ❤️ 🔥 🎉 😢 👀 🤔 💯
- ⚠️ `✅` `❌` **不在官方支援清單中**，會靜默失敗。必須用 👍/👎 替代。

---

## ReactionManager 完整實作

```python
"""reaction_manager.py — Telegram 表情反應 + Typing 生命週期管理。"""
from __future__ import annotations

import asyncio
import logging

log = logging.getLogger(__name__)


class ReactionManager:
    """管理 Telegram 訊息 reaction 生命週期 + typing indicator。"""

    def __init__(self, bot=None):
        self._bot = bot
        self._targets: dict[str, tuple[int, int]] = {}  # instance → (chat_id, msg_id)
        self._typing_tasks: dict[str, asyncio.Task] = {}

    def set_bot(self, bot) -> None:
        """延遲設定 bot（啟動後才有）。"""
        self._bot = bot

    # ── Reaction ──────────────────────────────────────────

    async def mark_received(self, instance: str, chat_id: int, message_id: int) -> None:
        """收到訊息 → 👀。"""
        self._targets[instance] = (chat_id, message_id)
        await self._set_reaction(chat_id, message_id, "👀")

    async def mark_processing(self, instance: str) -> None:
        """開始處理 → ⏳。"""
        target = self._targets.get(instance)
        if target:
            await self._set_reaction(*target, "⏳")

    async def mark_delegating(self, instance: str) -> None:
        """派工給子 Agent → 🔄。"""
        target = self._targets.get(instance)
        if target:
            await self._set_reaction(*target, "🔄")

    async def mark_done(self, instance: str, success: bool = True) -> None:
        """完成 → 👍 或 👎。"""
        target = self._targets.pop(instance, None)
        if target:
            emoji = "👍" if success else "👎"
            await self._set_reaction(*target, emoji)

    async def _set_reaction(self, chat_id: int, message_id: int, emoji: str) -> None:
        """底層 API 呼叫，失敗靜默。"""
        if not self._bot:
            return
        try:
            from telegram import ReactionTypeEmoji
            await self._bot.set_message_reaction(
                chat_id=chat_id,
                message_id=message_id,
                reaction=[ReactionTypeEmoji(emoji=emoji)],
                is_big=False,
            )
        except Exception as e:
            log.debug("set_reaction failed (chat=%d, msg=%d): %s", chat_id, message_id, e)

    # ── Typing Indicator ──────────────────────────────────

    def start_typing(self, instance: str, chat_id: int,
                     thread_id: int | None = None, action: str = "typing") -> None:
        """啟動 typing indicator loop（4 秒一次）。"""
        self.stop_typing(instance)
        self._typing_tasks[instance] = asyncio.create_task(
            self._typing_loop(instance, chat_id, thread_id, action)
        )

    def stop_typing(self, instance: str) -> None:
        """停止 typing indicator。"""
        task = self._typing_tasks.pop(instance, None)
        if task and not task.done():
            task.cancel()

    async def _typing_loop(self, instance: str, chat_id: int,
                           thread_id: int | None, action: str) -> None:
        """每 4 秒送出 chat action。"""
        from telegram.constants import ChatAction
        action_map = {
            "typing": ChatAction.TYPING,
            "upload_photo": ChatAction.UPLOAD_PHOTO,
            "upload_document": ChatAction.UPLOAD_DOCUMENT,
        }
        chat_action = action_map.get(action, ChatAction.TYPING)
        try:
            while True:
                try:
                    kwargs = {"chat_id": chat_id, "action": chat_action}
                    if thread_id:
                        kwargs["message_thread_id"] = thread_id
                    await self._bot.send_chat_action(**kwargs)
                except Exception:
                    pass
                await asyncio.sleep(4)
        except asyncio.CancelledError:
            pass

    def stop_all(self) -> None:
        """停止所有 typing tasks（shutdown 時呼叫）。"""
        for instance in list(self._typing_tasks.keys()):
            self.stop_typing(instance)
        self._targets.clear()
```

---

## Gateway Telegram Handler 整合點

### 產出的 gateway/telegram/handlers/message.py 中：

```python
async def handle_message(update, context):
    msg = update.effective_message
    rm: ReactionManager = context.bot_data["reaction_manager"]

    # ★ 第一時間回饋（路由判斷之前）
    target_agent = _resolve_target(msg.text)
    await rm.mark_received(target_agent or "default", msg.chat_id, msg.message_id)

    # 路由判斷...
    if not target_agent:
        target_agent = _route_to_default_agent(msg.text)

    # 發送給 Agent
    await rm.mark_processing(target_agent)
    rm.start_typing(target_agent, msg.chat_id)

    try:
        result = await _send_to_daemon(target_agent, msg.text)
        await rm.mark_done(target_agent, success=bool(result))
    except Exception:
        await rm.mark_done(target_agent, success=False)
    finally:
        rm.stop_typing(target_agent)

    # 回覆使用者
    if result:
        await msg.reply_text(result)
```

### delegate_task 時加入 🔄：

```python
async def _delegate_to_worker(rm, leader, worker, task, chat_id, msg_id):
    """Leader 派工給 Worker 時的 reaction 流程。"""
    await rm.mark_delegating(leader)  # 🔄 表示正在派工
    result = await daemon.delegate_task(worker, task)
    await rm.mark_done(leader, success=bool(result))
```

---

## Typing Action 感知

| 觸發場景 | Chat Action | 使用者看到 |
|----------|-------------|-----------|
| 一般處理 | `typing` | "正在輸入..." |
| 產出檔案（HTML/PDF） | `upload_document` | "正在傳送檔案..." |
| 圖片生成 | `upload_photo` | "正在傳送圖片..." |

---

## 踩坑紀錄

### 1. 雙重回覆（reply_fn + handler 同時回覆）

**現象**：使用者收到兩次回覆。

**根因**：daemon 的 `reply_fn` 和 handler 的 `msg.reply_text()` 同時生效。

**規則**：
- 有 Telegram Update context 時 → **handler 回覆**（唯一出口）
- 無 context（排程、系統告警）→ 用 `notify_fn` 推送
- **永遠不要同時設定兩個出口**

```python
# ❌ 錯誤
daemon.set_reply_fn(_reply)          # 出口 A
result = await daemon.send(name, msg)
await msg.reply_text(result)         # 出口 B

# ✅ 正確（只有一個出口）
result = await daemon.send(name, msg)
await msg.reply_text(result)         # 唯一出口
```

### 2. mark_received 時機太晚

**規則**：👀 必須在 Planner / Router 之前觸發。

### 3. Telegram Reaction emoji 限制

Telegram Bot API 支援的 Reaction emoji：
- 👍 👎 ❤️ 🔥 🎉 😢 👀 🤔 💯

**`✅` `❌` 不在官方支援清單中**，Bot API 可能接受但部分 client 不顯示。統一使用 👍/👎。

### 4. 群組禁用 Reaction

某些群組設定禁止 Bot 發 reaction → `_set_reaction` 必須 try/except 靜默降級。

---

## 與 team-agent 本體的差異

| 項目 | team-agent（已有） | Builder 產出（建議） |
|------|-------------------|---------------------|
| 設計 | instance-centric（一個 instance 一個 pending） | 同 |
| Typing 管理 | 分離在 telegram.py | 合併在 ReactionManager |
| mark_delegating | ❌ 缺少 | ✅ 有 |
| stop_all | ❌ 缺少 | ✅ 有 |
| 介面 | `mark_received(instance, chat_id, msg_id)` | 同 |

Builder 產出的版本比 team-agent 本體更完整（含 typing + stop_all + delegating）。
team-agent 本體可選擇升級，但不影響 builder 獨立產出。
