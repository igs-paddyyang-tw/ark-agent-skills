# 命名規範

## Instance 命名

- 格式：`{role}-agent`（kebab-case + `-agent` 後綴）
- Regex：`^[a-z][a-z0-9-]*-agent$`
- 長度：3-30 字元（含 -agent）
- 禁止：大寫、底線、空格、特殊字元

## 範例

| 使用者輸入 | 轉換結果 |
|-----------|---------|
| Tech Lead | leader-agent |
| Frontend Developer | frontend-agent |
| QA Engineer | qa-agent |
| 資料工程師 | data-engineer-agent |
| ML Engineer | ml-engineer-agent |
| DevOps | devops-agent |

## Working Directory

- 格式：`agents/{instance_name}`
- 範例：`agents/leader-agent`

## Description

- 格式：`"{emoji} {角色名} — {職責}"`
- 範例：`"🔱 技術負責人 — 架構規劃、任務拆解、品質把關"`
