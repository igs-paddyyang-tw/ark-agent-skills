---
title: "常見問題排除"
type: concept
tags: [troubleshooting, debug, faq, errors]
created: {{TODAY}}
updated: {{TODAY}}
status: mature
---

# 常見問題排除

## 啟動失敗

### kiro-cli 找不到

**症狀：** `FileNotFoundError: 找不到 kiro-cli`

**解法：**
1. 確認 kiro-cli 已安裝：`kiro-cli --version`
2. 設定環境變數：`KIRO_CLI_PATH=C:\Users\{user}\AppData\Local\Kiro-Cli\kiro-cli.exe`
3. 或加入 PATH

### team.yaml not found

**症狀：** `FileNotFoundError: team.yaml`

**解法：**
1. 確認在正確目錄執行 `python start.py`
2. 或設定 `ARK_TEAM_AGENT_HOME` 環境變數指向專案根目錄

### Telegram Bot 啟動失敗

**症狀：** `telegram.error.InvalidToken`

**解法：**
1. 確認 `.env` 中 `TELEGRAM_BOT_TOKEN` 正確
2. 確認 Token 未過期（向 @BotFather 確認）
3. 確認網路可連接 Telegram API

### Port 衝突

**症狀：** `OSError: [Errno 98] Address already in use`

**解法：**
1. 確認沒有其他團隊佔用同一 port
2. 修改 `team.yaml` 的 `health_port`（每個團隊用不同 port）
3. 常用配置：第一團隊 13030、第二團隊 23030

---

## MCP 通訊問題

### Agent 收不到訊息

**可能原因：**
1. Agent subprocess 已 crash（`query_team_status()` 確認）
2. 目標 instance name 拼錯（case-sensitive）
3. HTTP API 未啟動（port 未開）

**排查步驟：**
```
1. query_team_status() → 確認目標 agent 狀態
2. 檢查 logs/team.log → 找 HTTP 錯誤
3. 重啟目標 agent
```

### reply 沒有送到 Telegram

**可能原因：**
1. admin 的 `private_chat` 未設定正確的 Telegram user ID
2. Bot 未被使用者 `/start`
3. 4096 字元超限

**解法：**
1. 確認 `team.yaml` admin 的 `private_chat` = 你的 Telegram ID
2. 在 Telegram 對 Bot 發送 `/start`
3. reply 內容控制在 150 字以內

### MCP tool 呼叫失敗

**症狀：** `HTTP Error 404` 或 `Connection refused`

**解法：**
1. 確認 API server 正在運行：`curl http://localhost:13030/health`
2. 確認 `.kiro/settings/mcp.json` 中 port 正確
3. 重啟整個團隊

---

## Agent 異常

### Agent 持續 crash

**可能原因：**
1. .kiro/ 配置損壞
2. MCP server 連線失敗
3. 記憶體不足

**解法：**
1. 刪除 agent 的 `.kiro/` 目錄，讓 daemon 重新產出
2. 確認 MCP server 路徑正確
3. 減少同時運行的 agent 數量

### Agent 無回應（Hang）

**症狀：** agent 狀態 running 但不回覆

**解法：**
1. `hang_detector` 會在 `timeout_minutes` 後通知
2. 手動重啟：寫入 `restart.flag` 或用 API
3. 檢查 agent 是否卡在等待使用者確認（應有 --trust-all-tools）

### 訊息遺失

**可能原因：**
1. backpressure：佇列滿了（maxsize=50）
2. agent crash 時佇列中的訊息丟失
3. 網路中斷

**解法：**
1. 升級到 Stage 2 獲得 message_overflow 持久化
2. 減少同時派工的數量
3. 確認網路穩定

---

## 排程問題

### Cron job 沒有觸發

**檢查清單：**
1. scheduler.yaml 語法正確（`cron: "0 9 * * *"`）
2. timezone 設定正確（Asia/Taipei）
3. job 的 `enabled: true`
4. target agent 正在 running

### 排程重複觸發

**原因：** 多個 start.py 進程同時運行

**解法：**
1. 確保只有一個 start.py / watchdog 進程
2. 用 `start-team.bat` / `.sh` 統一管理
3. 檢查是否有多個 Bot polling（`Conflict: terminated by other getUpdates request`）

---

## 快速診斷指令

```bash
# 確認服務健康
curl http://localhost:13030/health

# 查看所有 agent 狀態
curl http://localhost:13030/status

# 查看日誌
tail -f logs/team.log

# 強制重啟
echo "" > restart.flag
```
