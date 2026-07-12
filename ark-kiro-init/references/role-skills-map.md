# 角色 Skills 對照表

## 預裝規則

`build_kiro.py` 依角色自動安裝對應 Skills。

## 對照表

| 角色 | 預裝 Skills | 說明 |
|------|------------|------|
| **全員（Loop 五件套）** | `ark-grill-me` `ark-superpowers` `ark-spec-executor` `ark-code-spec-validator` `ark-wiki-engine` | 需求→文件→執行→驗證→知識（迴圈工程核心） |
| admin | `ark-planning-with-files` | 輕量管理+持久任務 |
| leader | `ark-project-planning` `ark-uml-generator` `ark-doc-coauthoring` | 規劃+圖表+共筆 |
| ai-dev | `ark-skill-creator` `ark-mcp-builder` `ark-llm-tools` | Skill 開發+MCP+LLM |
| coder | `ark-skill-creator` `ark-code-review` | 開發+審查 |
| qa | `ark-code-review` `ark-test-runner` | 審查+測試 |
| devops | `ark-docker-deploy` `ark-env-doctor` | 部署+環境 |
| designer | `ark-frontend-design` `ark-canvas-design` `ark-ui-design-system` | 設計 |
| analyst | `ark-kpi-calculator` `ark-chart-generator` `ark-etl-pipeline` | 分析+圖表+ETL |

## 來源優先順序

```
1. ai-team-agent/skills/{skill-name}/（同 repo，完整版）
2. .kiro/skills/{skill-name}/（全域，完整版）
3. 僅 SKILL.md（輕量版，省空間）
```

## 安裝模式

| 模式 | 指令 | 說明 |
|------|------|------|
| full | `build_kiro.py --clone-skills` | 完整複製（含 scripts/references） |
| light | `build_kiro.py --clone-skills --light` | 僅 SKILL.md |
| skip | `build_kiro.py`（預設） | 不安裝，只建空目錄 |
