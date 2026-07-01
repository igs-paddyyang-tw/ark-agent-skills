# 角色 Skills 對照表

## 預裝規則

`build_kiro.py` 依角色自動安裝對應 Skills。

## 對照表

| 角色 | 預裝 Skills | 說明 |
|------|------------|------|
| **全員** | `ark-wiki-engine` | 知識庫管理（自我成長核心） |
| admin | （無額外） | 輕量管理 |
| leader | `ark-superpowers` `ark-code-spec-validator` `ark-project-planning` `ark-uml-generator` `ark-doc-coauthoring` | 規格+驗證+規劃 |
| ai-dev | `ark-skill-creator` `ark-grill-me` `ark-superpowers` | Skill 開發+設計拷問 |
| coder | `ark-skill-creator` `ark-code-review` | 開發+審查 |
| qa | `ark-code-spec-validator` `ark-code-review` | 驗證+審查 |
| devops | `ark-docker-deploy` | 部署 |
| designer | `ark-frontend-design` `ark-canvas-design` | 設計 |
| analyst | `ark-kpi-calculator` `ark-chart-generator` | 分析+圖表 |

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
