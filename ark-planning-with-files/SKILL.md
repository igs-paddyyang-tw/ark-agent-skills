---
name: ark-planning-with-files
description: |
  持久化任務追蹤：複雜任務（3+ 步驟）自動建立 3-File Pattern（task_plan.md / findings.md / progress.md），
  防止 context 丟失、goal drift、錯誤重複。參考 Manus 模式。
  使用此 Skill 當使用者提及 planning with files、任務追蹤、持久化計畫、
  3-file pattern、防止遺忘、長任務管理、Manus workflow、
  或任何需要跨 session 保持任務狀態的場景。
metadata:
  author: paddyyang
  version: "1.0"
  updated: 2026-05-16
  reference: https://github.com/OthmanAdi/planning-with-files
---

# ark-planning-with-files

複雜任務持久化追蹤 — 3-File Pattern，防止 goal drift 與 context 丟失。

## 觸發條件

- 任務 ≥ 3 步驟
- 跨多個工具呼叫的研究/建構任務
- 使用者說「建立計畫」「追蹤進度」「planning」
- 預期超過 50 次工具呼叫

## 核心原則

```
Context Window = RAM（揮發性、有限）
Filesystem = Disk（持久性、無限）
→ 重要資訊必須寫入磁碟
```

---

## 3-File Pattern

每個複雜任務建立 3 個檔案於工作目錄：

| 檔案 | 用途 | 更新頻率 |
|------|------|---------|
| `task_plan.md` | 階段分解 + checkbox 進度 | 每完成一個階段 |
| `findings.md` | 研究發現 + 錯誤紀錄 | 每 2 次操作後 |
| `progress.md` | Session log + 測試結果 | 每個 session |

---

## 流程

### 1. 建立計畫（任務開始時）

```markdown
# Task Plan: {任務名稱}

## 目標
{一句話描述成功標準}

## 階段
- [ ] Phase 1: {描述}
- [ ] Phase 2: {描述}
- [ ] Phase 3: {描述}

## 約束
- {時間/技術/依賴限制}

## 完成條件
- {可驗證的 DoD}
```

### 2. 2-Action Rule（執行中）

每 2 次 view/browser/search 操作後，將發現寫入 `findings.md`：

```markdown
## {時間戳}

### 發現
- {重點 1}
- {重點 2}

### 錯誤（如有）
- {錯誤描述} → {嘗試的解法} → {結果}
```

### 3. 進度更新（每個階段完成時）

更新 `task_plan.md` 的 checkbox + 在 `progress.md` 追加：

```markdown
## {時間戳} — Phase {N} 完成

- 耗時：{估計}
- 產出：{檔案/結果}
- 下一步：Phase {N+1}
```

### 4. 完成驗證（任務結束前）

停止前必須檢查：
- [ ] task_plan.md 所有 Phase 都 ✅
- [ ] 完成條件全部滿足
- [ ] findings.md 無未解決的錯誤
- [ ] progress.md 有最終摘要

---

## 何時使用 / 何時跳過

**使用：**
- 多步驟任務（3+ 步驟）
- 研究任務
- 建構/建立專案
- 跨多次工具呼叫的任務

**跳過：**
- 簡單問答
- 單檔修改
- 快速查詢

---

## 與現有機制整合

| 機制 | 定位 | 關係 |
|------|------|------|
| MEMORY.md | 跨任務的專案記憶 | 任務完成後摘要寫入 MEMORY |
| board.json | 結構化任務板 | task_plan.md 是單一任務的詳細展開 |
| knowledge/wiki/ | 長期知識 | findings.md 有價值的部分歸檔到 wiki |

---

## 防止常見失敗

| 失敗模式 | 3-File 如何防止 |
|---------|---------------|
| Goal drift（忘記目標） | task_plan.md 開頭有目標 + 完成條件 |
| 重複犯錯 | findings.md 記錄所有錯誤 + 嘗試 |
| Context 丟失（/clear 後） | 檔案在磁碟，重新讀取即恢復 |
| 宣稱完成但沒做完 | 完成驗證 checklist 強制檢查 |

---

## 注意事項

- 檔案放在任務相關的工作目錄（非 knowledge/）
- 任務完成後可刪除或歸檔到 knowledge/
- 不要把 3-file 用在簡單任務（過度工程）
- findings.md 是 append-only，不刪除舊記錄
