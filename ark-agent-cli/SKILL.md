---
name: ark-agent-cli
description: |
  統一 Agent CLI 閘道：封裝 kiro-cli / claude / gemini / codex 四種 CLI 為單一呼叫介面。
  支援三種使用方式：Python import、HTTP API（OpenAI-compatible）、CLI 腳本。
  使用此 skill 當使用者需要「呼叫 agent」「問 claude/kiro/gemini」「CLI 對話」
  「統一 LLM 後端呼叫」「多模型切換」、或需要從命令列直接測試 agent 回覆時。
  取代 ark-llm-cli 的定位，提供更完整的多 backend 支援與輸出清理。
metadata:
  author: paddyyang
  schema_version: 1
  category: pipeline
  outputs:
    - { format: data, audience: ai }
  render: none
  status: active
  replaces: [ark-llm-cli]
---

# ark-agent-cli

統一 Agent CLI 閘道 — 四種 CLI 後端、三種使用方式、一個核心。

## 觸發條件

- 「呼叫 agent」「問一下 claude/kiro/gemini」「用 CLI 問」
- 「統一 LLM 呼叫」「多 backend」「切換模型」
- 「從命令列測試 agent」「跑一下 kiro」「問 codex」
- 需要從 Python 程式碼呼叫任意 CLI agent 取得回覆

## 架構

```
┌─────────────────────────────────────────┐
│           ark-agent-cli                  │
├─────────┬──────────────┬────────────────┤
│ Python  │  HTTP API    │  CLI 腳本      │
│ import  │  (Gateway)   │  直接執行      │
└────┬────┴──────┬───────┴───────┬────────┘
     └───────────┼───────────────┘
                 ▼
     ┌───────────────────────┐
     │     core（統一核心）    │
     │  ┌────┐┌──────┐┌────┐│
     │  │kiro││claude││gemi││
     │  └────┘└──────┘└────┘│
     │  ┌─────┐             │
     │  │codex│             │
     │  └─────┘             │
     │  清理 · 超時 · 重試   │
     └───────────────────────┘
```

## 支援的 Backend

| Backend | CLI 工具 | 特色 | 環境變數 |
|---------|---------|------|---------|
| `kiro` | kiro-cli | 11 模型 + rate_multiplier、Agent 機制、--resume 續接 | `ARK_CLI_KIRO_CMD` / `KIRO_CLI_PATH` |
| `claude` | claude (Claude Code) | --output-format json、--json-schema、--tools ""、--max-budget-usd | `ARK_CLI_CLAUDE_CMD` / `CLAUDE_CLI_CMD` |
| `gemini` | gemini-cli | --output-format json、--approval-mode yolo、YOLO 免確認 | `ARK_CLI_GEMINI_CMD` / `GEMINI_CLI_CMD` |
| `codex` | codex-cli | 三級沙箱（read-only/workspace-write/full）、-o FILE 乾淨輸出 | `ARK_CLI_CODEX_CMD` / `CODEX_CLI_CMD` |

## 三種使用方式

### 1. Python import

```python
from src.skills.internal.ark_agent_cli import ArkAgentCli

# 基本呼叫
result = await ArkAgentCli.call("kiro", "幫我分析這段程式碼", model="auto")
print(result.text)      # 清理後的回覆
print(result.elapsed_ms)  # 延遲 ms

# Claude 省 token 模式
result = await ArkAgentCli.call(
    backend="claude",
    prompt="分析需求並產出 TaskPlan JSON",
    model="haiku",
    json_output=True,
    lean=True,          # --tools "" --effort low（省 97% input）
    timeout=120,
)
print(result.json_data)  # 解析後的 dict

# Gemini JSON 輸出
result = await ArkAgentCli.call("gemini", "分類意圖", json_output=True)

# model spec 格式
backend, model = ArkAgentCli.parse_model_spec("claude/haiku")  # ("claude", "haiku")
```

### 2. HTTP API（Gateway :8642）

```bash
# OpenAI-compatible 格式，model 用 "backend/model_name"
curl -X POST http://localhost:8642/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude/haiku",
    "messages": [
      {"role": "system", "content": "你是分析助手"},
      {"role": "user", "content": "分析這段程式碼的效能瓶頸"}
    ]
  }'

# model 格式範例：
#   "kiro/auto"       → kiro-cli --model auto
#   "claude/opus"     → claude -p --model opus
#   "gemini/flash"    → gemini --prompt -m gemini-3.6-flash
#   "codex/gpt-4.1"  → codex exec
```

