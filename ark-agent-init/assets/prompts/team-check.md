---
name: team-check
description: 確認團隊狀態、查任務板、依計劃派工或追蹤進度
layer: ops
roles: [leader]
tools_required: [query_team_status, list_tasks, reply]
inputs: []
outputs:
  format: none
  contract: none
example: true
---

## 任務

用 `query_team_status()` 確認團隊狀態，然後：
1. 查看任務板（`list_tasks`）
2. 依計劃派工或追蹤進度
3. 更新 MEMORY.md
4. 用 `reply` 回報當前狀態

## 輸出樣板

```
團隊：{X}/{N} running
任務板：進行中 {a} · 待派 {b} · 已完成 {c}
動作：{已派工 <task> 給 <member> | 追蹤 <task> | 無}
```

## 範例

### 輸入
（隊長定期巡檢，無額外輸入）

### 期望輸出
團隊：3/3 running
任務板：進行中 1 · 待派 1 · 已完成 2
動作：已派工「RTP 驗證」給 {{team_members}} 中的 functional-qa
