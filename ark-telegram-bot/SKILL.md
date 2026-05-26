---
name: ark-telegram-bot
author: paddyyang
description: |
  Telegram Bot 開發完整 SOP（python-telegram-bot）：傳送圖片/檔案/相簿、
  Web App 整合、Menu 命令設定、InlineKeyboard 互動、訊息格式化與分段、
  Rate Limiting 處理、推送通知（排程/告警）、Workflow 串接。
  為 ark-agent-team-builder 打造的 Telegram UI/UX 互動標準。
  也可產出完整可運行的 Telegram Adapter 模組（整合 CoreDaemon）。
  使用此 Skill 當使用者提及 Telegram Bot 開發、TG 推送、傳送圖片、傳送檔案、
  Web App、Mini App、Menu 命令、InlineKeyboard、Bot API、
  訊息格式、分段發送、TG 通知、推播訊息、告警通知、
  產出 Telegram adapter、整合 Bot 到團隊、telegram_adapter、
  或任何 Telegram Bot 功能開發與推送場景。
metadata:
  version: "3.0"
  updated: 2026-05-18
---

# ark-telegram-bot

Telegram Bot 開發完整 SOP — 8 大模組（含推送通知）+ **Adapter 產出模式** + ark-team-agent 整合指引。

## 模式選擇

| 模式 | 觸發詞 | 產出 |
|------|--------|------|
| **SOP 模式**（預設） | 「Telegram Bot 開發」「TG 推送」 | 教學文件 + 程式碼片段 |
| **Adapter 模式** | 「產出 Telegram adapter」「整合 Bot 到團隊」 | `src/{pkg}/telegram_adapter.py` 可運行模組 |

---

## Adapter 模式（產出可運行的 Telegram 整合模組）

### 觸發條件

- 「產出 Telegram adapter」「整合 Bot 到團隊」
- 「telegram_adapter」「Bot 接入」
- Phase C2 執行時

### 輸入參數

| 參數 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `project_dir` | `str` | ✅ | — | 專案目錄 |
| `package_name` | `str` | ✅ | — | Python 套件名（如 `game_analytics`） |
| `default_target` | `str` | ❌ | `"leader-agent"` | 預設訊息路由目標 |

### 產出檔案

```
{project_dir}/src/{package_name}/telegram_adapter.py
```

### 產出內容（~340 行）

```python
class TelegramAdapter:
    """Telegram Bot 適配器 — 私聊模式，訊息路由到 CoreDaemon。"""

    def __init__(self, daemon: CoreDaemon) -> None: ...
    async def start(self) -> None: ...          # Bot polling + 啟動通知
    async def stop(self) -> None: ...           # 優雅關閉
    async def _on_message(self, update, ctx): ... # 訊息 → agent stdin
    async def _poll_output(self, name): ...     # stdout → 偵測 reply → TG
    async def _extract_final_reply(self, lines): ... # 過濾雜訊提取回覆
    async def _send(self, chat_id, text): ...   # rate limited 發送
    async def _send_reply(self, text): ...      # reply → 使用者
    async def _cmd_start(self, update, ctx): ... # /start 歡迎
    async def _cmd_status(self, update, ctx): ... # /status 狀態
    async def _cmd_help(self, update, ctx): ...  # /help 說明
    async def _notify_startup(self): ...        # 啟動通知
```

### 功能清單

| 功能 | 說明 |
|------|------|
| Bot polling | 持續監聽 Telegram 訊息 |
| 私聊路由 | 預設 → leader，@mention → 指定 agent |
| stdout 監聽 | 偵測 reply() 呼叫 → 發送 Telegram |
| stdout 過濾 | 過濾 shell/git/pip/traceback 雜訊 |
| /start | 歡迎訊息 + 使用說明 + 團隊成員 |
| /status | 各 agent 狀態（alive/idle/restarts） |
| /help | 指令說明 |
| 啟動通知 | 「✅ Team 就緒 N/N」 |
| Rate limiting | 100ms 間隔 + 429 重試 |
| 分段發送 | > 4000 字自動切割 |
| HTML 格式 | 粗體/斜體/code + fallback 純文字 |
| 白名單 | access.allowed_users 驗證 |

### 整合到 start.py

```python
from src.{package_name}.telegram_adapter import TelegramAdapter

daemon = CoreDaemon("team.yaml")
# ... 啟動 agents ...
adapter = TelegramAdapter(daemon)
await adapter.start()
# ... 主迴圈 ...
await adapter.stop()
```

### 依賴

```
python-telegram-bot[ext]>=21.0
python-dotenv>=1.0.0
```