### 3. CLI 腳本

```bash
# 基本使用
python -m src.skills.internal.ark_agent_cli "你的問題"

# 指定 backend 和 model
python -m src.skills.internal.ark_agent_cli -b claude -m haiku "分析需求"

# 省 token 模式
python -m src.skills.internal.ark_agent_cli -b claude --lean "分類意圖"

# JSON 輸出
python -m src.skills.internal.ark_agent_cli -b gemini --json "結構化這段文字"

# 指定工作目錄
python -m src.skills.internal.ark_agent_cli -b kiro --cwd agents/dev-agent "修復 bug"

# verbose（顯示延遲）
python -m src.skills.internal.ark_agent_cli -b kiro -v "1+1"

# 從 stdin 讀取
echo "分析這段 log" | python -m src.skills.internal.ark_agent_cli -b claude
```

## 核心設計原則

### 輸出清理（所有 backend 統一）

```
移除：ANSI escape codes、OSC 序列、"> " 前綴、
      "▸ Time:" 行、"All tools are now trusted" 行
```

CLI 的 exit code **不可靠**（有 stdout 就算成功），輸出清理是必要步驟。

### 超時處理

- 預設 300 秒（env `ARK_CLI_TIMEOUT`）
- 超時後回傳 `CliResult(success=False, timed_out=True, text="[TIMEOUT]")`
- 進程被 kill

### JSON 解析

`json_output=True` 時，自動嘗試：
1. 直接 `json.loads(text)`
2. 從 ```json code block 提取
3. 失敗則 `json_data=None`，text 仍有原始文字

### model spec 解析

```
"backend/model" → (backend, model)
"kiro/auto"     → ("kiro", "auto")
"claude/haiku"  → ("claude", "haiku")
"auto"          → ("kiro", "auto")    # 無 / 時預設 kiro
```

## CliResult 回傳結構

```python
@dataclass
class CliResult:
    success: bool          # 有輸出 = True
    text: str              # 清理後的回覆文字
    backend: str           # 使用的 backend
    model: str             # 使用的 model
    elapsed_ms: int        # 延遲毫秒
    raw_stdout: str        # 原始 stdout（debug 用）
    raw_stderr: str        # 原始 stderr（debug 用）
    timed_out: bool        # 是否超時
    json_data: dict | None # json_output=True 時解析結果
```

## 環境變數

| 變數 | 預設 | 說明 |
|------|------|------|
| `ARK_CLI_KIRO_CMD` | fallback `KIRO_CLI_PATH` → `kiro-cli` | Kiro CLI 路徑 |
| `ARK_CLI_CLAUDE_CMD` | fallback `CLAUDE_CLI_CMD` → `claude` | Claude CLI 路徑 |
| `ARK_CLI_GEMINI_CMD` | fallback `GEMINI_CLI_CMD` → `gemini` | Gemini CLI 路徑 |
| `ARK_CLI_CODEX_CMD` | fallback `CODEX_CLI_CMD` → `codex` | Codex CLI 路徑 |
| `ARK_CLI_DEFAULT_BACKEND` | `kiro` | 預設 backend |
| `ARK_CLI_TIMEOUT` | `300` | 全域超時秒數 |

## 與 ark-llm-cli 的差異

| | ark-llm-cli | ark-agent-cli |
|---|---|---|
| Backend 數 | 4（相同） | 4（相同） |
| 統一核心 | ❌ 各 backend 獨立邏輯 | ✅ 單一 `ArkAgentCli.call()` |
| HTTP API | ❌ 無 | ✅ Gateway OpenAI-compatible |
| CLI 腳本 | ❌ 無 | ✅ `python -m ...` |
| 輸出清理 | 基本（ANSI + 前綴） | 完整（ANSI + OSC + 前綴 + 噪音行） |
| JSON 解析 | ❌ 手動 | ✅ 自動（code block 提取） |
| lean 模式 | ❌ 無 | ✅ Claude --tools "" 省 97% |
| model spec | ❌ 無 | ✅ "backend/model" 格式 |

**結論：ark-agent-cli 完全取代 ark-llm-cli。**
