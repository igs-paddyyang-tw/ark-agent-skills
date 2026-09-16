# Prompt Schema v1 — build_kiro prompts/ 資產格式

> `ark-agent-init/assets/prompts/**/*.md` 每份提詞的 frontmatter 契約。
> 這是範例樣板與 lint 的載體。對齊 `ark-prompt-spec-validator` 的 L1（prompt_lint）。

## Frontmatter 欄位

```yaml
---
name: test-plan                  # 提詞 id（= 檔名去 .md）
description: 依功能規格產出 AC 覆蓋測試計畫   # 一句話
layer: work                      # ops | work
roles: [qa]                      # 配發對象：ops 用 admin/manager/leader/worker；work 用 role-id
tools_required: []               # 引用的 runtime 工具（ops 常含 [query_team_status, reply]）
inputs: [spec_path]              # 佔位符/輸入宣告
outputs:
  format: md                     # md | data | code | none
  contract: ac-table             # ac-table | md-report | endpoint-table | none
example: true                    # 本文必含「## 範例」段
---
```

## 本文三段（固定）

```markdown
## 任務
（指令內容）

## 輸出樣板
（期望輸出骨架，欄位對齊 outputs.contract）

## 範例
### 輸入
（最小而真實的輸入樣本 —— 不用 foo/bar）
### 期望輸出
（照輸出樣板填好的完整範例）
```

## 模板變數（產出時由 build_kiro 從 team.yaml 注入）

| 變數 | 來源 |
|---|---|
| `{{leader_name}}` | instances 中 role=leader 的第一個 key（多個取第一並警告） |
| `{{team_members}}` | instances keys 逗號串 |
| `{{agent_name}}` / `{{role}}` | 當前 agent |
| `{{artifacts_dir}}` | 固定 `artifacts/` |

> 🔴 產出後檔案內**不得殘留** `{{`（validate 驗，對齊 prompt_lint placeholder 檢查）。
> asset 檔（未渲染）允許 `{{var}}`；產出檔（已渲染）不允許。

## 兩層配發

- **ops 層**（跟團隊位置走）：admin / manager / leader / worker
- **work 層**（跟專業角色走）：role-id，配方來源 = references 已定義的角色包，**不另發明**

對照表：`references/role-prompts-map.md`（`role_prompts:` 錨點）。
