# backend 對照（one-shot 旗標與環境變數）

## 支援的 Backend

| Backend | CLI 工具 | 特色 | 環境變數 |
|---------|---------|------|---------|
| `kiro` | kiro-cli | 11 模型 + rate_multiplier、Agent 機制、--resume 續接 | `ARK_CLI_KIRO_CMD` / `KIRO_CLI_PATH` |
| `claude` | claude (Claude Code) | --output-format json、--json-schema、--tools ""、--max-budget-usd | `ARK_CLI_CLAUDE_CMD` / `CLAUDE_CLI_CMD` |
| `gemini` | gemini-cli | --output-format json、--approval-mode yolo、YOLO 免確認 | `ARK_CLI_GEMINI_CMD` / `GEMINI_CLI_CMD` |
| `codex` | codex-cli | 三級沙箱（read-only/workspace-write/full）、-o FILE 乾淨輸出 | `ARK_CLI_CODEX_CMD` / `CODEX_CLI_CMD` |


## 環境變數

| 變數 | 預設 | 說明 |
|------|------|------|
| `ARK_CLI_KIRO_CMD` | fallback `KIRO_CLI_PATH` → `kiro-cli` | Kiro CLI 路徑 |
| `ARK_CLI_CLAUDE_CMD` | fallback `CLAUDE_CLI_CMD` → `claude` | Claude CLI 路徑 |
| `ARK_CLI_GEMINI_CMD` | fallback `GEMINI_CLI_CMD` → `gemini` | Gemini CLI 路徑 |
| `ARK_CLI_CODEX_CMD` | fallback `CODEX_CLI_CMD` → `codex` | Codex CLI 路徑 |
| `ARK_CLI_DEFAULT_BACKEND` | `kiro` | 預設 backend |
| `ARK_CLI_TIMEOUT` | `300` | 全域超時秒數 |


## 本 skill 的 argv 組法

見 `scripts/agent_common.py` 的 `BACKENDS` 表：`args`（one-shot 固定參數）、`model`、`json`、`resume`、`agent` 旗標模板；`prompt` 走 argv 或 stdin。`fake` backend 只給測試與 dry-run。
