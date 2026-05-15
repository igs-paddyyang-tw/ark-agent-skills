---
author: paddyyang
name: ark-xlsx-tool
description: "當試算表檔案為主要輸入或輸出時，請使用此技能。這包括任何使用者想要：開啟、讀取、編輯或修復現有 .xlsx、.xlsm、.csv 或 .tsv 檔案的任務（例如新增欄位、計算公式、格式化、製作圖表、清理雜亂資料）；從零開始或從其他資料來源建立新的試算表；或在表格式檔案格式之間轉換。特別是當使用者以名稱或路徑提及試算表檔案時觸發——即使是隨意提及（例如「我下載資料夾裡的 xlsx」）——並且想要對其進行操作或從中產出結果。也適用於將雜亂的表格資料檔案（格式錯誤的列、錯位的標題、垃圾資料）清理或重組為正確的試算表。交付物必須是試算表檔案。當主要交付物是 Word 文件、HTML 報告、獨立 Python 腳本、資料庫管線或 Google Sheets API 整合時，即使涉及表格資料，也不要觸發。"
---

# 輸出要求

## 所有 Excel 檔案

### 專業字型
- 除非使用者另有指示，所有交付物使用一致的專業字型（例如 Arial、Times New Roman）

### 零公式錯誤
- 每個 Excel 模型交付時必須有零公式錯誤（#REF!、#DIV/0!、#VALUE!、#N/A、#NAME?）

### 保留現有範本（更新範本時）
- 修改檔案時，研究並精確匹配現有的格式、樣式和慣例
- 不要對已有既定模式的檔案強加標準化格式
- 現有範本慣例始終優先於這些指南

## 財務模型

### 色彩編碼標準
除非使用者或現有範本另有說明

#### 業界標準色彩慣例
- **藍色文字（RGB: 0,0,255）**：硬編碼輸入值，以及使用者會為情境分析而更改的數字
- **黑色文字（RGB: 0,0,0）**：所有公式和計算
- **綠色文字（RGB: 0,128,0）**：從同一工作簿中其他工作表拉取的連結
- **紅色文字（RGB: 255,0,0）**：連結到其他檔案的外部連結
- **黃色背景（RGB: 255,255,0）**：需要注意的關鍵假設或需要更新的儲存格

### 數字格式標準

#### 必要格式規則
- **年份**：格式化為文字字串（例如 "2024" 而非 "2,024"）
- **貨幣**：使用 $#,##0 格式；務必在標題中指定單位（"Revenue ($mm)"）
- **零值**：使用數字格式將所有零值顯示為 "-"，包括百分比（例如 "$#,##0;($#,##0);-"）
- **百分比**：預設使用 0.0% 格式（一位小數）
- **倍數**：估值倍數（EV/EBITDA、P/E）格式化為 0.0x
- **負數**：使用括號 (123) 而非負號 -123

### 公式建構規則

#### 假設值放置
- 將所有假設值（成長率、利潤率、倍數等）放在獨立的假設儲存格中
- 在公式中使用儲存格參照而非硬編碼值
- 範例：使用 =B5*(1+$B$6) 而非 =B5*1.05

#### 公式錯誤預防
- 驗證所有儲存格參照是否正確
- 檢查範圍中的偏移錯誤
- 確保所有預測期間的公式一致
- 使用邊界情況測試（零值、負數）
- 確認沒有非預期的循環參照

#### 硬編碼值的文件記錄要求
- 在儲存格中加入註解或在旁邊（如果是表格末端）。格式："Source: [系統/文件], [日期], [具體參照], [URL（如適用）]"
- 範例：
  - "Source: Company 10-K, FY2024, Page 45, Revenue Note, [SEC EDGAR URL]"
  - "Source: Company 10-Q, Q2 2025, Exhibit 99.1, [SEC EDGAR URL]"
  - "Source: Bloomberg Terminal, 8/15/2025, AAPL US Equity"
  - "Source: FactSet, 8/20/2025, Consensus Estimates Screen"

# XLSX 建立、編輯與分析

## 概述

使用者可能會要求你建立、編輯或分析 .xlsx 檔案的內容。你有不同的工具和工作流程可用於不同的任務。

## 重要要求

