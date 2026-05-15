---
author: paddyyang
name: ark-docx-tool
description: "當使用者想要建立、讀取、編輯或操作 Word 文件（.docx 檔案）時使用此技能。觸發條件包括：任何提及 'Word doc'、'word document'、'.docx'，或要求產出具有目錄、標題、頁碼或信頭等格式的專業文件。也適用於從 .docx 檔案中擷取或重組內容、在文件中插入或替換圖片、在 Word 檔案中執行尋找與取代、處理追蹤修訂或註解，或將內容轉換為精美的 Word 文件。如果使用者要求以 Word 或 .docx 檔案形式產出「報告」、「備忘錄」、「信函」、「範本」或類似交付物，請使用此技能。不適用於 PDF、試算表、Google Docs 或與文件產生無關的一般程式設計任務。"
---

# DOCX 建立、編輯與分析

## 概述

.docx 檔案是一個包含 XML 檔案的 ZIP 壓縮檔。

## 快速參考

| 任務 | 方法 |
|------|------|
| 讀取/分析內容 | `pandoc` 或解壓取得原始 XML |
| 建立新文件 | 使用 `docx-js` — 參見下方「建立新文件」 |
| 編輯現有文件 | 解壓 → 編輯 XML → 重新打包 — 參見下方「編輯現有文件」 |

### 將 .doc 轉換為 .docx

舊版 `.doc` 檔案必須先轉換才能編輯：

```bash
python scripts/office/soffice.py --headless --convert-to docx document.doc
```

### 讀取內容

```bash
# 含追蹤修訂的文字擷取
pandoc --track-changes=all document.docx -o output.md

# 原始 XML 存取
python scripts/office/unpack.py document.docx unpacked/
```

### 轉換為圖片

```bash
python scripts/office/soffice.py --headless --convert-to pdf document.docx
pdftoppm -jpeg -r 150 document.pdf page
```

### 接受追蹤修訂

產出一份已接受所有追蹤修訂的乾淨文件（需要 LibreOffice）：

```bash
python scripts/accept_changes.py input.docx output.docx
```

---

## 建立新文件

使用 JavaScript 產生 .docx 檔案，然後驗證。安裝：`npm install -g docx`

### 設定
```javascript
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun,
        Header, Footer, AlignmentType, PageOrientation, LevelFormat, ExternalHyperlink,
        InternalHyperlink, Bookmark, FootnoteReferenceRun, PositionalTab,
        PositionalTabAlignment, PositionalTabRelativeTo, PositionalTabLeader,
        TabStopType, TabStopPosition, Column, SectionType,
        TableOfContents, HeadingLevel, BorderStyle, WidthType, ShadingType,
        VerticalAlign, PageNumber, PageBreak } = require('docx');

const doc = new Document({ sections: [{ children: [/* content */] }] });
Packer.toBuffer(doc).then(buffer => fs.writeFileSync("doc.docx", buffer));
```

### 驗證
建立檔案後進行驗證。如果驗證失敗，解壓、修正 XML，然後重新打包。
```bash
python scripts/office/validate.py doc.docx
```

### 頁面尺寸

```javascript
// 重要：docx-js 預設為 A4，不是 US Letter
// 務必明確設定頁面尺寸以確保一致的結果
sections: [{
  properties: {
    page: {
      size: {
        width: 12240,   // 8.5 inches in DXA
        height: 15840   // 11 inches in DXA
      },
      margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } // 1 inch margins
    }
  },
  children: [/* content */]
}]
```

**常見頁面尺寸（DXA 單位，1440 DXA = 1 英吋）：**

| 紙張 | 寬度 | 高度 | 內容寬度（1 英吋邊距） |
|------|------|------|----------------------|
| US Letter | 12,240 | 15,840 | 9,360 |
| A4（預設） | 11,906 | 16,838 | 9,026 |

**橫向方向：** docx-js 會在內部交換寬度/高度，因此傳入直向尺寸並讓它處理交換：
```javascript
size: {
  width: 12240,   // Pass SHORT edge as width
  height: 15840,  // Pass LONG edge as height
  orientation: PageOrientation.LANDSCAPE  // docx-js swaps them in the XML
},
// Content width = 15840 - left margin - right margin (uses the long edge)
```


### 樣式（覆寫內建標題）

使用 Arial 作為預設字型（通用支援）。標題保持黑色以確保可讀性。

