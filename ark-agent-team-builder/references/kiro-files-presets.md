# kiro_files Policy 預設組合

## 概述

`kiro_files` 控制 `backend.py` 啟動時如何管理每個 agent 的 `.kiro/` 目錄。
6 種 policy：`symlink` / `copy` / `always` / `once` / `template` / `skip`

---

## 預設組合

### Minimal（新手推薦）

最少配置，只產出必要檔案。

```yaml
kiro_files:
  steering:
    agents_md: symlink        # 共用規範（symlink 到根層）
    team_md: symlink   # 每次啟動重新產生
    soul_md: once             # 首次產出後不覆寫
    memory_md: once           # 首次產出後不覆寫
  settings:
    mcp_json: always          # 每次啟動重新產生（確保工具同步）
  agents:
    agent_json: once          # 首次產出後不覆寫
  skills:
    policy: skip              # 不自動部署 skills
```

**適用：** 快速啟動、不需要 skills 自動部署。

---

### Standard（推薦）

標準配置，自動部署 4 個核心 skills。

```yaml
kiro_files:
  steering:
    agents_md: symlink
    team_md: symlink
    soul_md: once
    memory_md: once
  settings:
    mcp_json: always
  agents:
    agent_json: once
  prompts:
    policy: once
  skills:
    policy: once              # 首次部署，之後不覆寫
    # source: null            # 預設從 templates/skills/ 讀取
```

**適用：** 大部分團隊。

---

### Full（進階）

完整配置，含 knowledge 掛載和 template 模式。

```yaml
kiro_files:
  steering:
    agents_md: symlink
    team_md: symlink
    soul_md: template         # 支援 .meta.json 變數替換
    memory_md: once
  settings:
    mcp_json: always
  agents:
    agent_json: template      # 支援 .meta.json 變數替換
  prompts:
    policy: once
    source: templates/prompts
  skills:
    policy: once
    source: templates/skills
  shared_wiki: knowledge/shared
  private_wiki: knowledge/{instance}
```

**適用：** 大型團隊、需要知識庫和模板變數。

---

## Policy 說明

| Policy | 行為 | 適用場景 |
|--------|------|---------|
| `symlink` | 建立 symlink 指向根層檔案 | 共用規範（修改一處全員生效） |
| `copy` | 複製檔案（獨立副本） | 需要各 agent 獨立修改 |
| `always` | 每次啟動都重新產生 | 動態內容（team-context、mcp.json） |
| `once` | 只在不存在時產出 | 使用者可能手動修改的檔案 |
| `template` | 讀 .meta.json 做變數替換 | 需要 per-agent 客製化 |
| `skip` | 不處理 | 不需要的功能 |

## template 模式範例

```json
// agents/coder/agent.json.meta.json
{
  "variables": {
    "agent_name": "dev-agent",
    "display_name": "Developer",
    "emoji": "🧑‍💻"
  }
}
```

```json
// agents/coder/agent.json（模板）
{
  "name": "{{agent_name}}",
  "displayName": "{{display_name}} {{emoji}}"
}
```

---

## 選擇建議

| 情境 | 推薦 |
|------|------|
| 第一次建團隊 | Minimal |
| 正式專案 | Standard |
| 大型團隊（6+ 人） | Full |
| 需要知識庫 | Full（含 shared_wiki） |
| 需要 per-agent 客製 | Full（template 模式） |