**公式重新計算需要 LibreOffice**：你可以假設已安裝 LibreOffice，使用 `scripts/recalc.py` 腳本重新計算公式值。該腳本在首次執行時會自動設定 LibreOffice，包括在 Unix socket 受限的沙箱環境中（由 `scripts/office/soffice.py` 處理）。

## 讀取與分析資料

### 使用 pandas 進行資料分析
對於資料分析、視覺化和基本操作，使用 **pandas**，它提供強大的資料操作能力：

```python
import pandas as pd

# Read Excel
df = pd.read_excel('file.xlsx')  # Default: first sheet
all_sheets = pd.read_excel('file.xlsx', sheet_name=None)  # All sheets as dict

# Analyze
df.head()      # Preview data
df.info()      # Column info
df.describe()  # Statistics

# Write Excel
df.to_excel('output.xlsx', index=False)
```

## Excel 檔案工作流程

## 關鍵：使用公式，而非硬編碼值

**務必使用 Excel 公式，而非在 Python 中計算值後硬編碼。** 這確保試算表保持動態且可更新。

### ❌ 錯誤做法 - 硬編碼計算值
```python
# Bad: Calculating in Python and hardcoding result
total = df['Sales'].sum()
sheet['B10'] = total  # Hardcodes 5000

# Bad: Computing growth rate in Python
growth = (df.iloc[-1]['Revenue'] - df.iloc[0]['Revenue']) / df.iloc[0]['Revenue']
sheet['C5'] = growth  # Hardcodes 0.15

# Bad: Python calculation for average
avg = sum(values) / len(values)
sheet['D20'] = avg  # Hardcodes 42.5
```

### ✅ 正確做法 - 使用 Excel 公式
```python
# Good: Let Excel calculate the sum
sheet['B10'] = '=SUM(B2:B9)'

# Good: Growth rate as Excel formula
sheet['C5'] = '=(C4-C2)/C2'

# Good: Average using Excel function
sheet['D20'] = '=AVERAGE(D2:D19)'
```

這適用於所有計算——總計、百分比、比率、差異等。試算表應該能在來源資料變更時重新計算。

## 常見工作流程
1. **選擇工具**：pandas 用於資料處理，openpyxl 用於公式/格式化
2. **建立/載入**：建立新工作簿或載入現有檔案
3. **修改**：新增/編輯資料、公式和格式
4. **儲存**：寫入檔案
5. **重新計算公式（使用公式時為必要步驟）**：使用 scripts/recalc.py 腳本
   ```bash
   python scripts/recalc.py output.xlsx
   ```
6. **驗證並修正任何錯誤**：
   - 腳本會回傳包含錯誤詳情的 JSON
   - 如果 `status` 為 `errors_found`，檢查 `error_summary` 以取得具體的錯誤類型和位置
   - 修正已識別的錯誤並再次重新計算
   - 常見需修正的錯誤：
     - `#REF!`：無效的儲存格參照
     - `#DIV/0!`：除以零
     - `#VALUE!`：公式中的資料類型錯誤
     - `#NAME?`：無法識別的公式名稱

### 建立新的 Excel 檔案

```python
# Using openpyxl for formulas and formatting
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

wb = Workbook()
sheet = wb.active

# Add data
sheet['A1'] = 'Hello'
sheet['B1'] = 'World'
sheet.append(['Row', 'of', 'data'])

# Add formula
sheet['B2'] = '=SUM(A1:A10)'

# Formatting
sheet['A1'].font = Font(bold=True, color='FF0000')
sheet['A1'].fill = PatternFill('solid', start_color='FFFF00')
sheet['A1'].alignment = Alignment(horizontal='center')

# Column width
sheet.column_dimensions['A'].width = 20

wb.save('output.xlsx')
```

### 編輯現有 Excel 檔案

```python
# Using openpyxl to preserve formulas and formatting
from openpyxl import load_workbook

# Load existing file
wb = load_workbook('existing.xlsx')
sheet = wb.active  # or wb['SheetName'] for specific sheet

# Working with multiple sheets
for sheet_name in wb.sheetnames:
    sheet = wb[sheet_name]
    print(f"Sheet: {sheet_name}")

# Modify cells
sheet['A1'] = 'New Value'
sheet.insert_rows(2)  # Insert row at position 2
sheet.delete_cols(3)  # Delete column 3

# Add new sheet
new_sheet = wb.create_sheet('NewSheet')
new_sheet['A1'] = 'Data'

wb.save('modified.xlsx')
```