```javascript
const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 24 } } }, // 12pt default
    paragraphStyles: [
      // IMPORTANT: Use exact IDs to override built-in styles
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 240, after: 240 }, outlineLevel: 0 } }, // outlineLevel required for TOC
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial" },
        paragraph: { spacing: { before: 180, after: 180 }, outlineLevel: 1 } },
    ]
  },
  sections: [{
    children: [
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("Title")] }),
    ]
  }]
});
```

### 清單（絕對不要使用 unicode 項目符號）

```javascript
// ❌ WRONG - never manually insert bullet characters
new Paragraph({ children: [new TextRun("• Item")] })  // BAD
new Paragraph({ children: [new TextRun("\u2022 Item")] })  // BAD

// ✅ CORRECT - use numbering config with LevelFormat.BULLET
const doc = new Document({
  numbering: {
    config: [
      { reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: "numbers",
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ]
  },
  sections: [{
    children: [
      new Paragraph({ numbering: { reference: "bullets", level: 0 },
        children: [new TextRun("Bullet item")] }),
      new Paragraph({ numbering: { reference: "numbers", level: 0 },
        children: [new TextRun("Numbered item")] }),
    ]
  }]
});

// ⚠️ Each reference creates INDEPENDENT numbering
// Same reference = continues (1,2,3 then 4,5,6)
// Different reference = restarts (1,2,3 then 1,2,3)
```

### 表格

**重要：表格需要雙重寬度設定** — 必須同時在表格上設定 `columnWidths` 以及在每個儲存格上設定 `width`。缺少任一設定，表格在某些平台上會渲染不正確。

```javascript
// CRITICAL: Always set table width for consistent rendering
// CRITICAL: Use ShadingType.CLEAR (not SOLID) to prevent black backgrounds
const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };

new Table({
  width: { size: 9360, type: WidthType.DXA }, // Always use DXA (percentages break in Google Docs)
  columnWidths: [4680, 4680], // Must sum to table width (DXA: 1440 = 1 inch)
  rows: [
    new TableRow({
      children: [
        new TableCell({
          borders,
          width: { size: 4680, type: WidthType.DXA }, // Also set on each cell
          shading: { fill: "D5E8F0", type: ShadingType.CLEAR }, // CLEAR not SOLID
          margins: { top: 80, bottom: 80, left: 120, right: 120 }, // Cell padding (internal, not added to width)
          children: [new Paragraph({ children: [new TextRun("Cell")] })]
        })
      ]
    })
  ]
})
```

**表格寬度計算：**

務必使用 `WidthType.DXA` — `WidthType.PERCENTAGE` 在 Google Docs 中會出問題。

```javascript
// Table width = sum of columnWidths = content width
// US Letter with 1" margins: 12240 - 2880 = 9360 DXA
width: { size: 9360, type: WidthType.DXA },
columnWidths: [7000, 2360]  // Must sum to table width
```

**寬度規則：**
- **務必使用 `WidthType.DXA`** — 絕不使用 `WidthType.PERCENTAGE`（與 Google Docs 不相容）
- 表格寬度必須等於 `columnWidths` 的總和
- 儲存格 `width` 必須與對應的 `columnWidth` 相符
- 儲存格 `margins` 是內部填充 — 會縮減內容區域，不會增加儲存格寬度
- 全寬表格：使用內容寬度（頁面寬度減去左右邊距）


### 圖片

```javascript
// CRITICAL: type parameter is REQUIRED
new Paragraph({
  children: [new ImageRun({
    type: "png", // Required: png, jpg, jpeg, gif, bmp, svg
    data: fs.readFileSync("image.png"),
    transformation: { width: 200, height: 150 },
    altText: { title: "Title", description: "Desc", name: "Name" } // All three required
  })]
})
```

### 分頁符號

```javascript
// CRITICAL: PageBreak must be inside a Paragraph
new Paragraph({ children: [new PageBreak()] })

// Or use pageBreakBefore
new Paragraph({ pageBreakBefore: true, children: [new TextRun("New page")] })
```

### 超連結

