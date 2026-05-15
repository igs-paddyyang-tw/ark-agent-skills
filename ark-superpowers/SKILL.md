---
author: paddyyang
name: ark-superpowers
description: |
  產出工程標準化文件（Spec 規格、Design 設計/ADR、Execution Plan 執行計畫），
  基於 power-engineer-skills 框架，協助資深工程師與技術領導者
  將技術決策轉化為可溯源的標準化資產。
  支援完整版與 One Pager 輕量版、ADR 自動編號、雙語模板（繁中/英文）、
  品質檢查清單、RFC 流程整合、Git hook 文件完整性驗證。
  使用此 Skill 當使用者提及 superpowers、工程標準化、標準化文件、
  寫 spec、規格文件、需求文件、設計文件、design doc、ADR、架構決策、
  執行計畫、execution plan、技術提案、系統設計、RFC、里程碑、
  或任何需要產出結構化工程決策文件的場景。
---

# ark-superpowers

產出工程標準化文件，將技術決策轉化為可溯源的標準化資產。

## 觸發條件

- 「superpowers」、「工程標準化」、「標準化文件」
- 「寫 spec」、「規格文件」、「需求文件」、「RFC」
- 「設計文件」、「design doc」、「ADR」、「架構決策」
- 「執行計畫」、「execution plan」、「里程碑」
- 「技術提案」、「technical proposal」、「系統設計」
- 「review 文件」、「文件檢查」

---

## 文件類型

| 類型 | 代號 | 用途 | 產出路徑 |
|------|------|------|----------|
| One Pager | onepager | 合併版：問題+方案+計畫（初期構想） | `docs/one-pagers/{name}.md` |
| 規格文件 | spec | 完整需求定義、NFR、成功指標 | `docs/specs/{name}-spec.md` |
| 設計文件 | design | 完整架構設計、數據流、故障隔離 | `docs/designs/{name}-design.md` |
| 架構決策 | adr | 單一決策記錄（MADR 格式） | `docs/designs/adr/{NNN}-{title}.md` |
| 執行計畫 | plan | 完整里程碑、風險、驗證、回滾 | `docs/plans/{name}-plan.md` |

### 文件深度分級

```
One Pager（1 份，快速決策）
  ↓ 需要正式提案時升級
完整版（spec + design + plan，3 份獨立文件）
```

One Pager 的 frontmatter 有 `upgraded_to` 欄位，升級後指向完整文件，保留追溯性。

每類文件支援兩種語言：繁體中文（預設）、English。

---

## 互動流程

```
1. 辨識意圖 → 確認文件類型（onepager / spec / design / adr / plan）
2. 確認語言 → 繁體中文（預設）或 English
3. 收集資訊 → 引導使用者提供關鍵內容
4. 產出文件 → 依模板填充，存入對應路徑
5. 品質檢查 → 依 checklist 驗證完整性
6. （ADR）自動編號 + 更新索引
7. （升級）One Pager → 完整版時，更新 upgraded_to 欄位
```

### 意圖對應表

| 使用者意圖 | 動作 |
|------------|------|
| 「one pager」、「簡短版」、「快速」 | 產出合併版到 `docs/one-pagers/` |
| 「幫我寫 spec」、「完整規格」 | 產出完整 spec 到 `docs/specs/` |
| 「記錄架構決策」、「新增 ADR」 | 自動編號 → 產出 ADR |
| 「寫設計文件」、「完整設計」 | 產出完整 design 到 `docs/designs/` |
| 「規劃執行計畫」 | 產出完整 plan 到 `docs/plans/` |
| 「全套文件」 | 依序產出 spec → design → plan |
| 「升級這份 one pager」 | 從 one-pager 展開為 spec + design + plan |
| 「review 這份文件」 | 依 checklist 檢查品質 |
| 「English version」 | 使用英文模板 |

### 模式選擇邏輯

- 使用者說「簡短」、「one pager」、「快速」、「摘要版」→ One Pager（合併一份到 `docs/one-pagers/`）
- 使用者說「完整」、「詳細」、「full」、「正式」→ 完整版（分別到 specs/designs/plans/）
- 未指定 → 預設 One Pager，主動詢問是否需要完整版

