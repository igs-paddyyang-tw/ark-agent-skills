# Telegram 整合參考（webbot 的 TG 層）

> 併自原 `ark-telegram-bot`（2026-09-08 三合一）。
> 本檔是 `ark-webapp-generator` 產出的 webbot 骨架中，**TG channel 的 API 與 UX 慣例**。
>
> 🔴 **定位提醒**：若你的專案是 `ark_bot_agent` / `ark_team_agent` 的**消費端**，
> TG polling / adapter 已由套件內建，**不要照本檔手搭 adapter** ——
> 只需在 `bot.yaml`（`ark_bot_agent`）或 `team.yaml` 的 `channel.bot_token_env`
> （`ark_team_agent`）設定即可。本檔適用於 **webapp-generator 產出的獨立 FastAPI 應用**
> （非套件消費端）要自己接 TG 的場景。

## 依賴

```
python-telegram-bot[ext]>=21.0
python-dotenv>=1.0.0
```

## Adapter 模組（獨立應用自接 TG 時）

產出 `src/{package_name}/telegram_adapter.py`，核心方法：

```python
class TelegramAdapter:
    """Telegram Bot 適配器 — 私聊模式，訊息路由到後端。"""
    def __init__(self, backend) -> None: ...
    async def start(self) -> None: ...           # Bot polling + 啟動通知
    async def stop(self) -> None: ...            # 優雅關閉
    async def _on_message(self, update, ctx): ... # 訊息 → 後端
    async def _poll_output(self, name): ...      # 後端輸出 → 偵測 reply → TG
    async def _send(self, chat_id, text): ...    # rate limited 發送
    async def _cmd_start/_cmd_status/_cmd_help    # 指令
    async def _notify_startup(self): ...         # 啟動通知
```

| 功能 | 說明 |
|------|------|
| Bot polling | 持續監聽（TG 一律 polling，不需開 port） |
| 私聊路由 | 預設目標 / @mention 指定 |
| stdout 過濾 | 過濾 shell/git/pip/traceback 雜訊 |
| Rate limiting | 100ms 間隔 + 429 重試 |
| 分段發送 | > 4000 字自動切割 |
| HTML 格式 | 粗體/斜體/code + fallback 純文字 |
| 白名單 | `access.allowed_users` 驗證 |

## TG API 限制（送檔/媒體）

| 類型 | 大小限制 | 方法 |
|------|---------|------|
| Photo | 10MB（寬+高 ≤ 10000px） | `send_photo` |
| Document | 50MB | `send_document` |
| Video | 50MB | `send_video` |
| Audio | 50MB | `send_audio` |
| Voice | 1MB（OGG/OPUS） | `send_voice` |
| Caption | ≤ 1024 字元 | — |

- 重複發送同一圖片 → 快取 `file_id`（最快）
- 相簿 `send_media_group`：2-10 個，caption 只在第一個項目

## UX 慣例

- **Menu 命令**：`setMyCommands` 設定 `/start` `/status` `/help`
- **InlineKeyboard**：模式切換、選項用按鈕（避免開放式問句）
- **Web App / Mini App**：Menu Button 開啟（`web_app` 參數）
- **就地編輯 vs 新訊息**：最終回覆用新訊息（TG 對編輯不發通知，使用者易錯過）

## 前置條件

- Token 從 `.env` 讀（`bot_token_env` 指定變數名）
- 至少一個 reply 出口（私訊 chat_id）
- Bot polling 需 BotFather 關閉 privacy mode（若要收群組非 @ 訊息）
