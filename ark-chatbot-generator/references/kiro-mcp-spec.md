# Kiro CLI MCP 整合規範

Kiro CLI 作為獨立的 Agent 後端整合進 Bot，提供程式碼分析、檔案操作、複雜推理等能力。
Kiro 不參與一般 LLM fallback chain（延遲太高），而是作為獨立路徑，使用者明確要求時才走。

## 架構定位

```
使用者訊息
    ↓
IntentRouter 判斷
    ├── Kiro 指令（/ask_kiro, /read, /write, /ls, /analyze, /version, /doctor）
    │     → KiroAdapter（subprocess kiro-cli）
    │     → 適合：程式碼分析、檔案操作、複雜推理
    │
    ├── Skill 呼叫（自然語言 → 意圖分類 → FC）
    │     → LLM Fallback: Gemini → Ollama → 靜態
    │     → 適合：快速回應、Skill 路由
    │
    └── 一般對話（閒聊、問答）
          → LLM_BACKEND 決定路由：
            - gemini（預設）：Gemini → Ollama → 靜態
            - kiro：kiro-cli chat → Gemini → Ollama → 靜態
            - ollama：Ollama → Gemini → 靜態
```

### 與 LLM Fallback Chain 的關係

| 項目 | KiroAdapter | GeminiAdapter | LLMAdapter（Ollama） |
|------|------------|---------------|---------------------|
| 定位 | 獨立 Agent 後端 | 主要 LLM 後端 | 備援 LLM 後端 |
| 延遲 | 30-120 秒 | 1-5 秒 | 2-10 秒 |
| 能力 | 完整 agent（讀寫檔案、搜尋、執行命令） | 文字生成 + Function Calling | 文字生成 |
| 觸發方式 | 明確指令 或 `LLM_BACKEND=kiro` | 預設 | `OLLAMA_ENABLED=true` |
| 前置條件 | kiro-cli 已安裝且已登入 | GEMINI_API_KEY | Ollama 服務運行中 |
| 適合場景 | 程式碼分析、跨檔案重構、複雜推理 | 意圖分類、FC、一般對話 | 離線環境、本地推理 |

---

## KiroAdapter 類別規範

### 檔案位置

`src/llm/kiro_adapter.py`

### 類別設計