### 語言選擇邏輯

- 使用者用中文提問 → 繁體中文模板（預設）
- 使用者說「English」、「用英文寫」→ 英文模板
- frontmatter 加入 `language: zh-TW | en` 欄位

---

## ADR 自動編號

建立 ADR 時自動處理編號：

1. 掃描 `docs/designs/adr/` 目錄下所有 `*.md`（排除 `_index.md`）
2. 從檔名提取編號（格式 `{NNN}-`），取最大值 +1
3. 若目錄為空，從 001 開始
4. 檔名格式：`{NNN}-{kebab-case-title}.md`
5. 產出後自動更新 `docs/designs/adr/_index.md` 索引

索引格式：
```markdown
# Architecture Decision Records

| # | 標題 | 狀態 | 日期 |
|---|------|------|------|
| 001 | 決策標題 | accepted | 2026-05-11 |
```

---

## 品質檢查清單

產出文件後，自動依據以下清單驗證（通過/未通過，不評分）：

### Spec 檢查項
- [ ] 有明確的問題陳述（摘要或問題章節）
- [ ] 目標與非目標已區分
- [ ] 非功能性需求有量化指標
- [ ] 成功指標可衡量
- [ ] 開放問題已列出

### Design 檢查項
- [ ] 至少列出 2 個替代方案
- [ ] 決策理由明確
- [ ] 有故障降級策略
- [ ] 安全性已考量
- [ ] 數據流清晰

### ADR 檢查項
- [ ] 背景描述清楚
- [ ] 至少 2 個選項
- [ ] 決策明確且有理由
- [ ] 後果（正面 + 負面）已列出

### Execution Plan 檢查項
- [ ] 里程碑有明確時程
- [ ] 每個任務有驗收條件
- [ ] 風險已識別並有緩解策略
- [ ] 回滾計畫存在
- [ ] 依賴關係已釐清

---

## 模板參考

完整模板存放於附帶資源，依需求載入：

| 模板 | 路徑 |
|------|------|
| 繁中 One Pager（合併版） | `references/templates/zh-TW/onepager.md` |
| 繁中完整 Spec | `references/templates/zh-TW/spec-full.md` |
| 繁中完整 Design | `references/templates/zh-TW/design-full.md` |
| 繁中 ADR | `references/templates/zh-TW/adr.md` |
| 繁中完整 Plan | `references/templates/zh-TW/plan-full.md` |
| 英文 One Pager（合併版） | `references/templates/en/onepager.md` |
| 英文完整 Spec | `references/templates/en/spec-full.md` |
| 英文完整 Design | `references/templates/en/design-full.md` |
| 英文 ADR | `references/templates/en/adr.md` |
| 英文完整 Plan | `references/templates/en/plan-full.md` |
| 品質檢查清單 | `references/review-checklist.md` |
| 框架對照表 | `references/framework-mapping.md` |

產出文件時，載入對應模板作為骨架，填入使用者提供的內容。

---

## Git Hook 整合

### Kiro Hook（自動觸發）

當 `docs/specs/`、`docs/designs/`、`docs/plans/` 下的 `.md` 檔案被編輯時，
自動檢查 frontmatter 必要欄位和必要章節是否完整。

### pre-commit 腳本

`scripts/check_doc_completeness.py` 提供 CLI 檢查：
- 驗證 frontmatter：`title`、`status`、`created` 必要
- 驗證章節：依 `type` 欄位對應必要章節清單
- 輸出：PASS / FAIL + 缺失項目

---

## 與現有系統整合

- **Wiki**：產出文件可透過 `wiki_ingest` 匯入知識庫
- **Workflow**：可定義 YAML 工作流自動化文件產生
- **Git RFC**：建議搭配 `feature/rfc-{title}` 分支 + PR review

---

## 注意事項

- frontmatter 欄位名一律英文（機器可讀），內容依語言設定
- ADR 一旦 accepted 不可刪除，只能 superseded
- One Pager 適合初期構想，正式提案建議升級為完整版
- 「全套文件」模式下，後續文件自動引用前序文件（spec → design → plan）
- 檔名一律 kebab-case，遵循專案命名規範
