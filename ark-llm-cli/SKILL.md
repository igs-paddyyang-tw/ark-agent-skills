---
name: ark-llm-cli
author: paddyyang
description: |
  統一封裝多個 LLM CLI Agent 為標準化 Skill，支援 Gemini CLI、Kiro CLI、Claude CLI、Antigravity CLI。
  提供非互動模式對話、程式碼產出、Skill CodeGen、需求評估。
  自動偵測可用 CLI 並建立 fallback chain。
  使用此 Skill 當使用者提及 LLM CLI、Gemini CLI、Kiro CLI、Claude CLI、Antigravity CLI、
  CLI agent、codegen、用 CLI 產出程式碼、產出 Skill、自動寫 Skill、
  或任何需要呼叫 LLM CLI 工具的場景。
metadata:
  version: "2.0"
  updated: 2026-05-23
---

# ark-llm-cli

統一封裝多個 LLM CLI Agent — 對話、CodeGen、Skill 產出、需求評估。

## 觸發條件

- 「LLM CLI」、「Gemini CLI」、「Kiro CLI」、「Claude CLI」、「Antigravity CLI」
- 「CLI agent」、「codegen」、「用 CLI 產出程式碼」
- 「產出 Skill」、「自動寫 Skill」
- 「ag chat」、「claude -p」、「gemini -p」、「kiro-cli chat」
- 「封裝 Gemini CLI」、「封裝 LLM」、「Gemini CLI Skill」、「LLM 封裝」

---

## 支援的 CLI 後端

| Backend | 指令 | 特色 | 延遲 | 環境變數 |
|---------|------|------|------|---------|
| gemini | `gemini -p` | CodeGen、工具呼叫、快速 | 5-30s | `GEMINI_API_KEY` |
| kiro | `kiro-cli chat --no-interactive` | 完整 Agent + MCP + Skill | 30-120s | — |
| claude | `claude -p --output-format text` | 強推理、長文、精確 | 10-60s | `ANTHROPIC_API_KEY` |
| antigravity | `ag chat -m` | Go binary、輕量、本地 | 5-20s | — |

### Fallback Chain

根據 `backend` 參數和可用性自動降級：

```
指定 backend 可用 → 使用指定
指定 backend 不可用 → gemini → claude → antigravity → 報錯
```

---

## 輸入參數

| 參數 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `prompt` | `str` | ✅ | — | 提示詞 |
| `mode` | `str` | ❌ | `"chat"` | 模式：chat / codegen / skill_gen / evaluate |
| `backend` | `str` | ❌ | `"gemini"` | 後端：gemini / kiro / claude / antigravity |
| `model` | `str` | ❌ | `""` | 模型（空則用後端預設） |
| `system_prompt` | `str` | ❌ | `""` | 系統提示詞 |
| `timeout` | `int` | ❌ | `120` | 超時秒數 |
| `output_path` | `str` | ❌ | `""` | codegen/skill_gen 輸出路徑 |
| `skill_id` | `str` | ❌ | `""` | skill_gen 時的 Skill ID |

---

## 各後端預設模型

| Backend | 預設模型 |
|---------|---------|
| gemini | `gemini-2.5-flash` |
| kiro | `auto`（由 Kiro 決定） |
| claude | `claude-sonnet-4-20250514` |
| antigravity | `claude-sonnet-4-20250514` |

---

## 產出檔案

- `src/skills/internal/llm_cli.py`

---

## 產出指引

### 步驟 1：參數模型

```python
from src.skills.base import SkillParam

class LlmCliParams(SkillParam):
    """llm_cli 輸入參數。"""
    prompt: str
    mode: str = "chat"          # chat / codegen / skill_gen / evaluate
    backend: str = "gemini"     # gemini / kiro / claude / antigravity
    model: str = ""
    system_prompt: str = ""
    timeout: int = 120
    output_path: str = ""
    skill_id: str = ""
```

### 步驟 2：Skill 類別

```python
class LlmCliSkill(BaseSkill):
    skill_id = "llm_cli"
    skill_type = SkillType.PYTHON
    description = "統一 LLM CLI 封裝 — 支援 Gemini/Kiro/Claude/Antigravity"
    version = "2.0.0"
    input_schema = LlmCliParams
```

### 步驟 3：Backend 定義