### 前置條件

- team.yaml 有 `channel.bot_token_env` 設定
- .env 有對應的 Bot Token
- 至少一個 instance 有 `private_chat`（reply 出口）
- CoreDaemon 已啟動（agents 在運行中）

### 驗收

- Bot 收到訊息 → agent stdin 收到
- agent reply → Telegram 發送給使用者
- /start 顯示歡迎 + 團隊成員
- /status 顯示 agent 狀態

---

## SOP 模式（以下為原有內容）

使用 `python-telegram-bot[ext]>=21.0`，為 ark-agent-team-builder 團隊打造 Telegram UI/UX 互動標準。

## 觸發條件

- 「Telegram Bot」「TG 開發」「Bot API」
- 「傳送圖片」「傳送檔案」「send photo」
- 「Web App」「Mini App」「webapp」
- 「Menu 命令」「BotCommand」「setMyCommands」
- 「InlineKeyboard」「callback」「按鈕互動」
- 「訊息格式」「分段發送」「HTML 格式」
- 「設定 Telegram」「Bot 加入群組」「取得 group_id」「TG 設定」

---

## 前置條件

- Python 3.11+ / `python-telegram-bot[ext]>=21.0`
- Bot Token（BotFather 取得）
- 了解 async/await

---

## 模組 1：傳送圖片

### 三種方式

```python
# 1. 本地檔案
await bot.send_photo(chat_id, photo=open("img.png", "rb"), caption="說明文字")

# 2. URL
await bot.send_photo(chat_id, photo="https://example.com/img.jpg")

# 3. file_id（已上傳過的檔案，最快）
await bot.send_photo(chat_id, photo="AgACAgIAAxk...")
```

### 限制

| 項目 | 限制 |
|------|------|
| 圖片大小 | ≤ 10MB（photo）/ ≤ 50MB（document） |
| 圖片尺寸 | 寬+高 ≤ 10000px |
| Caption | ≤ 1024 字元 |
| 格式 | JPEG / PNG / GIF / WebP |

### SOP

1. 圖片 ≤ 10MB → `send_photo`（自動壓縮 + 預覽）
2. 圖片 > 10MB 或需保留原檔 → `send_document`
3. 重複發送同一圖片 → 快取 `file_id`，後續用 file_id 發送
4. 加說明 → `caption` + `parse_mode="HTML"`

---

## 模組 2：傳送檔案

```python
# 文件
await bot.send_document(chat_id, document=open("report.pdf", "rb"),
                        filename="report.pdf", caption="每日報表")

# 影片
await bot.send_video(chat_id, video=open("demo.mp4", "rb"),
                     width=1280, height=720, duration=30)

# 音訊
await bot.send_audio(chat_id, audio=open("bgm.mp3", "rb"),
                     title="BGM", performer="OceanKing")
```

### 限制

| 類型 | 大小限制 | 方法 |
|------|---------|------|
| Document | 50MB | `send_document` |
| Video | 50MB | `send_video` |
| Audio | 50MB | `send_audio` |
| Voice | 1MB | `send_voice`（OGG/OPUS） |

---

## 模組 3：相簿（Media Group）

```python
from telegram import InputMediaPhoto, InputMediaDocument

# 圖片相簿（2-10 張）
media = [
    InputMediaPhoto(open("1.jpg", "rb"), caption="相簿標題"),  # 只第一張加 caption
    InputMediaPhoto(open("2.jpg", "rb")),
    InputMediaPhoto(open("3.jpg", "rb")),
]
await bot.send_media_group(chat_id, media=media)

# 文件相簿
media = [
    InputMediaDocument(open("a.pdf", "rb")),
    InputMediaDocument(open("b.pdf", "rb")),
]
await bot.send_media_group(chat_id, media=media)
```

### 規則

- 2-10 個媒體
- 同一 group 只能混合 photo+video 或純 document
- Caption 只在第一個項目設定

---

## 模組 4：Web App（Mini App）

### 設定 Menu Button 開啟 Web App

```python
from telegram import MenuButtonWebApp, WebAppInfo

await bot.set_chat_menu_button(
    chat_id=chat_id,
    menu_button=MenuButtonWebApp(
        text="🎮 開啟遊戲",
        web_app=WebAppInfo(url="https://your-domain.com/app")
    )
)
```

### InlineKeyboard 開啟 Web App

```python
keyboard = InlineKeyboardMarkup([[
    InlineKeyboardButton("🎮 Play", web_app=WebAppInfo(url="https://your-domain.com/game"))
]])
await bot.send_message(chat_id, "點擊開始遊戲：", reply_markup=keyboard)
```

