---
name: ark-dashboard-health
description: |
  [DEPRECATED — 已併入 ark-env-doctor（端點模式 `env_doctor.py --endpoints`；原文在 references/dashboard-health.md）]
  原說明（保留觸發詞，讓舊說法仍導向新位置）：自動化測試 Dashboard 所有 API 端點 + SSE 連線 + 前端頁面可用性。 產出 Health Report（通過/失敗清單 + 回應時間）。 使用此 Skill 當使用者提及 dashboard 正常嗎、API 測試、SSE 測試、 健康檢查、端點測試、dashboard health、服務可用性、 或任何需要驗證 Web Dashboard 是否正常運作的場景。
metadata:
  version: "2.0.0"
  schema_version: "1.2"
  status: deprecated
  updated: 2026-10-29
  category: ops
  form: instruction
  domain: general
  author: paddyyang
---

# ark-dashboard-health（已併入 ark-env-doctor）

本 skill 已併入 **`ark-env-doctor`**：端點模式 `env_doctor.py --endpoints`。原內容原樣保留在 `ark-env-doctor/references/dashboard-health.md`。

消費端若還沒有 `ark-env-doctor`（`mirror_sync` 不會自動安裝新 skill）：

```bash
cp -r <ark-agent-skills>/ark-env-doctor .kiro/skills/
```

## 版本

| 版本 | 日期 | 變更 |
|---|---|---|
| 2.0.0 | 2026-10-29 | **Breaking**：併入 `ark-env-doctor`，內容移至 `ark-env-doctor/references/dashboard-health.md`，本目錄只留轉址；角色對照表改指 ark-env-doctor |