```javascript
// External link
new Paragraph({
  children: [new ExternalHyperlink({
    children: [new TextRun({ text: "Click here", style: "Hyperlink" })],
    link: "https://example.com",
  })]
})

// Internal link (bookmark + reference)
// 1. Create bookmark at destination
new Paragraph({ heading: HeadingLevel.HEADING_1, children: [
  new Bookmark({ id: "chapter1", children: [new TextRun("Chapter 1")] }),
]})
// 2. Link to it
new Paragraph({ children: [new InternalHyperlink({
  children: [new TextRun({ text: "See Chapter 1", style: "Hyperlink" })],
  anchor: "chapter1",
})]})
```

### 註腳

```javascript
const doc = new Document({
  footnotes: {
    1: { children: [new Paragraph("Source: Annual Report 2024")] },
    2: { children: [new Paragraph("See appendix for methodology")] },
  },
  sections: [{
    children: [new Paragraph({
      children: [
        new TextRun("Revenue grew 15%"),
        new FootnoteReferenceRun(1),
        new TextRun(" using adjusted metrics"),
        new FootnoteReferenceRun(2),
      ],
    })]
  }]
});
```

### 定位點

```javascript
// Right-align text on same line (e.g., date opposite a title)
new Paragraph({
  children: [
    new TextRun("Company Name"),
    new TextRun("\tJanuary 2025"),
  ],
  tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
})

// Dot leader (e.g., TOC-style)
new Paragraph({
  children: [
    new TextRun("Introduction"),
    new TextRun({ children: [
      new PositionalTab({
        alignment: PositionalTabAlignment.RIGHT,
        relativeTo: PositionalTabRelativeTo.MARGIN,
        leader: PositionalTabLeader.DOT,
      }),
      "3",
    ]}),
  ],
})
```

### 多欄版面配置

```javascript
// Equal-width columns
sections: [{
  properties: {
    column: {
      count: 2,          // number of columns
      space: 720,        // gap between columns in DXA (720 = 0.5 inch)
      equalWidth: true,
      separate: true,    // vertical line between columns
    },
  },
  children: [/* content flows naturally across columns */]
}]

// Custom-width columns (equalWidth must be false)
sections: [{
  properties: {
    column: {
      equalWidth: false,
      children: [
        new Column({ width: 5400, space: 720 }),
        new Column({ width: 3240 }),
      ],
    },
  },
  children: [/* content */]
}]
```

使用 `type: SectionType.NEXT_COLUMN` 的新區段來強制分欄。

### 目錄

```javascript
// CRITICAL: Headings must use HeadingLevel ONLY - no custom styles
new TableOfContents("Table of Contents", { hyperlink: true, headingStyleRange: "1-3" })
```

### 頁首/頁尾

```javascript
sections: [{
  properties: {
    page: { margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } // 1440 = 1 inch
  },
  headers: {
    default: new Header({ children: [new Paragraph({ children: [new TextRun("Header")] })] })
  },
  footers: {
    default: new Footer({ children: [new Paragraph({
      children: [new TextRun("Page "), new TextRun({ children: [PageNumber.CURRENT] })]
    })] })
  },
  children: [/* content */]
}]
```

### docx-js 關鍵規則

- **明確設定頁面尺寸** — docx-js 預設為 A4；美國文件使用 US Letter（12240 x 15840 DXA）
- **橫向：傳入直向尺寸** — docx-js 會在內部交換寬度/高度；將短邊作為 `width`、長邊作為 `height`，並設定 `orientation: PageOrientation.LANDSCAPE`
- **絕不使用 `\n`** — 使用獨立的 Paragraph 元素
- **絕不使用 unicode 項目符號** — 使用 `LevelFormat.BULLET` 搭配 numbering 設定
- **PageBreak 必須在 Paragraph 內** — 獨立使用會產生無效的 XML
- **ImageRun 需要 `type`** — 務必指定 png/jpg 等
- **務必使用 DXA 設定表格 `width`** — 絕不使用 `WidthType.PERCENTAGE`（在 Google Docs 中會出問題）
- **表格需要雙重寬度** — `columnWidths` 陣列與儲存格 `width`，兩者必須相符
- **表格寬度 = columnWidths 的總和** — 使用 DXA 時，確保加總完全正確
- **務必加入儲存格邊距** — 使用 `margins: { top: 80, bottom: 80, left: 120, right: 120 }` 以獲得可讀的填充
- **使用 `ShadingType.CLEAR`** — 表格底色絕不使用 SOLID
- **絕不使用表格作為分隔線** — 儲存格有最小高度，會渲染為空白方框（包括頁首/頁尾）；改用 Paragraph 上的 `border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "2E75B6", space: 1 } }`。雙欄頁尾請使用定位點（參見定位點章節），不要使用表格
- **目錄需要僅使用 HeadingLevel** — 標題段落不可使用自訂樣式
- **覆寫內建樣式** — 使用精確的 ID："Heading1"、"Heading2" 等
- **包含 `outlineLevel`** — 目錄所需（H1 為 0、H2 為 1，依此類推）