## 重新計算公式

由 openpyxl 建立或修改的 Excel 檔案包含公式字串但不包含計算值。使用提供的 `scripts/recalc.py` 腳本來重新計算公式：

```bash
python scripts/recalc.py <excel_file> [timeout_seconds]
```

範例：
```bash
python scripts/recalc.py output.xlsx 30
```

該腳本：
- 首次執行時自動設定 LibreOffice 巨集
- 重新計算所有工作表中的所有公式
- 掃描所有儲存格以檢查 Excel 錯誤（#REF!、#DIV/0! 等）
- 回傳包含詳細錯誤位置和計數的 JSON
- 在 Linux 和 macOS 上皆可運作

## 公式驗證檢查清單

確保公式正確運作的快速檢查：

### 基本驗證
- [ ] **測試 2-3 個範例參照**：在建構完整模型之前，驗證它們是否拉取正確的值
- [ ] **欄位對應**：確認 Excel 欄位匹配（例如第 64 欄 = BL，而非 BK）
- [ ] **列偏移**：記住 Excel 列從 1 開始索引（DataFrame 第 5 列 = Excel 第 6 列）

### 常見陷阱
- [ ] **NaN 處理**：使用 `pd.notna()` 檢查空值
- [ ] **最右側欄位**：FY 資料通常在第 50+ 欄
- [ ] **多重匹配**：搜尋所有出現位置，而非僅第一個
- [ ] **除以零**：在公式中使用 `/` 之前檢查分母（#DIV/0!）
- [ ] **錯誤參照**：驗證所有儲存格參照指向預期的儲存格（#REF!）
- [ ] **跨工作表參照**：使用正確格式（Sheet1!A1）連結工作表

### 公式測試策略
- [ ] **從小處開始**：在廣泛套用之前，先在 2-3 個儲存格上測試公式
- [ ] **驗證依賴關係**：檢查公式中參照的所有儲存格是否存在
- [ ] **測試邊界情況**：包含零值、負值和極大值

### 解讀 scripts/recalc.py 輸出
腳本回傳包含錯誤詳情的 JSON：
```json
{
  "status": "success",           // or "errors_found"
  "total_errors": 0,              // Total error count
  "total_formulas": 42,           // Number of formulas in file
  "error_summary": {              // Only present if errors found
    "#REF!": {
      "count": 2,
      "locations": ["Sheet1!B5", "Sheet1!C10"]
    }
  }
}
```

## 最佳實踐

### 函式庫選擇
- **pandas**：最適合資料分析、批量操作和簡單資料匯出
- **openpyxl**：最適合複雜格式化、公式和 Excel 特定功能

### 使用 openpyxl 的注意事項
- 儲存格索引從 1 開始（row=1, column=1 指向儲存格 A1）
- 使用 `data_only=True` 讀取計算值：`load_workbook('file.xlsx', data_only=True)`
- **警告**：如果以 `data_only=True` 開啟並儲存，公式會被替換為值且永久遺失
- 對於大型檔案：讀取時使用 `read_only=True`，寫入時使用 `write_only=True`
- 公式會被保留但不會被計算——使用 scripts/recalc.py 更新值

### 使用 pandas 的注意事項
- 指定資料類型以避免推斷問題：`pd.read_excel('file.xlsx', dtype={'id': str})`
- 對於大型檔案，讀取特定欄位：`pd.read_excel('file.xlsx', usecols=['A', 'C', 'E'])`
- 正確處理日期：`pd.read_excel('file.xlsx', parse_dates=['date_column'])`

## 程式碼風格指南
**重要**：產生 Excel 操作的 Python 程式碼時：
- 撰寫精簡的 Python 程式碼，不加不必要的註解
- 避免冗長的變數名稱和多餘的操作
- 避免不必要的 print 語句

**對於 Excel 檔案本身**：
- 為包含複雜公式或重要假設的儲存格加入註解
- 記錄硬編碼值的資料來源
- 為關鍵計算和模型區段加入說明
