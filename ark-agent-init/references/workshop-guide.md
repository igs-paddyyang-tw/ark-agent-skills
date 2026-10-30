# Workshop 引導（agent-team-workshop）

> 2026-10-30 自 SKILL.md 原樣搬出（盤點 O-4：主檔只留流程與決策）。

## Workshop 引導（agent-team-workshop）

本 Skill 對應 Workshop Step 2：為每個 agent 配置 .kiro/。

### 觸發提詞（逐一配置）

```
為 pm-agent 配置 .kiro/，角色是專案經理
```

```
為 coder-agent 配置 .kiro/，角色是全端開發者
```

```
為 qa-agent 配置 .kiro/，角色是 QA 測試工程師
```

### 批次配置（進階）

```
為 ai-dev-agent 配置 .kiro/，角色是 AI 工程師，
專精 LLM 整合、Prompt Engineering、MCP 開發，
部署 ark-mcp-builder 和 ark-pipeline-recipes（llm-tools 食譜）Skills
```

### 預期產出（每個 agent）

- `agents/{name}-agent/.kiro/steering/SOUL.md` — 角色定義
- `agents/{name}-agent/AGENTS.md` — 行為準則（複本，wd 根）
- `agents/{name}-agent/.kiro/steering/MEMORY.md` — 記憶骨架
- `agents/{name}-agent/.kiro/agents/{role}.json` — Agent 配置

### 下一步

全部 agent 配置完成後：
- 單 bot（ark_bot_agent 消費端）→ `ark-agent-bot-builder`
- 團隊 daemon（ark_team_agent）→ `ark-agent-team-builder`
- 獨立 web/TG/排程應用（非套件）→ `ark-webapp-generator`

### 卡關時

- 只配 leader + 1 個 worker 即可（最小可用）
- 不確定角色描述 → 直接說「用預設」
- 目錄不存在 → 先確認 Step 1 已完成