---

## 編輯現有文件

**請依序完成以下 3 個步驟。**

### 步驟 1：解壓
```bash
python scripts/office/unpack.py document.docx unpacked/
```
擷取 XML、美化列印、合併相鄰的 run，並將智慧引號轉換為 XML 實體（`&#x201C;` 等）以確保編輯後仍能保留。使用 `--merge-runs false` 可跳過 run 合併。

### 步驟 2：編輯 XML

編輯 `unpacked/word/` 中的檔案。模式請參見下方 XML 參考。

**追蹤修訂和註解請使用 "Claude" 作為作者**，除非使用者明確要求使用其他名稱。

**直接使用 Edit 工具進行字串替換。不要撰寫 Python 腳本。** 腳本會引入不必要的複雜性。Edit 工具能清楚顯示正在替換的內容。

**重要：新內容請使用智慧引號。** 新增含有撇號或引號的文字時，使用 XML 實體來產生智慧引號：
```xml
<!-- Use these entities for professional typography -->
<w:t>Here&#x2019;s a quote: &#x201C;Hello&#x201D;</w:t>
```
| 實體 | 字元 |
|------|------|
| `&#x2018;` | '（左單引號） |
| `&#x2019;` | '（右單引號 / 撇號） |
| `&#x201C;` | "（左雙引號） |
| `&#x201D;` | "（右雙引號） |

**新增註解：** 使用 `comment.py` 處理跨多個 XML 檔案的樣板（文字必須是預先轉義的 XML）：
```bash
python scripts/comment.py unpacked/ 0 "Comment text with &amp; and &#x2019;"
python scripts/comment.py unpacked/ 1 "Reply text" --parent 0  # reply to comment 0
python scripts/comment.py unpacked/ 0 "Text" --author "Custom Author"  # custom author name
```
然後在 document.xml 中加入標記（參見 XML 參考中的註解章節）。

### 步驟 3：打包
```bash
python scripts/office/pack.py unpacked/ output.docx --original document.docx
```
驗證並自動修復、壓縮 XML，然後建立 DOCX。使用 `--validate false` 可跳過驗證。

**自動修復會修正：**
- `durableId` >= 0x7FFFFFFF（重新產生有效 ID）
- 含空白的 `<w:t>` 缺少 `xml:space="preserve"`

**自動修復不會修正：**
- 格式錯誤的 XML、無效的元素巢狀、缺少的關聯、schema 違規

### 常見陷阱

- **替換整個 `<w:r>` 元素**：新增追蹤修訂時，將整個 `<w:r>...</w:r>` 區塊替換為 `<w:del>...<w:ins>...` 作為同層元素。不要在 run 內部注入追蹤修訂標籤。
- **保留 `<w:rPr>` 格式**：將原始 run 的 `<w:rPr>` 區塊複製到追蹤修訂的 run 中，以維持粗體、字型大小等格式。


---

## XML 參考

### Schema 合規性

- **`<w:pPr>` 中的元素順序**：`<w:pStyle>`、`<w:numPr>`、`<w:spacing>`、`<w:ind>`、`<w:jc>`、`<w:rPr>` 最後
- **空白**：含前導/尾隨空格的 `<w:t>` 需加上 `xml:space="preserve"`
- **RSIDs**：必須為 8 位十六進位（例如 `00AB1234`）

### 追蹤修訂

**插入：**
```xml
<w:ins w:id="1" w:author="Claude" w:date="2025-01-01T00:00:00Z">
  <w:r><w:t>inserted text</w:t></w:r>
</w:ins>
```

**刪除：**
```xml
<w:del w:id="2" w:author="Claude" w:date="2025-01-01T00:00:00Z">
  <w:r><w:delText>deleted text</w:delText></w:r>
</w:del>
```

**在 `<w:del>` 內部**：使用 `<w:delText>` 取代 `<w:t>`，使用 `<w:delInstrText>` 取代 `<w:instrText>`。