```python
import os

BACKENDS = {
    "gemini": {
        "cmd": os.getenv("GEMINI_CLI_CMD", "gemini.cmd" if os.name == "nt" else "gemini"),
        "default_model": "gemini-2.5-flash",
        "build_args": lambda prompt, model, **kw: [
            kw["cmd"], "-p", prompt, "-m", model, "--skip-trust",
        ],
        "env_extra": {"GEMINI_CLI_TRUST_WORKSPACE": "true"},
    },
    "kiro": {
        "cmd": os.getenv("KIRO_CLI_CMD", "kiro-cli"),
        "default_model": "auto",
        "build_args": lambda prompt, model, **kw: [
            kw["cmd"], "chat", "--no-interactive", "--message", prompt,
        ],
        "env_extra": {},
        "default_timeout": 120,
    },
    "claude": {
        "cmd": os.getenv("CLAUDE_CLI_CMD", "claude"),
        "default_model": "claude-sonnet-4-20250514",
        "build_args": lambda prompt, model, **kw: [
            kw["cmd"], "-p", prompt, "-m", model, "--output-format", "text",
        ],
        "env_extra": {},
    },
    "antigravity": {
        "cmd": os.getenv("AG_CLI_CMD", "ag"),
        "default_model": "claude-sonnet-4-20250514",
        "build_args": lambda prompt, model, **kw: [
            kw["cmd"], "chat", "-m", model, "--message", prompt,
        ],
        "env_extra": {},
    },
}
```

### 步驟 4：可用性檢查

```python
_availability_cache: dict[str, bool] = {}

async def is_available(backend: str) -> bool:
    """檢查 CLI 是否已安裝（結果快取）。"""
    if backend in _availability_cache:
        return _availability_cache[backend]
    cmd = BACKENDS[backend]["cmd"]
    try:
        proc = await asyncio.create_subprocess_exec(
            cmd, "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(proc.communicate(), timeout=10)
        available = proc.returncode == 0
    except (FileNotFoundError, asyncio.TimeoutError):
        available = False
    _availability_cache[backend] = available
    return available
```

### 步驟 5：Fallback Chain

```python
FALLBACK_ORDER = ["gemini", "claude", "antigravity"]

async def _resolve_backend(self, preferred: str) -> str | None:
    """解析可用後端，不可用時依 fallback chain 降級。"""
    if await is_available(preferred):
        return preferred
    for b in FALLBACK_ORDER:
        if b != preferred and await is_available(b):
            return b
    return None
```

### 步驟 6：execute 主流程

```python
async def execute(self, params: dict) -> SkillResult:
    p = LlmCliParams(**params)
    backend = await self._resolve_backend(p.backend)
    if not backend:
        return SkillResult(success=False, error="無可用 CLI 後端")

    if p.mode == "chat":
        return await self._chat(p, backend)
    elif p.mode == "codegen":
        return await self._codegen(p, backend)
    elif p.mode == "skill_gen":
        return await self._skill_gen(p, backend)
    elif p.mode == "evaluate":
        return await self._evaluate(p, backend)
    else:
        return SkillResult(success=False, error=f"不支援的模式: {p.mode}")
```

### 步驟 7：通用 CLI 執行

```python
async def _run_cli(self, prompt: str, backend: str, model: str, timeout: int) -> tuple[str, str, int]:
    """執行 CLI，回傳 (stdout, stderr, returncode)。"""
    cfg = BACKENDS[backend]
    cmd = cfg["cmd"]
    m = model or cfg["default_model"]
    args = cfg["build_args"](prompt, m, cmd=cmd)
    env = os.environ.copy()
    env.update(cfg.get("env_extra", {}))

    import tempfile
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        cwd=tempfile.gettempdir(),
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    return (
        stdout.decode("utf-8").strip() if stdout else "",
        stderr.decode("utf-8").strip() if stderr else "",
        process.returncode,
    )
```

---

## 四種模式

### chat — 純對話

```python
async def _chat(self, p, backend):
    prompt = f"{p.system_prompt}\n\n{p.prompt}" if p.system_prompt else p.prompt
    out, err, code = await self._run_cli(prompt, backend, p.model, p.timeout)
    if code != 0:
        return SkillResult(success=False, error=f"CLI 失敗 (code {code}): {err[:300]}")
    return SkillResult(success=True, data={"output": out, "backend": backend, "model": p.model or BACKENDS[backend]["default_model"]})
```

### codegen — 產出程式碼

```python
async def _codegen(self, p, backend):
    prompt = f"只輸出程式碼，不要解釋：\n{p.prompt}"
    out, err, code = await self._run_cli(prompt, backend, p.model, p.timeout)
    if code != 0:
        return SkillResult(success=False, error=f"CLI 失敗: {err[:300]}")
    extracted = self._extract_code(out)
    if p.output_path:
        Path(p.output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(p.output_path).write_text(extracted, encoding="utf-8")
    return SkillResult(success=True, data={"code": extracted, "path": p.output_path, "backend": backend})
```

### skill_gen — 產出 BaseSkill

```python
async def _skill_gen(self, p, backend):
    skill_id = p.skill_id or "new_skill"
    prompt = f"""根據以下需求產出 Python Skill：
- 繼承 BaseSkill（from src.skills.base import BaseSkill, SkillParam, SkillResult, SkillType）
- 實作 async def execute(self, params: dict) -> SkillResult
- skill_id = "{skill_id}"
- Docstring 繁體中文
- Python 3.12 語法
需求：{p.prompt}
只輸出程式碼。"""
    out, err, code = await self._run_cli(prompt, backend, p.model, p.timeout)
    if code != 0:
        return SkillResult(success=False, error=f"CLI 失敗: {err[:300]}")
    extracted = self._extract_code(out)
    output_path = p.output_path or f"src/skills/internal/{skill_id}.py"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(extracted, encoding="utf-8")
    return SkillResult(success=True, data={"skill_id": skill_id, "path": output_path, "backend": backend})
```

