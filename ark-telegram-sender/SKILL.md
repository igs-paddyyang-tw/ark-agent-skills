---
name: ark-telegram-sender
description: |
  通用 Telegram 發送 Skill：文字訊息（HTML 格式）、檔案附件、圖片。
  支援 Forum topic 路由、可指定 Bot Token 環境變數、逸出策略切換、
  長訊息處置（截斷／分段／報錯）、429 依 retry_after 重試。
  失敗一律以回傳值表示、錯誤描述取自 Bot API 的 description（不是「HTTP 400」而已）。
  使用此 skill 當需要「發送 TG 訊息」「推送通知」「傳檔案到 Telegram」
  「發送日報摘要」「告警通知」，或任何需要透過 Bot API 發送內容到指定 chat／topic 的場景。
metadata:
  author: paddyyang
  schema_version: 1
  category: pipeline
  version: "2.0"
  updated: 2026-08-13
  outputs:
    - { format: data, audience: human }
  render: none
  status: active
---

# ark-telegram-sender

Telegram Bot API 發送閘道 — 文字、檔案、圖片三合一。

實作：`scripts/tg_send.py`（零第三方依賴，可當 CLI 也可 import）
送達規範：`references/delivery-sop.md` ← **接日報／報告類長內容前先讀這份**

## 觸發條件

- 「發 TG」「傳到 Telegram」「推送通知」
- 「傳檔案」「send file」「send document」
- 日報 workflow 的 send_message / send_file 步驟
- 告警／監控觸發的通知推送

## 快速使用

```bash
# 文字（走 team.yaml 的 topic 對照，token 也從 team.yaml 的 bot_token_env 解析）
python scripts/tg_send.py text --topic daily_report --file-text summary.txt

# 附件
python scripts/tg_send.py file --topic daily_report \
    --path data/output/market-2026-08-13.html --caption "競品日報 2026-08-13"

# 先看要送什麼，不真送（測試一律用這個）
python scripts/tg_send.py text --chat-id -100123 --text "測試" --dry-run
```

```python
from tg_send import send_text, send_file

r = send_text("📰 <b>日報</b>", topic="daily_report", token_env="TELEGRAM_BOT_TOKEN_GA")
if r["status"] != "success":      # ← 失敗以回傳值表示，這行不能省
    log.error("推送失敗: %s", r["message"])
```

## 三個容易漏掉的地方

| # | 事情 | 漏掉的後果 |
|---|------|-----------|
| 1 | **Forum topic** 要 `message_thread_id` | 訊息安靜地全發到 General 區 |
| 2 | **失敗以回傳值表示**，不拋例外 | 只包 try/except 會把失敗當成功（ninja D27：連續三天回報出刊成功，實際一則都沒送出） |
| 3 | **錯誤描述取自 response body** | 只讀例外字串得到「HTTP Error 400: Bad Request」，看不出是標籤沒閉合還是 topic 不存在 |

## 參數

### 共用

| 參數 | 說明 |
|------|------|
| `topic` | `team.yaml` 的 `topics` key（如 `daily_report`）。topic 名稱只維護一份，不要硬編數字 |
| `chat_id` / `thread_id` | 直接指定，優先於 `topic` |
| `token_env` | Bot Token 的環境變數名。未指定時依序試 `team.yaml` 的 `channel.bot_token_env` → `TELEGRAM_BOT_TOKEN`（**ninja 用的是 `TELEGRAM_BOT_TOKEN_GA`**） |
| `team_yaml` | 設定檔路徑，預設由 cwd 逐層往上找 |
| `dry_run` | 只回傳將送出的內容（chat/thread/長度/預覽），不呼叫 API |

### 文字

| 參數 | 預設 | 說明 |
|------|------|------|
| `parse_mode` | `HTML` | `HTML` / `Markdown` / `MarkdownV2` / `plain` |
| `escape` | `auto` | `auto`（內容含 TG 標籤就不逸出）/ `always` / `never`。決策樹見 SOP §3 |
| `on_overflow` | `truncate` | 超過 4000 字的處置：`truncate`（截到邊界 + 附註）/ `split`（切多則）/ `error` |
| `disable_preview` | `True` | 關閉連結預覽 |
| `reply_markup` | — | inline keyboard；多則時掛在最後一則，否則會被後續訊息推走 |

### 檔案／圖片

| 參數 | 說明 |
|------|------|
| `path` | 檔案路徑。超過 50 MB 直接回錯誤（Bot API 上限，不是換參數能解） |
| `caption` | 說明文字，超過 1024 字自動截斷（整則會被拒） |

## 回傳格式

```json
{"status": "success", "message_id": 2429, "method": "sendMessage", "parts": 1}
{"status": "error", "message": "HTTP 400: Bad Request: can't parse entities: Can't find end tag corresponding to start tag \"b\"", "http_status": 400}
{"status": "dry_run", "chat_id": -100123, "message_thread_id": 2, "parts": 1, "chars": [842]}
```

`status` 只有這三種。重試策略：逾時與 5xx 指數退避 3 次、429 依 `retry_after` 等待、
**4xx 不重試**（內容問題，重試幾次都一樣）。

## 長內容的正確送法

```
① 文字摘要（截斷，標明「其餘 N 則見附件」）
② HTML 附件（完整版）
```

不要把長內容硬切成多則文字訊息 —— 會洗版，讀者也拼不回來。完整理由見 SOP §1。

## Workflow 串接

```yaml
- id: send_message
  skill: ark-telegram-sender
  params:
    topic: daily_report
    text: "{{ outputs.build_summary.text }}"
    escape: never          # 內容由渲染層產生，已自行逸出
    on_overflow: truncate

- id: send_file
  skill: ark-telegram-sender
  params:
    topic: daily_report
    file_path: "{{ outputs.render.path }}"
    caption: "📅 完整報告"
```

## 測試

**絕不真送**：一律 `--dry-run` 或注入假發送函式。驗收真送時送到通報區（`ops_alert`）
而非日報區，並在內容標明是測試。理由見 SOP §7。

## 相關

| Skill | 關係 |
|-------|------|
| ark-daily-news | 日報的兩段式送達使用本 skill |
| ark-html-report | 產出的 HTML 走本 skill 的檔案附件（附件常離線開啟，該端需零外部請求） |
| ark-md-report | 報告 MD 轉 HTML 後同上 |
