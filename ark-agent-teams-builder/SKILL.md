---
author: paddyyang
name: ark-agent-teams-builder
description: |
  產出完整的多 Agent 團隊系統（team.yaml + runtime + scheduler + MCP），
  不依賴 pip install ark-team-agent，產出即可 python start.py 啟動。
  支援 2-12 人團隊，預設 3 人（leader + dev + qa）。
  使用此 Skill 當使用者提及 建立團隊、team builder、agent teams、
  多 agent 系統、團隊骨架、建立 N 人團隊、
  或任何需要從零建立可運行的多 Agent 協作系統的場景。
---

# ark-agent-teams-builder

產出完整多 Agent 團隊系統，`python start.py` 一鍵啟動。

## 觸發條件

- 「建立團隊」、「team builder」、「agent teams」
- 「多 agent 系統」、「團隊骨架」
- 「建立 N 人團隊」、「ark-agent-teams」

---

## 前置條件

| 依賴 | 說明 |
|------|------|
| Python ≥ 3.11 | runtime 執行環境 |
| kiro-cli | 每個 agent 的 AI 後端（唯一外部依賴） |

---

## 互動流程

```
1. 確認團隊規模 → 預設 3 人，可選 2-12 人
2. 確認角色組合 → 從 presets 選或自訂
3. 確認通訊管道 → Telegram（選填）
4. 確認排程需求 → 預設開啟
5. 產出全部檔案（team.yaml + runtime/ + agents/）
6. 提示：「用 /ark-kiro-init 為每個 agent 配置 .kiro/，然後 python start.py」
```

### 快速模式

「建立 3 人團隊」→ 跳過確認，直接用預設值產出。

---

## 產出結構

```
{project}/
├── team.yaml                       # 團隊配置
├── scheduler.yaml                  # Agent 排程（提詞觸發）
├── start.py                        # 一鍵啟動入口
├── requirements.txt                # pyyaml（必要）+ apscheduler（選填）
├── .env.example
├── .gitignore
├── prompts/                        # 共用提詞模板
│   ├── dispatch-feature.md
│   ├── dispatch-bugfix.md
│   ├── review-pr.md
│   ├── daily-report.md
│   └── learning-prompt.md
├── tasks/                          # 任務板
│   ├── board.json
│   └── items/
├── knowledge/                      # 全域知識庫
│   └── .gitkeep
├── docs/                           # 全域文件
│   └── .gitkeep
├── runtime/                        # 精簡版 runtime（自包含）
│   ├── __init__.py
│   ├── daemon.py                   # 管理 N 個 kiro-cli 子程序
│   ├── backend.py                  # kiro-cli 啟動命令 + .kiro/ 寫入
│   ├── config.py                   # team.yaml 解析
│   ├── process.py                  # asyncio subprocess 管理
│   ├── mcp_server.py              # 10 個核心 MCP 工具
│   ├── api.py                      # HTTP health + send + status
│   └── scheduler.py               # cron 排程觸發
├── leader-agent/                   # leader（根層）
│   ├── knowledge/
│   │   ├── learning.md
│   │   └── wiki/
│   ├── output/.gitkeep
│   ├── docs/.gitkeep
│   └── specs/.gitkeep
├── dev-agent/                      # worker
│   ├── knowledge/
│   │   ├── learning.md
│   │   └── wiki/
│   ├── output/.gitkeep
│   └── docs/.gitkeep
├── qa-agent/                       # worker
│   ├── knowledge/
│   │   ├── learning.md
│   │   └── wiki/
│   ├── output/.gitkeep
│   └── docs/.gitkeep
└── knowledge/                      # 全域知識庫
    ├── governance/                 # 治理知識（steering 決策、方針）
    │   └── .gitkeep
    └── shared/                     # 共享知識（晉升後的 wiki）
        └── .gitkeep
```

---

## 系統架構

```
start.py
  └── runtime/daemon.py（主程序）
        │
        ├── 讀取 team.yaml（config.py）
        ├── 為每個 instance 啟動 kiro-cli（backend.py + process.py）
        ├── 注入 MCP Server（mcp_server.py）
        ├── 啟動 HTTP API（api.py）
        └── 啟動排程（scheduler.py）

每個 agent instance：
  kiro-cli chat --trust-all-tools --legacy-ui --resume --model auto
    └── 透過 MCP Server 與其他 agent 通訊
```

### runtime 模組說明

| 模組 | 行數 | 職責 |
|------|------|------|
| `daemon.py` | ~200 | 啟動/停止/重啟所有 agent instance |
| `backend.py` | ~150 | 組裝 kiro-cli 啟動命令 + 寫入 .kiro/steering/ + mcp.json |
| `config.py` | ~100 | 解析 team.yaml → dataclass |
| `process.py` | ~80 | asyncio subprocess 封裝（start/kill/is_alive） |
| `mcp_server.py` | ~200 | stdio JSON-RPC MCP Server（6 個工具） |
| `api.py` | ~100 | HTTP server（health/send/status 3 個端點） |
| `scheduler.py` | ~80 | cron 解析 + 定時發送 prompt 給 agent |

### MCP 工具（10 個）