```python
"""KiroAdapter：封裝 kiro-cli 呼叫，作為獨立 Agent 後端。"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class KiroAdapter:
    """封裝 kiro-cli 所有操作，透過 subprocess 非同步執行。

    不參與一般 LLM fallback chain（延遲太高），
    作為獨立路徑供使用者明確要求時使用。
    當 LLM_BACKEND=kiro 時，一般對話也會走此路徑。
    """

    def __init__(
        self,
        kiro_cmd: str | None = None,
        workspace: str | None = None,
        chat_timeout: int | None = None,
        file_timeout: int | None = None,
    ) -> None:
        self.kiro_cmd = kiro_cmd or os.getenv("KIRO_CLI_CMD", "kiro-cli")
        self.workspace = workspace or os.getenv(
            "KIRO_WORKSPACE", str(Path.home() / "kiro-workspace")
        )
        self.chat_timeout = chat_timeout or int(os.getenv("KIRO_CHAT_TIMEOUT", "120"))
        self.file_timeout = file_timeout or int(os.getenv("KIRO_FILE_TIMEOUT", "30"))
        self._available: bool | None = None  # 延遲檢查

    # ── 可用性檢查 ──────────────────────────────────────────

    async def is_available(self) -> bool:
        """檢查 kiro-cli 是否可用（已安裝且可執行）。

        結果快取，僅第一次呼叫時執行檢查。
        """
        if self._available is not None:
            return self._available
        try:
            proc = await asyncio.create_subprocess_exec(
                self.kiro_cmd, "version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            self._available = proc.returncode == 0
            if self._available:
                version = stdout.decode("utf-8", errors="replace").strip()
                logger.info("Kiro CLI 可用：%s", version)
            else:
                logger.warning("Kiro CLI 不可用（exit %d）", proc.returncode)
        except (FileNotFoundError, asyncio.TimeoutError, Exception) as e:
            logger.warning("Kiro CLI 不可用：%s", e)
            self._available = False
        return self._available

    # ── 核心執行 ────────────────────────────────────────────

    async def _run(
        self,
        cmd: list[str],
        cwd: str | None = None,
        timeout: int | None = None,
        stdin_data: str | None = None,
    ) -> dict[str, Any]:
        """執行 shell 命令並回傳結果。"""
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE if stdin_data else None,
                cwd=cwd or self.workspace,
            )
            stdin_bytes = stdin_data.encode() if stdin_data else None
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=stdin_bytes),
                timeout=timeout or self.chat_timeout,
            )
            return {
                "success": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": stdout.decode("utf-8", errors="replace").strip(),
                "stderr": stderr.decode("utf-8", errors="replace").strip(),
            }
        except asyncio.TimeoutError:
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": f"執行超時（{timeout or self.chat_timeout}s）",
            }
        except FileNotFoundError:
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": f"找不到命令：{cmd[0]}，請確認 kiro-cli 已安裝",
            }
        except Exception as e:
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
            }

    def _fmt(self, result: dict, label: str = "") -> str:
        """格式化命令執行結果為可讀文字。"""
        parts = []
        if label:
            parts.append(f"【{label}】")
        if result["stdout"]:
            parts.append(result["stdout"])
        if result["stderr"] and not result["success"]:
            parts.append(f"⚠️ {result['stderr']}")
        if not result["success"] and not result["stdout"] and not result["stderr"]:
            parts.append(f"執行失敗（exit {result['returncode']}）")
        return "\n".join(parts) if parts else "（無輸出）"

    # ── 對話功能 ────────────────────────────────────────────

    async def ask(
        self,
        question: str,
        agent: str = "",
        trust_all_tools: bool = True,
    ) -> dict[str, Any]:
        """向 Kiro CLI 發送問題（非互動模式）。

        Args:
            question: 要問的問題或指令
            agent: 指定 agent 名稱（留空使用預設）
            trust_all_tools: 是否自動核准所有工具

        Returns:
            {"text": str, "model": str, "success": bool}
        """
        cmd = [self.kiro_cmd, "chat", "--no-interactive"]
        if trust_all_tools:
            cmd.append("--trust-all-tools")
        if agent:
            cmd += ["--agent", agent]
        cmd.append(question)

        result = await self._run(cmd, timeout=self.chat_timeout)
        return {
            "text": self._fmt(result, "Kiro"),
            "model": "kiro-cli",
            "success": result["success"],
            "tokens": 0,
        }

    async def resume_chat(
        self,
        question: str,
        session_id: str = "",
        trust_all_tools: bool = True,
    ) -> dict[str, Any]:
        """繼續 Kiro CLI 對話（resume 模式）。"""
        cmd = [self.kiro_cmd, "chat", "--no-interactive"]
        if trust_all_tools:
            cmd.append("--trust-all-tools")
        if session_id:
            cmd += ["--resume-id", session_id]
        else:
            cmd.append("--resume")
        cmd.append(question)

        result = await self._run(cmd, timeout=self.chat_timeout)
        return {
            "text": self._fmt(result, "Kiro 繼續對話"),
            "model": "kiro-cli",
            "success": result["success"],
            "tokens": 0,
        }

    async def list_sessions(self) -> str:
        """列出所有 Kiro CLI 對話 Session。"""
        cmd = [self.kiro_cmd, "chat", "--list-sessions"]
        result = await self._run(cmd, timeout=self.file_timeout)
        return self._fmt(result, "Sessions")

    # ── 檔案操作 ────────────────────────────────────────────

    async def file_read(self, path: str) -> str:
        """讀取檔案內容（直接 Python pathlib，不經 kiro-cli）。"""
        try:
            file_path = (
                Path(path) if Path(path).is_absolute()
                else Path(self.workspace) / path
            )
            if not file_path.exists():
                return f"❌ 檔案不存在：{file_path}"
            if not file_path.is_file():
                return f"❌ 不是檔案：{file_path}"
            content = file_path.read_text(encoding="utf-8", errors="replace")
            size = file_path.stat().st_size
            lines = content.count("\n") + 1
            return f"📄 {file_path}\n（{size} bytes，{lines} 行）\n\n{content}"
        except Exception as e:
            return f"❌ 讀取失敗：{e}"

    async def file_write(self, path: str, content: str, append: bool = False) -> str:
        """寫入檔案內容（自動建立目錄）。"""
        try:
            file_path = (
                Path(path) if Path(path).is_absolute()
                else Path(self.workspace) / path
            )
            file_path.parent.mkdir(parents=True, exist_ok=True)
            mode = "a" if append else "w"
            with open(file_path, mode, encoding="utf-8") as f:
                f.write(content)
            action = "附加" if append else "寫入"
            size = file_path.stat().st_size
            return f"✅ {action}成功：{file_path}（{size} bytes）"
        except Exception as e:
            return f"❌ 寫入失敗：{e}"

    async def file_list(self, path: str = "", pattern: str = "*") -> str:
        """列出目錄內容。"""
        try:
            dir_path = (
                Path(path) if (path and Path(path).is_absolute())
                else Path(self.workspace) / (path or "")
            )
            if not dir_path.exists():
                return f"❌ 路徑不存在：{dir_path}"
            if not dir_path.is_dir():
                return f"❌ 不是目錄：{dir_path}"
            items = sorted(dir_path.glob(pattern))
            lines = [f"📁 {dir_path}\n"]
            for item in items:
                prefix = "📁" if item.is_dir() else "📄"
                size = f"  ({item.stat().st_size}b)" if item.is_file() else ""
                lines.append(f"  {prefix} {item.name}{size}")
            return "\n".join(lines) if len(lines) > 1 else f"📁 {dir_path}\n（空目錄）"
        except Exception as e:
            return f"❌ 列出失敗：{e}"

    async def file_delete(self, path: str) -> str:
        """刪除檔案。"""
        try:
            file_path = (
                Path(path) if Path(path).is_absolute()
                else Path(self.workspace) / path
            )
            if not file_path.exists():
                return f"❌ 檔案不存在：{file_path}"
            file_path.unlink()
            return f"✅ 已刪除：{file_path}"
        except Exception as e:
            return f"❌ 刪除失敗：{e}"

    # ── Kiro 分析 ───────────────────────────────────────────

    async def analyze_file(self, path: str, instruction: str) -> str:
        """讓 Kiro CLI 讀取並分析檔案。"""
        file_path = (
            Path(path) if Path(path).is_absolute()
            else Path(self.workspace) / path
        )
        if not file_path.exists():
            return f"❌ 檔案不存在：{file_path}"

        prompt = f"請讀取並處理以下檔案：{file_path}\n\n指令：{instruction}"
        cmd = [
            self.kiro_cmd, "chat", "--no-interactive",
            "--trust-all-tools", prompt,
        ]
        result = await self._run(
            cmd, cwd=str(file_path.parent), timeout=self.chat_timeout,
        )
        return self._fmt(result, f"分析 {file_path.name}")

    # ── 系統資訊 ────────────────────────────────────────────

    async def version(self) -> str:
        """取得 Kiro CLI 版本。"""
        result = await self._run([self.kiro_cmd, "version"], timeout=10)
        return self._fmt(result, "版本")

    async def doctor(self) -> str:
        """執行 Kiro CLI 診斷。"""
        result = await self._run(
            [self.kiro_cmd, "doctor", "--format", "plain"], timeout=30,
        )
        return self._fmt(result, "診斷報告")

    async def whoami(self) -> str:
        """查看登入資訊。"""
        result = await self._run(
            [self.kiro_cmd, "whoami", "--format", "plain"], timeout=10,
        )
        return self._fmt(result, "使用者資訊")

    async def translate(self, instruction: str) -> str:
        """自然語言翻譯為 shell 命令（不執行）。"""
        cmd = [self.kiro_cmd, "translate", instruction]
        result = await self._run(cmd, timeout=30)
        return self._fmt(result, "Shell 命令建議")

    # ── LLM 相容介面 ───────────────────────────────────────

    async def generate(
        self,
        prompt: str,
        system: str = "",
        **kwargs,
    ) -> dict[str, Any]:
        """LLM 相容介面：將 generate 呼叫轉為 kiro-cli chat。

        當 LLM_BACKEND=kiro 時，LLMRouter 會呼叫此方法。
        注意：延遲 30-120 秒，遠高於 Gemini/Ollama。
        """
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        return await self.ask(full_prompt)
```