### 接收 Web App 資料

```python
async def handle_web_app_data(update, context):
    data = update.effective_message.web_app_data.data  # JSON string
    parsed = json.loads(data)
    # 處理回傳資料...
```

### 要求

- HTTPS（必須）
- 域名需在 BotFather 設定（`/setmenubutton` 或 `/newapp`）
- 前端用 `Telegram.WebApp.sendData(json)` 回傳

---

## 模組 5：Menu 命令

### 設定命令列表

```python
from telegram import BotCommand, BotCommandScopeAllPrivateChats

commands = [
    BotCommand("start", "開始使用"),
    BotCommand("help", "使用說明"),
    BotCommand("status", "系統狀態"),
    BotCommand("skills", "技能列表"),
]
await bot.set_my_commands(commands)

# 分 scope 設定（私聊 vs 群組不同命令）
await bot.set_my_commands(
    commands=[BotCommand("admin", "管理面板")],
    scope=BotCommandScopeAllPrivateChats()
)
```

### 動態更新

```python
# 刪除所有命令
await bot.delete_my_commands()

# 依語言設定
await bot.set_my_commands(commands, language_code="zh-hant")
```

### SOP

1. 啟動時 `set_my_commands` 註冊所有命令
2. 群組/私聊用不同 scope
3. 命令描述 ≤ 256 字元、命令名 1-32 字元小寫英文

---

## 模組 6：InlineKeyboard 互動

```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# 建立按鈕
keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("✅ 確認", callback_data="confirm:123")],
    [InlineKeyboardButton("❌ 取消", callback_data="cancel:123")],
])
await bot.send_message(chat_id, "確認執行？", reply_markup=keyboard)

# 處理回調
async def handle_callback(update, context):
    query = update.callback_query
    await query.answer()  # 必須！消除 loading 狀態
    data = query.data     # "confirm:123"

    if data.startswith("confirm:"):
        await query.edit_message_text("✅ 已確認")
    elif data.startswith("cancel:"):
        await query.edit_message_text("❌ 已取消")
```

### 規則

| 項目 | 限制 |
|------|------|
| callback_data | ≤ 64 bytes |
| 按鈕文字 | 無硬限制，建議 ≤ 20 字 |
| 每行按鈕 | 建議 ≤ 3 個 |
| 總按鈕數 | 建議 ≤ 8 個 |

### SOP

1. `callback_data` 用 `action:id` 格式（方便 parse）
2. handler 開頭必須 `await query.answer()`
3. 操作完成後 `edit_message_text` 或 `edit_message_reply_markup(reply_markup=None)`
4. 避免 stale button：加時間戳或 session_id 防重複點擊

---

## 模組 7：訊息格式與限制

### HTML 格式（推薦）

```python
text = (
    "<b>粗體</b> / <i>斜體</i> / <code>程式碼</code>\n"
    "<pre>多行程式碼</pre>\n"
    '<a href="https://example.com">連結</a>\n'
    "<blockquote>引用區塊</blockquote>"
)
await bot.send_message(chat_id, text, parse_mode="HTML")
```

### 字元限制

| 方法 | 限制 |
|------|------|
| send_message | 4096 字元 |
| caption | 1024 字元 |
| callback_data | 64 bytes |
| 命令描述 | 256 字元 |

### 分段策略

```python
def split_message(text: str, max_len: int = 4000) -> list[str]:
    """智慧分段：優先在換行處切割。"""
    if len(text) <= max_len:
        return [text]
    parts = []
    while text:
        if len(text) <= max_len:
            parts.append(text)
            break
        # 找最後一個換行
        cut = text.rfind("\n", 0, max_len)
        if cut == -1:
            cut = max_len
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return parts
```

### HTML Escape

```python
from html import escape
safe_text = escape(user_input)  # 防止 HTML injection
```

---

## Rate Limiting 處理

### Telegram API 限制

| 範圍 | 限制 |
|------|------|
| 全域 | 30 msg/s（不同 chat） |
| 同一 chat | 1 msg/s |
| 同一 group | 20 msg/min |
| 批量操作 | 30 msg/s |

### 429 處理

```python
from telegram.error import RetryAfter

try:
    await bot.send_message(chat_id, text)
except RetryAfter as e:
    await asyncio.sleep(e.retry_after)
    await bot.send_message(chat_id, text)  # 重試
```

### SOP

1. 用 Semaphore 限制並發（≤ 5 同時發送）
2. 每次發送間隔 ≥ 100ms
3. 捕獲 `RetryAfter` → sleep → 重試
4. 群組訊息用 queue 排隊，避免 flood

