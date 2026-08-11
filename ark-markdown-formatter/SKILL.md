---
name: ark-markdown-formatter
description: |
  將任何內容轉換為精美、結構化的 Markdown 文件。
  聚焦繁體中文排版、視覺層級設計、Mermaid 圖表整合與文件模板。
  使用此 Skill 當使用者提及格式化 Markdown、美化文件、精美排版、
  寫 README、產出技術文件、Markdown 模板、報告排版、文件美化、
  changelog、指南撰寫、中文排版、callout、badge、
  或任何需要將內容轉換為高品質 Markdown 文件的場景。
  不適用於 PDF/Word/PPT 等非 Markdown 格式（請使用對應的 ark-*-tool）。
metadata:
  author: paddyyang
  version: "1.0.0"
  updated: 2026-06-05
---

# ark-markdown-formatter

將任何內容轉換為精美、結構化的 Markdown 文件。

## 觸發條件

- 「格式化 Markdown」、「美化文件」、「精美排版」
- 「寫 README」、「產出技術文件」、「文件模板」
- 「報告排版」、「文件美化」、「changelog」
- 「中文排版」、「callout」、「badge」
- 「幫我排版」、「整理成 Markdown」

## 核心哲學

```
內容第一 → 結構清晰 → 視覺引導 → 精緻收尾
```

精美不是堆疊裝飾，而是讓讀者一眼抓住重點、順暢閱讀。

---

## 工作流程

### 步驟 1：辨識文件類型

判斷使用者需要的文件類型，載入對應模板：

| 文件類型 | 模板 | 適用場景 |
|---------|------|---------|
| README | `references/templates/readme.md` | 專案介紹頁 |
| 技術報告 | `references/templates/report.md` | 分析結果、調查報告 |
| 操作指南 | `references/templates/guide.md` | How-to、教學 |
| CHANGELOG | `references/templates/changelog.md` | 版本異動記錄 |
| 會議紀錄 | `references/templates/meeting.md` | 會議摘要與行動項目 |
| 比較文件 | `references/templates/comparison.md` | 方案比較、選型分析 |
| 通用文件 | （無需模板） | 自由格式 |

若無明確類型，直接套用通用美化規則。

### 步驟 2：套用中文排版規範

載入 `references/style-rules.md` 中的完整規範，核心規則：

1. **中英文間加空格** — `使用 Markdown 格式` 而非 `使用Markdown格式`
2. **全形標點** — 逗號用 `，` 句號用 `。` 分號用 `；`
3. **數字與單位** — `8 個項目`、`100%`、`3.5 秒`
4. **段落節奏** — 每段 3-5 行，避免巨型段落
5. **Heading 層級** — 遞增不跳級（H1→H2→H3），每文件一個 H1

### 步驟 3：套用視覺設計模式

載入 `references/design-patterns.md`，選用適當的設計元素：

| 元素 | 用途 | 節制原則 |
|------|------|---------|
| Emoji | H2 段落標題的視覺錨點 | 每個 H2 最多一個，H3 以下不放 |
| 表格 | 結構化比較、參數列表 | 3+ 項並列資訊改用表格 |
| Callout | 重要提示、警告、技巧 | 每章節最多 1-2 個 |
| Badge | 版本號、狀態、技術棧標籤 | 僅用於 README 頂部 |
| 分隔線 | 主要章節之間的視覺切割 | 不要每個 H2 都加 |
| 程式碼區塊 | 範例、設定、指令 | 必須標注語言 |
| Mermaid | 流程、架構、關係圖 | 取代冗長文字描述 |

### 步驟 4：考慮 Mermaid 圖表

若內容涉及流程、架構、或關係，載入 `references/mermaid-guide.md` 選擇圖表：

| 內容特徵 | 建議圖表 |
|---------|---------|
| 步驟流程、決策邏輯 | flowchart |
| 元件互動、API 呼叫 | sequenceDiagram |
| 資料模型 | erDiagram |
| 時間軸、里程碑 | timeline / gantt |
| 概念層級、分類 | mindmap |
| 系統架構 | graph LR |
| 狀態變遷 | stateDiagram-v2 |