---

## LLMRouter 類別規範

### 檔案位置

`src/llm/llm_router.py`

### 設計概念

統一路由所有 LLM 呼叫，根據 `LLM_BACKEND` 環境變數決定優先順序，
自動建構 fallback chain。

```python
"""LLMRouter：統一 LLM 路由，支援 Kiro/Gemini/Ollama 三後端 + fallback chain。"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# 支援的後端
BACKENDS = ("kiro", "gemini", "ollama")


class LLMRouter:
    """統一 LLM 路由器。

    根據 LLM_BACKEND 環境變數決定優先順序，自動建構 fallback chain。
    Kiro 作為獨立 Agent 後端，僅在 LLM_BACKEND=kiro 時參與一般對話。
    Kiro 指令（/ask_kiro 等）不經過此 Router，直接走 KiroAdapter。

    Fallback chain 建構邏輯：
    - LLM_BACKEND=gemini（預設）：Gemini → Ollama → 靜態
    - LLM_BACKEND=kiro：Kiro → Gemini → Ollama → 靜態
    - LLM_BACKEND=ollama：Ollama → Gemini → 靜態
    """

    def __init__(
        self,
        kiro=None,       # KiroAdapter | None
        gemini=None,     # GeminiAdapter | None
        ollama=None,     # LLMAdapter | None（Ollama 模式）
        backend: str | None = None,
    ) -> None:
        self.kiro = kiro
        self.gemini = gemini
        self.ollama = ollama
        self.backend = (
            backend or os.getenv("LLM_BACKEND", "gemini")
        ).lower()

    def _build_chain(self) -> list[tuple[str, Any]]:
        """根據 backend 設定建構 fallback chain。

        Returns:
            [(backend_name, adapter), ...] 依優先順序排列
        """
        all_backends = {
            "kiro": self.kiro,
            "gemini": self.gemini,
            "ollama": self.ollama,
        }

        # 主後端排第一
        chain = []
        if self.backend in all_backends and all_backends[self.backend]:
            chain.append((self.backend, all_backends[self.backend]))

        # 其餘後端依預設順序加入
        default_order = ["gemini", "ollama", "kiro"]
        for name in default_order:
            if name != self.backend and all_backends.get(name):
                chain.append((name, all_backends[name]))

        return chain

    async def generate(
        self,
        prompt: str,
        system: str = "",
        tier: str = "FAST",
        temperature: float = 0.7,
        **kwargs,
    ) -> dict[str, Any]:
        """統一文字生成介面，自動 fallback。"""
        chain = self._build_chain()

        for i, (name, adapter) in enumerate(chain):
            try:
                if name == "kiro":
                    # KiroAdapter.generate() 相容介面
                    result = await adapter.generate(
                        prompt=prompt, system=system,
                    )
                elif name == "gemini":
                    result = await adapter.generate(
                        prompt=prompt, system=system,
                        tier=tier, temperature=temperature,
                    )
                else:
                    # LLMAdapter（Ollama）
                    result = await adapter.generate(
                        prompt=prompt, system=system,
                        tier=tier, temperature=temperature,
                    )
                result["fallback"] = i > 0
                result["backend"] = name
                return result
            except Exception as e:
                logger.warning(
                    "LLMRouter: %s 失敗，嘗試下一個: %s", name, e,
                )
                continue

        # 全部失敗
        return {
            "text": "抱歉，目前無法處理您的請求。所有 LLM 後端暫時不可用。",
            "model": "static_fallback",
            "tokens": 0,
            "fallback": True,
            "backend": "static",
        }

    async def function_call(
        self,
        user_message: str,
        tools: list[dict],
        tier: str = "BALANCE",
    ) -> dict[str, Any]:
        """Function Calling（僅 Gemini 支援）。

        Kiro 和 Ollama 不支援 FC，直接走 GeminiAdapter。
        Gemini 不可用時降級為靜態回應。
        """
        if self.gemini:
            try:
                return await self.gemini.function_call(
                    user_message=user_message, tools=tools, tier=tier,
                )
            except Exception as e:
                logger.warning("LLMRouter FC 失敗: %s", e)

        return {
            "action": "reply",
            "text": "抱歉，Function Calling 目前不可用（需要 Gemini API Key）。",
        }
```

