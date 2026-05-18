---
name: ark-md-to-pixi-ast
description: |
  將 Markdown 文件轉換為 PixiJS 可渲染的 AST JSON（扁平節點陣列）。
  確定性轉換：同輸入永遠產出同輸出。
  用於 WebGL 文字渲染管線、Dashboard Agent、遊戲內 UI。
  使用此 Skill 當使用者提及 Markdown 轉 PixiJS、MD to AST、
  文字渲染 JSON、Pixi 節點、WebGL 文字、渲染管線、
  或任何需要將 Markdown 轉為可渲染結構的場景。
metadata:
  author: paddyyang
  version: "1.0"
  updated: 2026-05-18
  category: rendering-pipeline
  input_type: markdown
  output_type: json
  deterministic: true
---

# ark-md-to-pixi-ast

將 Markdown 轉換為 PixiJS 可渲染的 AST JSON。

## 觸發條件

- 「Markdown 轉 PixiJS」、「MD to AST」、「md-to-pixi」
- 「文字渲染 JSON」、「Pixi 節點結構」
- 「WebGL 文字」、「渲染管線」
- 「把這份 MD 轉成可渲染的格式」

---

## 轉換規則

### 節點類型映射

| Markdown | nodeType | fontSize | fontFamily |
|----------|----------|----------|------------|
| `#` | Heading1 | 48 | MSDF_Bold |
| `##` | Heading2 | 32 | MSDF_Regular |
| `###` | Heading3 | 24 | MSDF_Regular |
| 段落 | Text | 16 | MSDF_Regular |
| `` ``` `` | CodeBlock | 14 | MSDF_Mono |
| `- item` | ListItem | 16 | MSDF_Regular |
| `> quote` | Blockquote | 16 | MSDF_Italic |
| `---` | Divider | 0 | — |

### Layout 參數

| 參數 | 值 |
|------|-----|
| viewport | 1280×720 |
| x | 80（固定左邊距） |
| maxWidth | 960 |

### yOffset 增量

| nodeType | 增量 |
|----------|------|
| Heading1 | +80 |
| Heading2 | +60 |
| Heading3 | +50 |
| Text | +40 |
| CodeBlock | +80 |
| ListItem | +30 |
| Blockquote | +50 |
| Divider | +30 |

---

## 執行流程

```
1. 接收 Markdown 文字輸入
2. 逐行解析，識別節點類型
3. 依映射表填充 fontSize / fontFamily
4. 計算 yOffset（累加前一節點增量）
5. 產出 JSON（扁平 nodes 陣列）
6. 驗證輸出（7 項規則）
```

---

## 輸出格式

**嚴格規則：只輸出 JSON，不加任何說明文字。**

```json
{
  "nodes": [
    {
      "id": "n1",
      "nodeType": "Heading1",
      "text": "標題文字",
      "fontSize": 48,
      "fontFamily": "MSDF_Bold",
      "x": 80,
      "yOffset": 0
    },
    {
      "id": "n2",
      "nodeType": "Text",
      "text": "段落內容",
      "fontSize": 16,
      "fontFamily": "MSDF_Regular",
      "x": 80,
      "yOffset": 80,
      "maxWidth": 960,
      "wordWrap": true
    }
  ]
}
```

### 欄位規則

| 欄位 | 必要 | 條件 |
|------|------|------|
| id | ✅ | `n{序號}`，從 1 開始，連續 |
| nodeType | ✅ | 必須是映射表中的值 |
| text | ✅ | Divider 為空字串 |
| fontSize | ✅ | 依映射表 |
| fontFamily | ✅ | 依映射表 |
| x | ✅ | 固定 80 |
| yOffset | ✅ | 單調遞增 |
| maxWidth | Text/CodeBlock | 960 |
| wordWrap | Text | true |
| backgroundColor | CodeBlock | `#1E1E1E` |

---

## 範例

### 輸入

```markdown
# Pixi 架構

這是一個資料驅動的渲染系統。

## 初始化

```js
const app = new PIXI.Application();
```
```

### 輸出

```json
{
  "nodes": [
    {
      "id": "n1",
      "nodeType": "Heading1",
      "text": "Pixi 架構",
      "fontSize": 48,
      "fontFamily": "MSDF_Bold",
      "x": 80,
      "yOffset": 0
    },
    {
      "id": "n2",
      "nodeType": "Text",
      "text": "這是一個資料驅動的渲染系統。",
      "fontSize": 16,
      "fontFamily": "MSDF_Regular",
      "x": 80,
      "yOffset": 80,
      "maxWidth": 960,
      "wordWrap": true
    },
    {
      "id": "n3",
      "nodeType": "Heading2",
      "text": "初始化",
      "fontSize": 32,
      "fontFamily": "MSDF_Regular",
      "x": 80,
      "yOffset": 120
    },
    {
      "id": "n4",
      "nodeType": "CodeBlock",
      "text": "const app = new PIXI.Application();",
      "fontSize": 14,
      "fontFamily": "MSDF_Mono",
      "x": 80,
      "yOffset": 180,
      "maxWidth": 960,
      "backgroundColor": "#1E1E1E"
    }
  ]
}
```

---

## 驗證規則

轉換完成後自動檢查：

- [ ] 輸出是合法 JSON
- [ ] nodes 陣列不為空（除非輸入為空）
- [ ] 扁平結構（無巢狀）
- [ ] 每個節點都有 yOffset
- [ ] fontFamily 符合映射表
- [ ] id 連續（n1, n2, n3...）
- [ ] yOffset 單調遞增

---

## 邊界處理

| 情境 | 處理 |
|------|------|
| 空 Markdown | `{"nodes": []}` |
| 純空白 | `{"nodes": []}` |
| 不認識的語法 | 當作 Text |
| HTML 標籤 | 忽略 |
| 圖片 `![]()` | 忽略 |
| 表格 | 忽略（未來擴展） |
| 行內格式（**粗體**） | 保留文字，忽略格式 |

---

## 評分標準

| 維度 | 權重 | 說明 |
|------|------|------|
| structure_accuracy | 40% | 節點類型映射正確 |
| layout_consistency | 20% | yOffset 計算正確 |
| typography_correctness | 20% | 字體/字號正確 |
| determinism | 20% | 同輸入同輸出 |

---

## 未來擴展

| 擴展 | 說明 |
|------|------|
| 行內格式 | `**bold**` → spans 子陣列 |
| 表格 | Table nodeType |
| 動畫 metadata | 進場動畫設定 |
| 互動事件 | 點擊/hover 回調 |
| 自適應 layout | viewport 動態計算 |
| 子 Skill 拆分 | md-parser → layout-engine → pixi-render-adapter |
