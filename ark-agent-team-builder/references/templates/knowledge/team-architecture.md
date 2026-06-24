---
title: "團隊系統架構"
type: concept
tags: [architecture, system, daemon, mcp]
created: {{TODAY}}
updated: {{TODAY}}
status: mature
---

# 團隊系統架構

## 核心元件

| 元件 | 職責 | 通訊方式 |
|------|------|----------|
| Daemon | Agent 生命週期管理（啟動/停止/重啟/健康監控） | asyncio subprocess |
| API Server | HTTP 端點，MCP 工具的接收端 | FastAPI :13030 |
| MCP Server | 每個 agent 的工具介面（stdio JSON-RPC） | stdin/stdout |
| Scheduler | Cron 排程引擎 | HTTP → API |
| TelegramAdapter | 使用者介面（Telegram Bot） | python-telegram-bot |

## 資料流

```
使用者訊息 → TelegramAdapter → Daemon.send_message → Agent stdin
Agent 回覆 → MCP reply() → HTTP POST /reply → TelegramAdapter → 使用者
Agent 跨組通訊 → MCP send_to_instance() → HTTP POST /send/{target} → 目標 Agent stdin
排程觸發 → Scheduler → HTTP POST /send/{target} → 目標 Agent stdin
```

## 關鍵設定檔

| 檔案 | 用途 |
|------|------|
| team.yaml | 團隊配置（instances、channel、cost_guard、hang_detector） |
| scheduler.yaml | 排程定義（jobs + cron） |
| .env | 環境變數（Token、API Key） |
| .kiro/settings/mcp.json | 每個 agent 的 MCP server 配置 |

## 啟動順序

1. 讀取 team.yaml → 建構 TeamConfig
2. 為每個 instance 寫入 .kiro/ 配置
3. 啟動 FastAPI（HTTP API）
4. 逐一啟動 kiro-cli subprocess（stagger 2s）
5. 啟動 TelegramAdapter（polling）
6. 啟動 Scheduler（cron jobs）
7. 進入 health loop（每 30s 檢查一次）

## Agent 生命週期

```
STOPPED → STARTING → RUNNING → (CRASHED → STARTING)
                         ↓
                      PAUSED（cost_guard 熔斷）
```

## 端口規劃

| Port | 用途 | 說明 |
|------|------|------|
| 13030 | 第一個團隊 API | 預設 |
| 23030 | 第二個團隊 API | 避免衝突 |
| 33030 | 第三個團隊 API | 依此類推 |