**最小化編輯** — 只標記變更的部分：
```xml
<!-- Change "30 days" to "60 days" -->
<w:r><w:t>The term is </w:t></w:r>
<w:del w:id="1" w:author="Claude" w:date="...">
  <w:r><w:delText>30</w:delText></w:r>
</w:del>
<w:ins w:id="2" w:author="Claude" w:date="...">
  <w:r><w:t>60</w:t></w:r>
</w:ins>
<w:r><w:t> days.</w:t></w:r>
```

**刪除整個段落/清單項目** — 當移除段落中的所有內容時，也要將段落標記標示為已刪除，使其與下一段落合併。在 `<w:pPr><w:rPr>` 中加入 `<w:del/>`：
```xml
<w:p>
  <w:pPr>
    <w:numPr>...</w:numPr>  <!-- list numbering if present -->
    <w:rPr>
      <w:del w:id="1" w:author="Claude" w:date="2025-01-01T00:00:00Z"/>
    </w:rPr>
  </w:pPr>
  <w:del w:id="2" w:author="Claude" w:date="2025-01-01T00:00:00Z">
    <w:r><w:delText>Entire paragraph content being deleted...</w:delText></w:r>
  </w:del>
</w:p>
```
若 `<w:pPr><w:rPr>` 中沒有 `<w:del/>`，接受修訂後會留下空白段落/清單項目。

**拒絕其他作者的插入** — 在其插入內部巢狀刪除：
```xml
<w:ins w:author="Jane" w:id="5">
  <w:del w:author="Claude" w:id="10">
    <w:r><w:delText>their inserted text</w:delText></w:r>
  </w:del>
</w:ins>
```

**還原其他作者的刪除** — 在其後新增插入（不要修改其刪除）：
```xml
<w:del w:author="Jane" w:id="5">
  <w:r><w:delText>deleted text</w:delText></w:r>
</w:del>
<w:ins w:author="Claude" w:id="10">
  <w:r><w:t>deleted text</w:t></w:r>
</w:ins>
```

### 註解

執行 `comment.py` 後（參見步驟 2），在 document.xml 中加入標記。回覆請使用 `--parent` 旗標，並將標記巢狀在父註解內。

**重要：`<w:commentRangeStart>` 和 `<w:commentRangeEnd>` 是 `<w:r>` 的同層元素，絕不在 `<w:r>` 內部。**

```xml
<!-- Comment markers are direct children of w:p, never inside w:r -->
<w:commentRangeStart w:id="0"/>
<w:del w:id="1" w:author="Claude" w:date="2025-01-01T00:00:00Z">
  <w:r><w:delText>deleted</w:delText></w:r>
</w:del>
<w:r><w:t> more text</w:t></w:r>
<w:commentRangeEnd w:id="0"/>
<w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr><w:commentReference w:id="0"/></w:r>

<!-- Comment 0 with reply 1 nested inside -->
<w:commentRangeStart w:id="0"/>
  <w:commentRangeStart w:id="1"/>
  <w:r><w:t>text</w:t></w:r>
  <w:commentRangeEnd w:id="1"/>
<w:commentRangeEnd w:id="0"/>
<w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr><w:commentReference w:id="0"/></w:r>
<w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr><w:commentReference w:id="1"/></w:r>
```

### 圖片

1. 將圖片檔案加入 `word/media/`
2. 在 `word/_rels/document.xml.rels` 中新增關聯：
```xml
<Relationship Id="rId5" Type=".../image" Target="media/image1.png"/>
```
3. 在 `[Content_Types].xml` 中新增內容類型：
```xml
<Default Extension="png" ContentType="image/png"/>
```
4. 在 document.xml 中引用：
```xml
<w:drawing>
  <wp:inline>
    <wp:extent cx="914400" cy="914400"/>  <!-- EMUs: 914400 = 1 inch -->
    <a:graphic>
      <a:graphicData uri=".../picture">
        <pic:pic>
          <pic:blipFill><a:blip r:embed="rId5"/></pic:blipFill>
        </pic:pic>
      </a:graphicData>
    </a:graphic>
  </wp:inline>
</w:drawing>
```

---

## 相依套件

- **pandoc**：文字擷取
- **docx**：`npm install -g docx`（建立新文件）
- **LibreOffice**：PDF 轉換（透過 `scripts/office/soffice.py` 自動設定沙箱環境）
- **Poppler**：`pdftoppm` 用於圖片轉換