不要為了放圖而放圖——只在圖表能比文字更清楚時使用。

### 步驟 5：最終品質檢查

產出前逐項檢查：

- [ ] Heading 層級遞增不跳級
- [ ] 列表前後有空行
- [ ] 程式碼區塊前後有空行且標注語言
- [ ] 中英文間有空格
- [ ] 全形標點使用正確
- [ ] Emoji 節制（僅 H2）
- [ ] 表格對齊
- [ ] 無孤立短段（< 2 行的段落考慮合併）
- [ ] 檔案結尾有一個換行

---

## 設計原則

### 結構金字塔

```
H1 — 文件標題（唯一）
├── H2 — 主要章節（3-7 個）
│   ├── H3 — 子章節
│   │   └── H4 — 細項（少用）
│   └── H3
└── H2
```

**黃金數字**：一份文件 H2 控制在 3-7 個。超過 7 個考慮拆分文件。

### 視覺節奏

好的 Markdown 有節奏感：

```
[標題]
[短段落 2-3 行]

[表格或列表]

[短段落]

[程式碼區塊或圖表]

[過渡句 → 下一章節]
```

避免「全是段落」或「全是列表」的單調結構。交錯使用不同元素。

### Callout 語法

使用 GitHub/GitLab 相容的 blockquote callout：

```markdown
> [!NOTE]
> 提供額外資訊或補充說明。

> [!TIP]
> 實用建議，幫助讀者更有效率。

> [!IMPORTANT]
> 關鍵資訊，忽略可能導致問題。

> [!WARNING]
> 警告，操作可能造成不可逆的影響。

> [!CAUTION]
> 危險操作，需要特別注意。
```

### Badge 設計（僅 README 頂部）

```markdown
![Version](https://img.shields.io/badge/version-1.0.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.12+-yellow)
```

---

## 輸入/輸出範例

### 輸入：雜亂筆記

```
我們決定用Go寫API gateway因為效能好
python用來做報表服務
前端用nextjs
資料庫是postgresql
```

### 輸出：精美 Markdown

```markdown
## 🛠️ 技術選型

| 元件 | 技術 | 選擇理由 |
|------|------|---------|
| API Gateway | Go | 高效能、goroutine 並發 |
| 報表服務 | Python | 資料處理生態系豐富 |
| 前端 | Next.js | SSR + React 生態 |
| 資料庫 | PostgreSQL | 開源、ACID、擴充性佳 |
```

---

## 附帶資源索引

| 資源 | 路徑 | 用途 |
|------|------|------|
| 排版規範 | `references/style-rules.md` | 中文排版 + markdownlint 規則 |
| 設計模式 | `references/design-patterns.md` | 視覺元素使用指引 |
| Mermaid 指引 | `references/mermaid-guide.md` | 圖表選型 + 語法速查 |
| 文件模板 | `references/templates/` | 6 種開箱即用的文件骨架 |

---

## 邊界案例

| 情境 | 處理方式 |
|------|---------|
| 使用者提供 Word/PDF 內容 | 提取文字後格式化為 Markdown |
| 極長文件（> 500 行） | 建議拆分，提供目錄結構 |
| 需要 PDF/Word 輸出 | 先產出 Markdown，引導使用 ark-pdf-tool / ark-docx-tool |
| 英文文件 | 停用中文排版規則，使用英文慣例 |
| 程式碼為主的文件 | 以程式碼區塊為主體，文字為輔助說明 |

## 注意事項

- 本 Skill 產出 `.md` 檔案，不產出 PDF/Word
- 中文排版規則僅在內容含中文時啟用
- Mermaid 圖表需確認目標平台支援（GitHub/GitLab/VS Code 皆支援）
- Badge 僅限 README 頂部，其他文件類型不使用
- 表格行數超過 20 行時，考慮改用可收合的 `<details>` 區塊
