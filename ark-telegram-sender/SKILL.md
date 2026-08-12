---
name: ark-telegram-sender
description: |
  通用 Telegram 訊息發送 Skill：文字訊息（HTML 格式）、檔案附件、圖片。
  自動處理長訊息分段（4000 字上限）、重試機制、parse_mode 切換。
  使用此 skill 當需要「發送 TG 訊息」「推送通知」「傳檔案到 Telegram」
  「發送日報摘要」「告警通知」，或任何需要透過 Bot API 發送內容到指定 chat 的場景。
metadata:
  schema_version: 1
  status: active
  author: paddyyang
  category: pipeline
  outputs:
    - { format: data, audience: human }
---

# ark-telegram-sender

通用 Telegram Bot API 發送工具 — 文字、檔案、圖片三合一。

## 觸發條件

- 「發 TG」「傳到 Telegram」「推送通知」
- 「傳檔案」「send file」「send document」
- 日報 workflow 的 send_message / send_file 步驟
- 告警/監控觸發的通知推送

## 功能

### 1. 文字訊息

```python
params = {
    "chat_id": "937896656",
    "text": "📡 <b>科技日報</b>\n今日精選 5 則",
    "parse_mode": "HTML",  # HTML | Markdown | plain
}
```

特性：
- 超過 4000 字自動分段（按段落切割，不切斷 HTML 標籤）
- 分段間延遲 0.5 秒（避免 rate limit）
- `disable_web_page_preview: True`（預設不展開連結預覽）

### 2. 檔案附件

```python
params = {
    "chat_id": "937896656",
    "file_path": "output/tech-daily-2026-08-12.html",
    "caption": "📅 科技日報",
}
```

特性：
- 支援任意檔案格式
- 3 次重試 + 60 秒 timeout
- caption 可選

### 3. 圖片

```python
params = {
    "chat_id": "937896656",
    "photo_path": "artifacts/charts/kpi.png",
    "caption": "KPI 日報圖表",
}
```

## 輸入參數

| 參數 | 型別 | 必要 | 說明 |
|------|------|------|------|
| `chat_id` | str | ❌ | TG chat ID（預設從 env TELEGRAM_CHAT_ID） |
| `text` | str | ❌ | 文字訊息（與 file_path 二擇一） |
| `file_path` | str | ❌ | 檔案路徑 |
| `photo_path` | str | ❌ | 圖片路徑 |
| `caption` | str | ❌ | 檔案/圖片的說明文字 |
| `parse_mode` | str | ❌ | HTML（預設）/ Markdown / plain |

## 環境變數

| 變數 | 說明 |
|------|------|
| `TELEGRAM_BOT_TOKEN` | Bot Token（必填） |
| `TELEGRAM_CHAT_ID` | 預設 chat ID |

## 錯誤處理

- Bot Token 未設定 → 回傳 error（不拋出）
- TG API 回傳非 200 → raise + 日誌
- 網路逾時 → 重試最多 3 次

## Workflow 串接

```yaml
- id: send_message
  skill: ark-telegram-sender
  params:
    chat_id: "${TELEGRAM_CHAT_ID}"
    text: "{{ outputs.build_summary.text }}"
    parse_mode: "HTML"

- id: send_file
  skill: ark-telegram-sender
  params:
    chat_id: "${TELEGRAM_CHAT_ID}"
    file_path: "{{ outputs.render.path }}"
    caption: "📅 完整報告"
```
