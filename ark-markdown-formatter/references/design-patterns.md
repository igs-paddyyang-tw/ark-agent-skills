# 視覺設計模式

## 目錄

1. [Emoji 使用指引](#emoji-使用指引)
2. [表格設計](#表格設計)
3. [Callout 設計](#callout-設計)
4. [Badge 設計](#badge-設計)
5. [分隔與留白](#分隔與留白)
6. [可收合區塊](#可收合區塊)
7. [視覺節奏模板](#視覺節奏模板)

---

## Emoji 使用指引

### 放置規則

| 位置 | 規則 | 範例 |
|------|------|------|
| H2 標題 | ✅ 每個最多一個 | `## 🎯 目標` |
| H3 標題 | ❌ 不放 | `### 功能需求` |
| 列表項 | ⚠️ 偶爾（狀態標示） | `- ✅ 已完成` |
| 段落內 | ❌ 不放 | — |
| 表格 | ⚠️ 狀態欄可用 | `| ✅ | 已部署 |` |

### 推薦 Emoji 集（語意明確）

| 語意 | Emoji | 用途 |
|------|-------|------|
| 目標/重點 | 🎯 | 目標章節 |
| 工具/技術 | 🛠️ | 技術選型、工具 |
| 警告 | ⚠️ | 注意事項 |
| 完成 | ✅ | 清單項完成 |
| 失敗 | ❌ | 清單項未完成 |
| 想法/靈感 | 💡 | Tips |
| 文件 | 📋 | 文件相關 |
| 火箭/部署 | 🚀 | 快速開始、部署 |
| 架構 | 🏗️ | 架構設計 |
| 安全 | 🔒 | 安全相關 |
| 效能 | ⚡ | 效能、速度 |
| 資料庫 | 🗄️ | 資料層 |

### 反模式

```markdown
❌ 過度使用：
## 🎯🚀✨ 超級棒的目標 🎉🎊

✅ 節制使用：
## 🎯 目標
```

---

## 表格設計

### 何時使用表格

- 3 項以上的並列資訊
- key-value 對照
- 功能比較
- 參數列表

### 表格風格

```markdown
| 欄位 | 說明 | 預設值 |
|------|------|--------|
| name | 名稱 | — |
| port | 埠號 | `8080` |
```

### 表格技巧

- 首行粗體或語意明確的欄位名稱
- 無值用 `—`（全形破折號）
- 程式碼用 inline code
- 超過 20 行考慮用 `<details>` 收合
- 對齊冒號：`:---`（靠左）、`:---:`（置中）、`---:`（靠右）

---

## Callout 設計

### GitHub/GitLab 相容語法

```markdown
> [!NOTE]
> 補充資訊，不影響操作。

> [!TIP]
> 實用技巧，提升效率。

> [!IMPORTANT]
> 關鍵資訊，請勿忽略。

> [!WARNING]
> 警告，可能導致問題。

> [!CAUTION]
> 危險操作，不可逆。
```

### 使用時機

| 類型 | 用途 | 頻率 |
|------|------|------|
| NOTE | 額外背景、延伸閱讀 | 自由使用 |
| TIP | 效率技巧、捷徑 | 每章 1-2 個 |
| IMPORTANT | 忽略會出錯的資訊 | 關鍵處 |
| WARNING | 可能破壞性的操作 | 需要時 |
| CAUTION | 不可逆、資料遺失風險 | 僅必要時 |

### 反模式

- 連續 3 個以上 callout（讀者會疲勞）
- 把所有重點都放 callout（失去強調效果）
- callout 內放大段程式碼（改用 code block）

---

## Badge 設計

### 僅限 README 頂部

```markdown
# 專案名稱

![Version](https://img.shields.io/badge/version-2.0.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.12+-yellow)
![Status](https://img.shields.io/badge/status-production-brightgreen)
```

### 常用 Badge 模板

| 用途 | 模板 |
|------|------|
| 版本 | `![Version](https://img.shields.io/badge/version-{v}-blue)` |
| 授權 | `![License](https://img.shields.io/badge/license-{type}-green)` |
| 語言 | `![Lang](https://img.shields.io/badge/{lang}-{version}-yellow)` |
| 狀態 | `![Status](https://img.shields.io/badge/status-{state}-{color})` |
| CI | `![CI](https://github.com/{org}/{repo}/actions/workflows/ci.yml/badge.svg)` |

### 顏色對照

| 顏色 | 語意 |
|------|------|
| `brightgreen` | 正常、穩定 |
| `green` | 好的狀態 |
| `blue` | 資訊性 |
| `yellow` | 注意 |
| `orange` | 警告 |
| `red` | 危險、已棄用 |

---

## 分隔與留白

### 水平線（`---`）

- 用於主要章節群之間的視覺切割
- **不要**每個 H2 都加
- 典型用法：frontmatter 後、附錄前、文末

### 空行節奏

```markdown
## 章節標題

第一段內容，3-5 行。
第二行接續。

- 列表項一
- 列表項二
- 列表項三

下一段過渡文字。

```python
code_example()
```

結語或銜接下一章節。
```

---

## 可收合區塊

### 語法

```markdown
<details>
<summary>點擊展開詳細內容</summary>

內容（注意：`<summary>` 後必須空一行）

| 欄位 | 值 |
|------|---|
| A | 1 |

</details>
```

### 使用時機

- 長表格（> 20 行）
- 冗長的 log 輸出
- 次要參考資訊
- FAQ 問答

---

## 視覺節奏模板

### 標準技術文件

```
[H1 標題]
[一句話描述]
[badge 列（README only）]

---

[H2 🎯 概述]
[2-3 行重點段落]

[H2 🛠️ 技術選型]
[表格]

[H2 🏗️ 架構]
[Mermaid 圖]
[補充說明]

[H2 📋 API]
[表格 + 範例]

[H2 🚀 快速開始]
[步驟列表 + 程式碼]

---

[H2 注意事項]
[callout + 列表]
```

### 報告文件

```
[H1 報告標題]
[日期 + 作者]

[H2 📋 摘要]
[結論先行，3 行以內]

[H2 🔍 分析]
[圖表 + 數據表格]

[H2 💡 建議]
[行動項目列表]

[H2 附錄]
[<details> 收合詳細資料]
```
