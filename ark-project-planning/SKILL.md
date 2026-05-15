---
name: ark-project-planning
author: paddyyang
description: |
  標準化專案計畫流程。收到新功能需求時使用：釐清需求、撰寫規格文件、拆解任務、
  分派給 Agent、追蹤進度、驗收交付。
  Use when receiving new feature requests, project planning, task delegation to agents.
  觸發條件：新功能、新需求、派工、拆任務、專案規劃、project plan。
metadata:
  version: "2.0"
---

# 專案計畫 v2.0

標準化工作流程：需求 → 釐清 → 規格 → 拆解 → 分派 → 追蹤 → 驗收

## 與 ark-superpowers 分工

```
ark-project-planning → 「怎麼管理」（流程 6 步）
ark-superpowers      → 「產出什麼」（spec / design / plan 文件）
```

Step 2 呼叫 ark-superpowers 產出規格文件，其餘步驟由本 Skill 管理。

## 快速模式

需求滿足以下全部條件時，可跳過 Step 1-2：
- 需求 ≤ 1 句話且明確
- 單人任務（只派給 1 個 agent）
- 大小 ≤ S

直接從 Step 3 開始，派工格式不變。

---

## Step 1：需求釐清

1. 列出假設（ASSUMPTIONS）— 不要默默填補模糊需求
2. 提出釐清問題（最多 3 個關鍵問題）
3. 將模糊需求轉為可驗證的成功標準

```
ASSUMPTIONS：
1. [假設 1]
2. [假設 2]
→ 請確認或修正
```

**限時**：使用者 1 輪未回覆 → 用假設值繼續。

**驗證**：使用者確認需求正確，成功標準具體可驗證。

## Step 2：撰寫規格文件

呼叫 `/ark-superpowers` 產出規格（至少 one-pager）：

- 簡單需求 → one-pager（`docs/one-pagers/`）
- 複雜需求 → 完整 spec（`docs/specs/`）

規格必須包含：
- 目標 + 非目標
- 涉及 Agent 表
- 驗收標準（可勾選）
- 時程估算

**驗證**：規格檔案存在，驗收標準具體可測。

## Step 3：任務拆解

1. 畫依賴圖（什麼先做、什麼可並行）
2. 垂直切片（一次做完一個功能的全部層）
3. 每個任務寫驗收標準

大小標準：
- **XS** (1 檔) / **S** (1-2 檔) / **M** (3-5 檔)
- L (5-8 檔) → 建議再拆
- XL (8+ 檔) → **必須拆分**

使用 `create_task(title, assignee, priority, ...)` 建立到任務板。

**驗證**：每個任務有驗收標準，沒有 XL 任務，依賴順序正確。

## Step 4：分派任務

使用 `delegate_task` 分派，**必須用以下格式**：

```
📋 任務：{名稱}
📄 規格：specs/{檔名}.md（第 N 節）
🎯 你負責：{具體描述}
📁 範圍：{檔案/目錄}
⏰ 優先級：高/中/低
📎 依賴：{無 / 等待 XXX}
✅ 驗收：{完成條件}
📏 大小：XS / S / M
```

順序：先無依賴 → 可並行同時發 → 有依賴等前置完成。

**驗證**：每個任務都已分派，格式完整。

## Step 5：追蹤進度

1. `query_team_status()` 檢查 Agent 狀態
2. `list_tasks("in_progress")` 確認進度
3. 前置完成 → 分派下一批
4. 逾期（>4h 無更新）→ 催促
5. 阻塞 → 介入協助或重新分配

## Step 6：驗收

對照規格書驗收標準逐條確認：

```
✅ 驗收清單：
- [ ] 功能符合規格書
- [ ] 跨 Agent 介面一致
- [ ] 無硬編碼密鑰
- [ ] 產出檔案路徑正確
```

通過 → `update_task(task_id, "completed")` + 記錄 `verified_by`。
不通過 → 具體指出問題，發回修正。

完成後用 `reply(text)` 回報使用者。

---

## 紅旗（禁止事項）

- ❌ 沒有規格就分派
- ❌ 任務沒有驗收標準
- ❌ delegate_task 不用 📋 模板
- ❌ 分派後不追蹤
- ❌ 跳過驗收直接交付
- ❌ 所有任務都是 XL

## 反合理化

| 藉口 | 現實 |
|------|------|
| 直接開始做比較快 | 沒規格的返工 > 寫規格時間 |
| 任務很明顯不用拆 | 寫下來才能追蹤，也能發現遺漏 |
| Agent 自己會知道 | 明確指令減少來回，省 token 省時間 |
| 驗收太麻煩 | 不驗收就不知道做對沒 |
