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
| codex | **stdin**（`exec … -`） | `-s read-only` | `-s workspace-write` | `-s danger-full-access` | `--json` 事件流：回覆＝最後一個 `item.completed`／`agent_message.text`、用量＝`turn.completed.usage`（2.4.3 實測 0.146） |
| claude | **stdin**（`-p` 無參數） | `--allowedTools Read,Grep,Glob,LS` | `+ Write,Edit,Bash` | `--dangerously-skip-permissions` | `--output-format json` → `usage` / `total_cost_usd` |
| kiro | **prompt 檔**（argv 一行「讀 <path> 並執行」；`ARK_CLI_KIRO_PROMPT=stdin` 可改） | `--trust-tools=fs_read,read_file,list_directory,file_search,grep_search`（2.4.4：新舊名並列） | 唯讀 ＋ `fs_write,str_replace,fs_append,execute_bash`（⚠️ kiro 2.34 非互動不放行 shell） | `--trust-all-tools` | 無 usage（記 null） |
| gemini | stdin（加 `--skip-trust`：headless 未信任目錄會 exit 55） | `--approval-mode default` | `auto_edit` | `yolo` | `--output-format json`：回覆＝`response`、用量＝`stats.models.<model>.tokens` 加總（2.4.3 實測 0.53） |

**kiro 2.34 實測（2.4.4，2026-11-02）**：內建工具改名（讀檔 `read_file`）；只信任舊名 `fs_read` 時，讀工作區外的檔（背景 job 的 prompt 檔）會被擋。`execute_bash` 列在 `--trust-tools` 仍被擋（只有 `--trust-all-tools` 放行）。另：`--agent <name>` 指向的 agent.json 沒宣告 `tools` 時，非互動模式只有 MCP 工具、沒有內建讀檔工具 —— 背景 job 用 kiro 時要嘛不帶 `--agent`，要嘛 agent.json 宣告 tools。

為什麼不走 argv：Windows CreateProcess 命令列上限 32,767 字元，一段 sub-agent prompt（協定 + task + checkpoint）輕易超過，會 `WinError 206`。`--argv` 旗標只給極短 prompt 除錯。
旗標名以各 CLI 當前版本為準；第一次接真 backend 用 `agent_cli.py -b <x> --access read-only "回 ok"` 探一次，不對就改 `BACKENDS` 表（或 env 覆蓋 cmd）。
