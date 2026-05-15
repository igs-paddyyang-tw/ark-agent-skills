---
author: paddyyang
name: ark-telegram-notify
description: |
  產出 telegram_notify.py Skill，透過 Telegram Bot API 推送訊息和圖片。
  適用於 Workflow 最後一步推送結果、排程報表推送、異常告警通知。
  使用此 Skill 當使用者提及 Telegram 推送、TG 通知、推播訊息、
  發送報表、告警通知、或任何需要透過 Telegram 推送訊息的場景。
---

# ark-telegram-notify

產出 `src/skills/internal/telegram_notify.py`，透過 Telegram Bot API 推送訊息/圖片，可獨立運作。

## 觸發條件

- 「Telegram 推送」、「TG 通知」、「推播訊息」
- 「發送報表」、「告警通知」
- 「推送到群組」

## 輸入參數

| 參數 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `chat_id` | `str` | ✅ | — | 推送目標 chat_id |
| `message` | `str` | ✅ | — | 訊息內容（支援 Markdown） |
| `image_path` | `str` | ❌ | `None` | 圖片路徑（有則用 sendPhoto） |

## 產出檔案

- `src/skills/internal/telegram_notify.py`

## 產出指引

### 步驟 1：參數模型

```python
class TelegramNotifyParams(SkillParam):
    chat_id: str
    message: str
    image_path: str | None = None
```

### 步驟 2：Skill 類別

```python
class TelegramNotifySkill(BaseSkill):
    skill_id = "telegram_notify"
    skill_type = SkillType.PYTHON
    description = "透過 Telegram Bot API 推送訊息和圖片"
    version = "1.0.0"
    input_schema = TelegramNotifyParams
```

### 步驟 3：execute 方法

```python
async def execute(self, params: dict) -> SkillResult:
    validated = TelegramNotifyParams(**params)
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        return SkillResult(success=True, data={"notify_success": False, "reason": "TELEGRAM_BOT_TOKEN 未設定"})

    try:
        if validated.image_path and Path(validated.image_path).exists():
            await self._send_photo(token, validated)
        else:
            await self._send_message(token, validated)
        return SkillResult(success=True, data={"notify_success": True, "chat_id": validated.chat_id})
    except Exception as e:
        return SkillResult(success=True, data={"notify_success": False, "error": str(e)})
```

### 步驟 4：推送方法

- `_send_message`：POST `sendMessage`，訊息超過 4096 字元自動分段
- `_send_photo`：POST `sendPhoto`，caption 超過 1024 字元時另發 `sendMessage`
- 使用 `httpx.AsyncClient` 呼叫 Telegram Bot API

## Workflow 串接

```yaml
- id: notify
  type: skill
  skill: telegram_notify
  params:
    chat_id: "${NOTIFY_CHAT_ID}"
    message: "{{ outputs.report.content }}"
    image_path: "{{ outputs.chart.chart_path }}"
  output: notify_result
```

## 注意事項

- `TELEGRAM_BOT_TOKEN` 未設定時不報錯，回傳 `notify_success: False`
- 推送失敗記錄日誌，不影響 Workflow 後續步驟
- 訊息超過 4096 字元自動分段發送
- caption 超過 1024 字元時圖片和文字分開發送

## 踩坑紀錄

### Windows 路徑（2026-04-17）

`image_path` 在 Windows 上可能是反斜線路徑（如 `artifacts\charts\chart.png`）。
使用 `Path(image_path).exists()` 可正確處理，但傳給 httpx 的 `open()` 也需要用 `Path`。

```python
# 正確：用 Path 處理跨平台路徑
if p.image_path and Path(p.image_path).exists():
    with open(Path(p.image_path), "rb") as f:
        ...
```
