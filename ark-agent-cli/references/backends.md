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


## 2.4.0：餵法與權限（`agent_common.BACKENDS`）

| backend | prompt 餵法 | read-only | workspace | full | json / usage |
|---|---|---|---|---|---|
| codex | **stdin**（`exec … -`） | `-s read-only` | `-s workspace-write` | `-s danger-full-access` | `--json` 事件流 → `turn.completed.usage` |
| claude | **stdin**（`-p` 無參數） | `--allowedTools Read,Grep,Glob,LS` | `+ Write,Edit,Bash` | `--dangerously-skip-permissions` | `--output-format json` → `usage` / `total_cost_usd` |
| kiro | **prompt 檔**（argv 一行「讀 <path> 並執行」；`ARK_CLI_KIRO_PROMPT=stdin` 可改） | `--trust-tools=fs_read` | `--trust-tools=fs_read,fs_write,execute_bash` | `--trust-all-tools` | 無 usage（記 null） |
| gemini | stdin | `--approval-mode default` | `auto_edit` | `yolo` | `--output-format json` → `stats` |

為什麼不走 argv：Windows CreateProcess 命令列上限 32,767 字元，一段 sub-agent prompt（協定 + task + checkpoint）輕易超過，會 `WinError 206`。`--argv` 旗標只給極短 prompt 除錯。
旗標名以各 CLI 當前版本為準；第一次接真 backend 用 `agent_cli.py -b <x> --access read-only "回 ok"` 探一次，不對就改 `BACKENDS` 表（或 env 覆蓋 cmd）。