---

## Kiro Bot 指令 Handlers 規範

### 檔案位置

`src/bot/kiro_handlers.py`

### 指令清單

| 指令 | 說明 | KiroAdapter 方法 |
|------|------|-----------------|
| `/ask_kiro <問題>` | 透過 Kiro CLI 提問（完整 agent 能力） | `ask()` |
| `/resume_kiro <問題>` | 繼續上次 Kiro 對話 | `resume_chat()` |
| `/kiro_sessions` | 列出 Kiro 對話 Session | `list_sessions()` |
| `/read <路徑>` | 讀取檔案內容 | `file_read()` |
| `/write <路徑>` | 寫入檔案（下一則訊息為內容） | `file_write()` |
| `/ls [路徑]` | 列出目錄 | `file_list()` |
| `/rm <路徑>` | 刪除檔案（有確認步驟） | `file_delete()` |
| `/analyze <路徑> <指令>` | 讓 Kiro 分析檔案 | `analyze_file()` |
| `/kiro_version` | Kiro CLI 版本 | `version()` |
| `/kiro_doctor` | 系統診斷 | `doctor()` |
| `/gen_skill <kiro_skill> <skill_id> [描述]` | 產出 Runtime Skill | `generate_skill()` |
| `/list_kiro_skills` | 列出可產出的 Kiro Skills | — |
| `/skill_status <skill_id>` | 檢查 Skill 檔案狀態 | `get_skill_status()` |