| 工具 | 用途 | 可用角色 |
|------|------|---------|
| `reply(text)` | 回覆使用者（stdout/webhook） | 全部 |
| `send_to_instance(instance, msg)` | 發訊息給其他 agent | leader/manager |
| `delegate_task(instance, task)` | 委派任務 | leader |
| `query_team_status()` | 查詢團隊狀態 | 全部 |
| `create_task(title, assignee)` | 建立任務 | leader |
| `update_task(task_id, status)` | 更新任務狀態 | 全部 |
| `log_to_leader(text)` | 私下回報 leader | 全部 |
| `list_tasks(status)` | 列出任務板 | 全部 |
| `record_spend(amount, note)` | 記錄成本 | 全部 |
| `broadcast_all(message)` | 廣播全員 | leader |

### 啟動流程

```python
# start.py
import asyncio
from runtime.daemon import TeamDaemon

if __name__ == "__main__":
    daemon = TeamDaemon("team.yaml")
    asyncio.run(daemon.run())
```

---

## 產出規則

### 1. team.yaml

```yaml
defaults:
  backend: kiro-cli
  model: auto

cost_guard:
  daily_limit_usd: 30.0
  warn_at_percentage: 80
  timezone: Asia/Taipei

hang_detector:
  enabled: true
  timeout_minutes: 60

# channel:
#   bot_token_env: TELEGRAM_BOT_TOKEN
#   group_id: -100xxxxxxxxxx

instances:
  {leader}-agent:
    working_directory: {leader}-agent
    description: "{emoji} {描述}"
    role: leader

  {worker}-agent:
    working_directory: {worker}-agent
    description: "{emoji} {描述}"
    role: worker

health_port: 13030
```

### 2. scheduler.yaml

```yaml
timezone: Asia/Taipei

jobs:
  - name: hourly-progress
    target: {leader}-agent
    prompt: "⏰ 確認團隊狀態，派工或追蹤。更新 memory.md。"
    cron: "10 9-21 * * *"

  - name: daily-summary
    target: {leader}-agent
    prompt: "📋 今日摘要 + 明日計劃，reply 回報。"
    cron: "daily:21:00"
```

### 3. start.py

```python
"""一鍵啟動多 Agent 團隊。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from runtime.daemon import TeamDaemon

if __name__ == "__main__":
    daemon = TeamDaemon("team.yaml")
    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        print("\n團隊已停止。")
```

### 4. requirements.txt

```
pyyaml>=6.0
# apscheduler>=3.10.0  # 需要排程時取消註解
```

### 5. runtime/ 模組

從 `references/runtime-modules.md` 載入各模組的精簡版規格，逐一產出。

核心設計原則：
- 零第三方依賴（除 pyyaml）
- asyncio 原生（不用 aiohttp）
- 手寫 stdio JSON-RPC（不用 mcp SDK）
- Windows + Linux 相容

---

## 角色預設組合

從 `references/role-presets.md` 載入。

| 預設 | 角色 |
|------|------|
| 最小（2人） | leader + dev |
| 標準（3人） | leader + dev + qa |
| 全端（4人） | leader + frontend + backend + devops |
| 遊戲（5人） | leader + gamedev + frontend + backend + qa |
| 完整（6人） | leader + dev + qa + devops + design + analyst |

---

## 與其他 Skill 的關係

```
/ark-agent-teams-builder     → 團隊系統（runtime + 配置）
  ↓
/ark-kiro-init               → 各 agent 的 .kiro/（SOUL.md + prompts + skills）
  ↓
/ark-wiki-engine             → 知識庫

獨立擴充（在某個 agent 的 working_directory 下）：
/ark-webapp                  → 加 Web 服務
/ark-chatbot                 → 加 Telegram Bot + LLM
/ark-scheduler               → 加 WorkflowEngine + YAML 工作流
```

**注意**：runtime/scheduler.py（團隊排程，發 prompt 給 agent）≠ ark-scheduler-generator（應用排程，執行 Python Skill）。

---

## 冪等性

```
if team.yaml 已存在 → 提示覆寫或跳過
if runtime/ 已存在 → 提示覆寫或跳過
if agents/{name}/ 已存在 → 跳過（不刪除）
```

---

## 品質檢查

- [ ] `team.yaml` 有 defaults + instances + health_port
- [ ] 恰好 1 個 role: leader
- [ ] `scheduler.yaml` 有 timezone + ≥ 2 jobs
- [ ] `start.py` 可執行（`python start.py --help` 不報錯）
- [ ] `runtime/` 全部模組可 import
- [ ] 每個 agent 目錄有 knowledge/ + output/
- [ ] `.env.example` + `.gitignore` 存在

---

## 完成回報格式

```
✅ 多 Agent 團隊系統已建立

📁 產出清單：
- team.yaml（{N} 個 instances）
- scheduler.yaml（{M} 個 jobs）
- start.py（一鍵啟動）
- runtime/（7 個模組，~900 行）
- requirements.txt
- .env.example + .gitignore
- agents/（{N} 個目錄）

📋 下一步：
1. 執行 /ark-kiro-init 為每個 agent 配置 .kiro/
2. pip install -r requirements.txt
3. python start.py
```
