---
name: ark-team-runtime
description: |
  產出 Agent Team 的 runtime 啟動程式（daemon + start.py），
  使用 ark_team_core 提供完整能力（掛起偵測、成本控制、崩潰恢復、MCP 通訊）。
  使用此 Skill 當使用者提及 team runtime、啟動腳本、agent daemon、
  團隊啟動程式、start.py、team 管理程式、
  或任何需要產出 Agent Team 啟動/管理程式的場景。
metadata:
  author: paddyyang
  version: "1.0"
  updated: 2026-05-18
---

# ark-team-runtime

產出 Agent Team 的 runtime 啟動程式，一鍵啟動整個團隊。

## 觸發條件

- 「team runtime」、「啟動腳本」、「agent daemon」
- 「團隊啟動程式」、「start.py」、「team 管理程式」
- 「產出 runtime」、「啟動管理」
- 「產出團隊啟動程式」、「包含 CoreDaemon」、「team start」

---

## 輸入參數

| 參數 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `project_dir` | `str` | ✅ | — | 團隊專案目錄 |
| `team_name` | `str` | ✅ | — | 團隊名稱（kebab-case） |
| `has_mcp_tools` | `bool` | ❌ | `true` | 是否有業務 MCP Tools 需註冊 |
| `tools_module` | `str` | ❌ | `"src.{team_name}.mcp_setup"` | MCP Tools 註冊模組路徑 |

## 前置條件

- 已有 `team.yaml`（由 `ark-agent-team-builder` 產出）
- 已安裝 `ark-team-agent`（`pip install -e .` 或 `pip install ark-team-agent`）

---

## 產出指引

### 步驟 1：產出 start.py

```python
"""一鍵啟動 {team_name} Team。"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 確保專案根目錄在 path
sys.path.insert(0, str(Path(__file__).parent))

from ark_team_core import CoreDaemon


def main() -> None:
    # 註冊業務 MCP Tools（如有）
    tool_setup = None
    try:
        from {tools_module} import register_tools
        tool_setup = register_tools
    except ImportError:
        pass

    daemon = CoreDaemon("team.yaml", tool_setup=tool_setup)
    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        print("\n團隊已停止。")


if __name__ == "__main__":
    main()
```

### 步驟 2：產出 MCP Tools 註冊模組（如 has_mcp_tools=true）

```python
# src/{team_name}/mcp_setup.py
"""MCP Tools 註冊 — 將業務工具接入 MCP 協議。"""
from __future__ import annotations

from ark_team_core import McpRegistry, ToolDefinition
from .tools import TOOL_DEFINITIONS


# 工具 handler 對應表
HANDLERS: dict[str, callable] = {}


def _load_handlers() -> None:
    """延遲載入 handlers，避免 import 循環。"""
    from .tools import (
        # 在此 import 各工具的 handler 函式
    )
    # HANDLERS["tool_name"] = handler_function


def register_tools(registry: McpRegistry) -> None:
    """將業務工具註冊到 MCP Server。"""
    _load_handlers()
    for defn in TOOL_DEFINITIONS:
        name = defn["name"]
        if name in HANDLERS:
            registry.register(ToolDefinition(
                name=name,
                description=defn["description"],
                input_schema=defn["inputSchema"],
                handler=HANDLERS[name],
            ))
```

### 步驟 3：產出 requirements.txt 追加

確認 `requirements.txt` 包含：

```
ark-team-agent
```

或開發模式下在 `pyproject.toml` 加入依賴：

```toml
[project]
dependencies = ["ark-team-agent"]
```

### 步驟 4：產出啟動腳本（Windows + Linux）

**start-team.bat（Windows watchdog）：**

```batch
@echo off
:loop
echo [%date% %time%] 啟動 {team_name} Team...
python start.py
echo [%date% %time%] 程序結束，3 秒後重啟...
timeout /t 3 /nobreak >nul
goto loop
```

**start-team.sh（Linux watchdog）：**

```bash
#!/bin/bash
while true; do
    echo "[$(date)] 啟動 {team_name} Team..."
    python start.py
    echo "[$(date)] 程序結束，3 秒後重啟..."
    sleep 3
done
```

### 步驟 5：驗證

```bash
python start.py
# 預期：所有 agent 啟動 + health API 可存取
curl http://127.0.0.1:{health_port}/api/status
```

---

## 產出檔案清單

```
{project_dir}/
├── start.py                    # 主啟動腳本
├── start-team.bat              # Windows watchdog
├── start-team.sh               # Linux watchdog
└── src/{team_name}/
    └── mcp_setup.py            # MCP Tools 註冊（如有）
```

## 注意事項

- `CoreDaemon` 自動讀取 `team.yaml` 的 `cost_guard` + `hang_detector` 設定
- `tool_setup` 為 None 時，MCP Server 只提供通用工具（send/reply/status）
- watchdog 腳本確保 crash 後自動重啟
- health_port 從 team.yaml 讀取（預設 23031）


---

## Workshop 引導（agent-team-workshop）

本 Skill 對應 Workshop Step 1b（產出啟動程式）+ Step 4（啟動團隊）。

### 觸發提詞

```
產出團隊啟動程式，包含 CoreDaemon + Telegram + 排程
```

### 預期產出

- `start.py` — 主啟動腳本
- `start-team.bat` / `start-team.sh` — watchdog
- `src/ark_team_core/` — vendored 核心引擎

### 啟動驗證（Step 4）

```bash
python start.py
```

預期看到：
```
[INFO] 載入 team.yaml...
[INFO] 啟動 5 個 agent...
[INFO] Health API: http://127.0.0.1:23031
```

### 下一步

完成後告訴 AI：`為 pm-agent 配置 .kiro/，角色是專案經理`（觸發 ark-kiro-init）

### 卡關時

- `ModuleNotFoundError: ark_team_core` → 確認 `src/ark_team_core/` 目錄存在
- `FileNotFoundError: team.yaml` → 確認在專案根目錄執行
- port 衝突 → 改 `team.yaml` 的 `health_port`
