---
author: paddyyang
name: ark-pdf-tool
description: |
  處理 PDF 檔案的所有操作。包括讀取或提取 PDF 中的文字/表格、
  合併或拆分 PDF、旋轉頁面、加浮水印、建立新 PDF、填寫 PDF 表單、
  加密/解密 PDF、提取圖片、以及對掃描 PDF 進行 OCR 使其可搜尋。
  當使用者提及 .pdf 檔案或要求產出 PDF 時，使用此 Skill。
---

# PDF 處理指南

## 概述

本指南涵蓋使用 Python 函式庫和命令列工具進行 PDF 處理的基本操作。
進階功能、JavaScript 函式庫和詳細範例請參閱 reference.md。
如需填寫 PDF 表單，請閱讀 forms.md 並遵循其指示。

## 快速開始

```python
from pypdf import PdfReader, PdfWriter

# 讀取 PDF
reader = PdfReader("document.pdf")
print(f"頁數: {len(reader.pages)}")

# 提取文字
text = ""
for page in reader.pages:
    text += page.extract_text()
```

## Python 函式庫

### pypdf — 基本操作

#### 合併 PDF
```python
from pypdf import PdfWriter, PdfReader

writer = PdfWriter()
for pdf_file in ["doc1.pdf", "doc2.pdf", "doc3.pdf"]:
    reader = PdfReader(pdf_file)
    for page in reader.pages:
        writer.add_page(page)

with open("merged.pdf", "wb") as output:
    writer.write(output)
```

#### 拆分 PDF
```python
reader = PdfReader("input.pdf")
for i, page in enumerate(reader.pages):
    writer = PdfWriter()
    writer.add_page(page)
    with open(f"page_{i+1}.pdf", "wb") as output:
        writer.write(output)
```

#### 提取中繼資料
```python
reader = PdfReader("document.pdf")
meta = reader.metadata
print(f"標題: {meta.title}")
print(f"作者: {meta.author}")
print(f"主題: {meta.subject}")
print(f"建立者: {meta.creator}")
```

#### 旋轉頁面
```python
reader = PdfReader("input.pdf")
writer = PdfWriter()
page = reader.pages[0]
page.rotate(90)  # 順時針旋轉 90 度
writer.add_page(page)
with open("rotated.pdf", "wb") as output:
    writer.write(output)
```

### pdfplumber — 文字與表格提取

#### 提取文字（含版面）
```python
import pdfplumber

with pdfplumber.open("document.pdf") as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        print(text)
```

#### 提取表格
```python
with pdfplumber.open("document.pdf") as pdf:
    for i, page in enumerate(pdf.pages):
        tables = page.extract_tables()
        for j, table in enumerate(tables):
            print(f"第 {i+1} 頁的表格 {j+1}:")
            for row in table:
                print(row)
```

#### 進階表格提取（轉 DataFrame）
```python
import pandas as pd

with pdfplumber.open("document.pdf") as pdf:
    all_tables = []
    for page in pdf.pages:
        tables = page.extract_tables()
        for table in tables:
            if table:
                df = pd.DataFrame(table[1:], columns=table[0])
                all_tables.append(df)

if all_tables:
    combined_df = pd.concat(all_tables, ignore_index=True)
    combined_df.to_excel("extracted_tables.xlsx", index=False)
```

### reportlab — 建立 PDF

#### 基本 PDF 建立
```python
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

c = canvas.Canvas("hello.pdf", pagesize=letter)
width, height = letter
c.drawString(100, height - 100, "Hello World!")
c.line(100, height - 140, 400, height - 140)
c.save()
```

#### 多頁 PDF
```python
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet

doc = SimpleDocTemplate("report.pdf", pagesize=letter)
styles = getSampleStyleSheet()
story = []
story.append(Paragraph("報告標題", styles['Title']))
story.append(Spacer(1, 12))
story.append(Paragraph("報告內容。" * 20, styles['Normal']))
story.append(PageBreak())
story.append(Paragraph("第 2 頁", styles['Heading1']))
doc.build(story)
```

#### 上標與下標

**重要**：絕對不要在 ReportLab PDF 中使用 Unicode 上標/下標字元（₀₁₂₃₄₅₆₇₈₉、⁰¹²³⁴⁵⁶⁷⁸⁹）。內建字型不包含這些字形，會渲染為黑色方塊。

改用 ReportLab 的 XML 標記：
```python
# 下標：使用 <sub> 標籤
chemical = Paragraph("H<sub>2</sub>O", styles['Normal'])
# 上標：使用 <super> 標籤
squared = Paragraph("x<super>2</super>", styles['Normal'])
```

## 命令列工具

### pdftotext（poppler-utils）
```bash
pdftotext input.pdf output.txt           # 提取文字
pdftotext -layout input.pdf output.txt   # 保留版面
pdftotext -f 1 -l 5 input.pdf output.txt # 提取第 1-5 頁
```

### qpdf
```bash
qpdf --empty --pages file1.pdf file2.pdf -- merged.pdf  # 合併
qpdf input.pdf --pages . 1-5 -- pages1-5.pdf            # 拆分
qpdf input.pdf output.pdf --rotate=+90:1                 # 旋轉
qpdf --password=mypassword --decrypt encrypted.pdf decrypted.pdf  # 解密
```

## 常見任務

### 掃描 PDF 的 OCR
```python
import pytesseract
from pdf2image import convert_from_path

images = convert_from_path('scanned.pdf')
text = ""
for i, image in enumerate(images):
    text += f"第 {i+1} 頁:\n"
    text += pytesseract.image_to_string(image)
    text += "\n\n"
```

### 加浮水印
```python
from pypdf import PdfReader, PdfWriter

watermark = PdfReader("watermark.pdf").pages[0]
reader = PdfReader("document.pdf")
writer = PdfWriter()
for page in reader.pages:
    page.merge_page(watermark)
    writer.add_page(page)
with open("watermarked.pdf", "wb") as output:
    writer.write(output)
```

### 提取圖片
```bash
pdfimages -j input.pdf output_prefix
# 提取所有圖片為 output_prefix-000.jpg、output_prefix-001.jpg 等
```

### 密碼保護
```python
from pypdf import PdfReader, PdfWriter

reader = PdfReader("input.pdf")
writer = PdfWriter()
for page in reader.pages:
    writer.add_page(page)
writer.encrypt("userpassword", "ownerpassword")
with open("encrypted.pdf", "wb") as output:
    writer.write(output)
```

## 快速參考

| 任務 | 最佳工具 | 指令/程式碼 |
|------|---------|------------|
| 合併 PDF | pypdf | `writer.add_page(page)` |
| 拆分 PDF | pypdf | 每頁一個檔案 |
| 提取文字 | pdfplumber | `page.extract_text()` |
| 提取表格 | pdfplumber | `page.extract_tables()` |
| 建立 PDF | reportlab | Canvas 或 Platypus |
| 命令列合併 | qpdf | `qpdf --empty --pages ...` |
| OCR 掃描 PDF | pytesseract | 先轉為圖片 |
| 填寫 PDF 表單 | pypdf（見 forms.md） | 見 forms.md |

## 延伸閱讀

- 進階 pypdfium2 用法，見 reference.md
- JavaScript 函式庫（pdf-lib），見 reference.md
- 填寫 PDF 表單，遵循 forms.md 的指示
