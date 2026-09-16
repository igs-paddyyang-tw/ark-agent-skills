# Role → Prompts 對照表

> **機器解析錨點**：下方 `role_prompts:` YAML block 是**唯一清單來源**。
> `build_kiro.py` 的 `_build_prompts()` 解析此表配發提詞，**不在 Python 硬編 if/elif**。
> 加角色 = 改此表 + 在 assets/prompts/ 補檔，不改 code。

## 雙層配發

- **ops 層**：跟「團隊位置」走（admin/manager/leader/worker）—— 每個 agent 依 `role`(tier) 配發
- **work 層**：跟「專業角色」走（role-id = role-profile 的 base_role）—— 依 `base_role` 配發
- 一個 agent 拿到的 = ops 身分的提詞 ∪ role-id 的提詞（聯集）
- 找不到 role-id 的對照 → 只配 ops 層並輸出提示行（**不靜默**）
- work 層對照列了但 assets/prompts/work/ 缺檔 → **報錯**（消滅幻覺索引）

## 對照（機器解析錨點：`role_prompts:`）

```yaml
role_prompts:
  ops:
    admin:   [route-message, service-check]
    manager: [route-message]
    leader:  [daily-report, team-check]
    worker:  [daily-report]
  work:
    architect:      [analyze-req, scaffold-api]
    fullstack-coder: [analyze-req]
    qa:             [test-plan]
    qa-manager:     [test-plan, data-query-routing]
    game-planner:   [gdd-draft, feature-spec]
    math-designer:  [par-sheet, balance-tuning, data-query-routing]
    liveops:        [event-spec]
    game-analyst:   [kpi-review, data-query-routing]
    data-analyst:   [data-query-routing]
    producer:       [milestone-plan]
```

> ops 提詞在 `assets/prompts/`（現階段平鋪，向後相容）；
> work 提詞在 `assets/prompts/work/`。
> 每個 work 提詞列於此表就**必須存在**於 assets（`validate` 驗，缺檔 exit≠0）。