---

## 與 ark-team-agent 整合

本 Skill 的模式已在 `telegram.py` 中實作：
- `_send_to_topic` / `_send_to_private` — 基礎發送
- `MessageQueue` — per-chat 佇列 + 429 退避
- `_on_callback` — InlineKeyboard 處理
- `ToolTracker` — edit_message 即時更新

新增功能時參考本 Skill 的 SOP 確保一致性。

---

## 注意事項

- 所有 Bot API 呼叫都是 async
- 生產環境用 Webhook（非 polling）提升效能
- 敏感操作（刪除/重啟）必須加 InlineKeyboard 確認
- file_id 跨 Bot 不通用（每個 Bot 有自己的 file_id）
- Web App 必須 HTTPS + 在 BotFather 註冊域名


---

## 模組 8：推送通知（telegram_notify Skill）

產出 `src/skills/internal/telegram_notify.py`，供 Workflow 排程/告警使用。

### 參數

| 參數 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `chat_id` | `str` | ✅ | — | 推送目標 chat_id |
| `message` | `str` | ✅ | — | 訊息內容（支援 HTML） |
| `image_path` | `str` | ❌ | `None` | 圖片路徑（有則用 sendPhoto） |

### 實作要點

```python
class TelegramNotifySkill(BaseSkill):
    skill_id = "telegram_notify"
    skill_type = SkillType.PYTHON
    description = "透過 Telegram Bot API 推送訊息和圖片"

    async def execute(self, params: dict) -> SkillResult:
        # 1. 取 TELEGRAM_BOT_TOKEN（未設定 → 靜默失敗）
        # 2. image_path 存在 → send_photo（caption ≤ 1024）
        # 3. 純文字 → send_message（自動分段 ≤ 4096）
        # 4. 使用 httpx.AsyncClient POST Bot API
```

### Workflow 串接

```yaml
- id: notify
  type: skill
  skill: telegram_notify
  params:
    chat_id: "${NOTIFY_CHAT_ID}"
    message: "{{ outputs.report.content }}"
    image_path: "{{ outputs.chart.chart_path }}"
```

### 規則

- `TELEGRAM_BOT_TOKEN` 未設定 → 不報錯，回傳 `notify_success: False`
- 訊息 > 4096 字元 → 自動分段
- caption > 1024 字元 → 圖片和文字分開發送
- Windows 路徑用 `Path()` 處理

---

## 踩坑紀錄

### Windows 路徑（2026-04-17）

`image_path` 在 Windows 上可能是反斜線路徑。用 `Path(image_path).exists()` + `open(Path(...))` 處理。

### 429 Rate Limit（2026-04-20）

群組高頻發送觸發 429。解法：Semaphore(5) + per-chat queue + RetryAfter sleep。

### file_id 跨 Bot 不通用（2026-05-01）

每個 Bot 有自己的 file_id namespace，不能跨 Bot 使用。需重新上傳。

---

## Workshop 引導（agent-team-workshop）

本 Skill 對應 Workshop Step 3：設定 Telegram Bot。

### 觸發提詞

```
設定 Telegram Bot，幫我取得 group_id 並更新 .env
```

### Telegram 設定 SOP

#### 1. 建立 Bot（@BotFather）

1. Telegram 搜尋 `@BotFather`
2. 發送 `/newbot`
3. 輸入 Bot 名稱（如 `My AI Team`）
4. 輸入 username（如 `my_ai_team_bot`）
5. 取得 Token（格式：`123456:ABC-DEF...`）

#### 2. 建立群組 + 取得 group_id

1. 建立 Telegram 群組
2. 將 Bot 加入群組並設為 Admin
3. 在群組發送任意訊息
4. 瀏覽器開啟：`https://api.telegram.org/bot{TOKEN}/getUpdates`
5. 找到 `"chat":{"id":-100xxxxxxxxxx}` 即為 group_id

#### 3. 更新 .env

```bash
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_GROUP_ID=-100xxxxxxxxxx
```

#### 4. 更新 team.yaml

```yaml
channel:
  bot_token_env: TELEGRAM_BOT_TOKEN
  group_id: -100xxxxxxxxxx
```

### 下一步

完成後告訴 AI：`啟動團隊`（執行 `python start.py`）

### 卡關時

- Bot 沒回應 → 確認 Bot 是群組 Admin
- getUpdates 空的 → 加 Bot 後在群組發一則訊息再重試
- 想跳過 TG → 不設 `channel` 區塊，用 HTTP API 操作