### Handler 設計模式

使用 `init_kiro()` 模組層級注入（與 `handlers.py` 的 `init_components()` 一致）：

```python
"""Kiro CLI 操作指令 Handlers。"""

from src.llm.kiro_adapter import KiroAdapter

_kiro: KiroAdapter | None = None

def init_kiro(kiro: KiroAdapter | None) -> None:
    """初始化 KiroAdapter（由 bot/main.py 呼叫）。"""
    global _kiro
    _kiro = kiro
```

---

## 環境變數設定

### `.env.example` 新增項目

```bash
# ── LLM 後端設定 ─────────────────────────────────────────
# 一般對話的 LLM 後端優先順序
# gemini = Gemini 為主、Ollama 備援（推薦，低延遲）
# kiro   = Kiro CLI 為主（高延遲但最強，完整 agent 能力）
# ollama = Ollama 為主、Gemini 備援（離線環境）
LLM_BACKEND=gemini

# ── Kiro CLI（獨立功能，不受 LLM_BACKEND 影響） ──────────
# kiro-cli 執行路徑（需在 PATH 中，或指定完整路徑）
KIRO_CLI_CMD=kiro-cli

# Kiro 預設工作目錄（Bot 操作檔案的根目錄）
KIRO_WORKSPACE=/your/workspace/path

# Kiro 對話超時（秒）— kiro-cli chat 可能需要較長時間
KIRO_CHAT_TIMEOUT=120

# 檔案操作超時（秒）
KIRO_FILE_TIMEOUT=30
```

### `requirements.txt` 新增

```
# MCP Client（可選，用於 MCP Server 管理功能）
mcp>=1.2.0
```

---

## 可選：MCP Client 模式

除了直接 subprocess 呼叫 kiro-cli，也可以透過 MCP Client 連接 kiro-mcp server。
兩種模式的差異：

| 項目 | Subprocess 模式（預設） | MCP Client 模式 |
|------|----------------------|----------------|
| 依賴 | 僅需 kiro-cli | 需 kiro-cli + MCP Server 腳本 |
| 設定 | 簡單（環境變數） | 需設定 MCP Server 路徑 |
| 功能 | 對話 + 檔案操作 | 完整 22 個 MCP Tools |
| 適用 | 一般使用 | 需要 MCP 管理、Agent 管理時 |

預設使用 Subprocess 模式，簡單直接。
需要完整 MCP 管理功能時，可啟用 MCP Client 模式（設定 `MCP_SERVER_SCRIPT` 環境變數）。
