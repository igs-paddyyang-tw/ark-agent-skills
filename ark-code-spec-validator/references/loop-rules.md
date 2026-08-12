# Loop Rules — 工作流迴圈規則

> 四段鏈（grill-me → superpowers → spec-executor → validator）的迴圈決策唯一來源。
> 所有 Skill 的迴圈邏輯皆引用本檔，禁止各自硬編碼閾值。

---

## 指標定義

| 指標名 | 全名 | 計算方式 | 用途 |
|--------|------|----------|------|
| `acceptance_rate` | AC 通過率 | `passed_tasks / total_tasks × 100` | spec-executor 驗收結果 |
| `drift_score` | 文件一致性分數 | `API×0.5 + 依賴×0.2 + 測試覆蓋×0.3` | validator 產出的總分 |

> 兩者量尺相同（0-100），但語意不同。`acceptance_rate` 衡量「任務有沒有做完」；`drift_score` 衡量「code 與文件有沒有對齊」。

---

## 閾值表

| 分數區間 | 判定 | 動作 |
|----------|------|------|
| **≥ 90** | ✅ Ship | 標記 milestone 完成，可進入下一階段或交付 |
| **70 – 89** | ⚠️ 方向分流 | 依偏移類型選擇修復路徑（見下方分流表） |
| **< 70** | 🛑 重大問題 | 依偏移類型選擇修復路徑（見下方分流表） |

---

## 方向分流表

當分數 < 90 時，依 Drift Report 中的偏移類型分布決定修復方向：

| 偏移主因 | 判定條件 | 修復動作 | 觸發 Skill |
|----------|----------|----------|-----------|
| `extra_in_code` 為主 | code 有但 docs 沒記載 > 50% 偏移項 | 更新文件（補文件追上 code） | `ark-superpowers`（補 spec/design） |
| `missing_in_code` 為主 | docs 定義但 code 未實作 > 50% 偏移項 | 補實作（code 追上 docs） | `ark-spec-executor`（補實作） |
| `mismatch` / 依賴違規為主 | 實作與文件矛盾 或 import 違規 > 50% 偏移項 | 回頭釐清需求（設計本身有問題） | `ark-grill-me`（重新拷問） |

### 分流判定邏輯

1. 從 Drift Report 提取所有偏移項
2. 分類計數：`extra_in_code` / `missing_in_code` / `mismatch_or_violation`
3. 取佔比最大者為「主因」
4. 若各類平均（無 > 50%），預設走 `ark-grill-me`（最保守）

---

## 保險絲（Fuse）

| 條件 | 動作 |
|------|------|
| `loop_count ≥ 3` | 🚨 **人工介入**——停止自動迴圈，向使用者回報歷次 drift_score 趨勢並請求指示 |

### 保險絲觸發時的回報格式

```
🚨 迴圈保險絲觸發（已執行 {loop_count} 輪）

歷次分數：{drift_scores 陣列}
主要未解決問題：{top 3 drift items}

請決定：
1️⃣ 人工修復後重跑 validator
2️⃣ 降低範圍（移除部分 spec 項目）
3️⃣ 接受現狀交付
```

---

## 各 Skill 責任

| Skill | 讀取 | 寫入 |
|-------|------|------|
| ark-grill-me | — | — |
| ark-superpowers | — | — |
| ark-spec-executor | 閾值表（判定是否自動重跑） | — |
| ark-code-spec-validator | 閾值表 + 方向分流表 | — |
| Pipeline 狀態檔 | 全部讀 | 全部寫（見 pipeline-state-schema.md） |

---

## 版本

- v1.0 — 2026-08-11 初版
