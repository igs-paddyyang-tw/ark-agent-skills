# 預設角色範本：全端工程師 + SA/SD

## 範本來源（現行 assets）

`build_kiro.py` 產出時，各檔的範本來自本 skill 的 `assets/`：

| 產出檔 | 範本來源 | 說明 |
|--------|---------|------|
| `.kiro/steering/SOUL.md` | `assets/steering/SOUL-{root,leader,admin,worker}.md` | 依角色選一 |
| `.kiro/steering/AGENTS.md` | 產出時組出（見 SKILL 步驟）| 全域規範，SSOT |
| `.kiro/steering/CODE.md` | `assets/steering/CODE.md` | 程式碼規範（`fileMatch: src/**/*.py`）|
| `.kiro/steering/MEMORY.md` | `assets/steering/MEMORY-template.md` | 工作記憶（含自我保護上限）|
| `.kiro/steering/BRAIN.md` | `assets/steering/BRAIN.md` | 角色知識範本 |
| `.kiro/steering/TEAM.md` | 套件 daemon 動態產生（`inclusion: manual`）| **不從 assets 取** |
| `.kiro/agents/{role}.json` | `assets/agents/{admin-agent,agent}.json` | agent 定義 |
| `.kiro/prompts/*.md` | `assets/prompts/*.md` | route-message / service-check / daily-report / team-check |

> 🔴 範本用**相對路徑**（`assets/…`），不寫死絕對路徑或平台路徑。
> 本 skill 跨機器/跨 OS 使用，硬路徑會在別台機器失效。

## 產出時的替換規則

複製範本到目標目錄時：

**保持不變（通用）**
- `CODE.md` 的語言/程式碼規範
- `AGENTS.md` 的共用行為準則

**需依專案調整（產出後提示使用者）**
- `agents/{role}.json` 的 `mcp_servers`（依實際可用工具）
- `.kiro/settings/mcp.json` 的環境變數（`${DATABASE_URL}` 等）
- 各 `SOUL.md` 的角色人格（換領域時要重寫，或用網路搜尋流程重產）

## 多角色合併

指定多角色時（如「全端 + DevOps」）：
1. `agents/*.json` 取主要角色
2. steering 全部保留（不衝突）
3. `prompts/` 合併
4. `settings/mcp.json` 合併 servers