### evaluate — 評估需求

```python
async def _evaluate(self, p, backend):
    prompt = f"""分析用戶需求，回傳 JSON（不要其他文字）：
{{"action": "answer|invoke|generate", "skill_id": "...", "params": {{}}, "reason": "..."}}
需求：{p.prompt}"""
    out, err, code = await self._run_cli(prompt, backend, p.model, p.timeout)
    if code != 0:
        return SkillResult(success=False, error=f"CLI 失敗: {err[:300]}")
    parsed = self._extract_json(out)
    return SkillResult(success=True, data={"evaluation": parsed, "raw": out, "backend": backend})
```

---

## 輸出解析（共用）

```python
def _extract_code(self, output: str) -> str:
    """從 CLI 輸出提取程式碼區塊。"""
    import re
    match = re.search(r"```(?:python)?\n(.*?)```", output, re.DOTALL)
    return match.group(1).strip() if match else output

def _extract_json(self, output: str) -> dict:
    """從 CLI 輸出提取 JSON。"""
    import json, re
    match = re.search(r"\{.*\}", output, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return {}
```

---

## 各 CLI 安裝方式

| CLI | 安裝指令 | 驗證 |
|-----|---------|------|
| Gemini | `npm install -g @google/gemini-cli` | `gemini --version` |
| Kiro | `npm install -g kiro-cli` | `kiro-cli --version` |
| Claude | `npm install -g @anthropic-ai/claude-code` | `claude --version` |
| Antigravity | Go binary 下載 | `ag --version` |

---

## 環境變數

```bash
# CLI 路徑覆寫（選填）
GEMINI_CLI_CMD=gemini
KIRO_CLI_CMD=kiro-cli
CLAUDE_CLI_CMD=claude
AG_CLI_CMD=ag

# API Keys
GEMINI_API_KEY=your_key
ANTHROPIC_API_KEY=your_key
```

---

## Kiro CLI 特殊注意

- 延遲高（30-120 秒），不適合意圖分類
- 支援完整 MCP 工具呼叫（其他 CLI 不支援）
- `--no-interactive` 必須，否則會等待 stdin
- 無 model 參數（由 Kiro 自動選擇）

## Claude CLI 特殊注意

- `--output-format text` 確保純文字輸出
- 支援 `--allowedTools` 限制工具使用
- 強推理能力，適合 evaluate 模式
- 需要 `ANTHROPIC_API_KEY`

## Antigravity CLI 特殊注意

- Go binary，需另外下載安裝
- 輕量快速，適合簡單 chat
- `-m` 指定模型
- 本地執行，無需 API Key（如用本地模型）

---

## Workflow 串接

```yaml
- id: ask_llm
  type: skill
  skill: llm_cli
  params:
    prompt: "分析這段程式碼的效能問題"
    mode: "chat"
    backend: "claude"
  output: analysis

- id: gen_skill
  type: skill
  skill: llm_cli
  params:
    prompt: "產出一個計算 Fibonacci 的 Skill"
    mode: "skill_gen"
    backend: "gemini"
    skill_id: "fibonacci"
  output: new_skill
```

---

## 注意事項

- 所有 CLI 使用 `asyncio.create_subprocess_exec`，非阻塞
- `_availability_cache` 快取可用性結果，避免重複檢查
- Kiro CLI 不支援 codegen/skill_gen 模式（僅 chat + evaluate）
- timeout 依後端調整：Kiro 預設 120s，其他 60s
- 輸出解析邏輯共用（code block 提取、JSON 提取）
- 所有 docstring 繁體中文，Python 3.12 語法


---

## Workshop 引導（ai-bot-workshop）

本 Skill 對應 Workshop Step 4：封裝 Gemini CLI 為 Skill。

### 前一步

確認已完成 Step 3（`ark-scheduler-generator`），專案有 `src/workflow/`。

### 觸發提詞

```
封裝 Gemini CLI 為 Skill
```

### 預期產出

- `src/skills/internal/llm_cli.py` — 統一 LLM CLI 封裝

### 驗證方式

```bash
python -c "from src.skills.internal.llm_cli import LlmCliSkill; print('OK')"
```

或直接測試：

```bash
gemini -p "你好"
```

### 下一步

完成後告訴 AI：`加入新聞抓取功能`（觸發 ark-web-scraper）

### 卡關時

- `gemini` 指令不存在 → `npm install -g @google/gemini-cli`
- 需要登入 → 執行 `gemini` 選擇 Login with Google
- 額度用完 → 等隔天重置（60 req/min, 1000 req/day）
