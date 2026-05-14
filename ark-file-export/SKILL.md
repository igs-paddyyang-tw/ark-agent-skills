---
name: ark-file-export
description: |
  產出檔案匯出 Skill，將記憶體中的資料（dict/list/str）輸出為 Markdown、CSV、JSON 檔案。
  用於 Workflow 最後一步存檔、資料備份匯出、正規化內容後匯入 Wiki 或報表。
  使用此 Skill 當使用者提及匯出檔案、存成 CSV、輸出 JSON、產生 Markdown 檔、
  資料備份、file export、或任何需要將處理結果寫入磁碟檔案的場景。
  不適用於 PDF/Word/Excel/PPT 等複雜格式（請使用對應的 ark-*-tool）。
---

# ark-file-export

產出 `src/skills/python_skills/file_export.py`，將資料匯出為 MD/CSV/JSON 檔案，可獨立運作。

## 觸發條件

- 「匯出檔案」、「存成 CSV」、「輸出 JSON」
- 「產生 Markdown 檔」、「資料備份」、「file export」
- 「把結果存下來」、「匯出報表」

## 與其他 Skill 的區別

| Skill | 職責 | 輸出 |
|-------|------|------|
| ark-etl-pipeline | 資料轉換（清洗/聚合/篩選） | 記憶體中的 dict/list |
| ark-file-export | 將資料寫入磁碟檔案 | .md / .csv / .json 檔案 |
| ark-report-template | Jinja2 模板組裝完整報表 | 格式化報表檔案 |
| ark-docx-tool / ark-pdf-tool | 複雜格式文件 | .docx / .pdf |

## 使用情境

| 情境 | Workflow 流程 | file_export 角色 |
|------|-------------|-----------------|
| 報表產出 | ETL → chart → report_template → **file_export** | 最後一步：存成 MD/HTML |
| 企劃文件 | GDD 內容 → **file_export**（MD）→ wiki_ingest | 中間步驟：正規化後匯入 Wiki |
| 資料備份 | db_query → **file_export**（CSV/JSON） | 獨立使用：查詢結果匯出 |
| 圖表附件 | chart_generator → **file_export**（JSON metadata） | 輔助：圖表元資料存檔 |

## 產出檔案

- `src/skills/python_skills/file_export.py`

## 產出指引

### 步驟 1：參數模型

```python
from pydantic import Field
from src.skills.base import SkillParam

class FileExportInput(SkillParam):
    """File Export 輸入參數。"""
    format: str = Field(description="輸出格式：markdown / csv / json")
    content: str | list | dict = Field(description="要匯出的內容")
    output_path: str = Field(default="", description="輸出路徑（空則回傳內容不存檔）")
    filename: str = Field(default="export", description="檔名（不含副檔名）")
```

### 步驟 2：Skill 類別

```python
class FileExportSkill(BaseSkill):
    skill_id = "file_export"
    skill_type = SkillType.PYTHON
    description = "將資料匯出為 Markdown / CSV / JSON 檔案"
    input_schema = FileExportInput
```

### 步驟 3：三種格式轉換

```python
async def execute(self, params: dict) -> SkillResult:
    fmt = params["format"]
    content = params["content"]

    if fmt == "markdown":
        text = _to_markdown(content)
    elif fmt == "csv":
        text = _to_csv(content)
    elif fmt == "json":
        text = json.dumps(content, ensure_ascii=False, indent=2)
    else:
        return SkillResult(success=False, error=f"不支援的格式: {fmt}")

    # 存檔（如有指定路徑）
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(text, encoding="utf-8")

    return SkillResult(success=True, data={"text": text, "format": fmt, "path": output_path})
```

### 步驟 4：Markdown 轉換規則

```python
def _to_markdown(content) -> str:
    """dict → 表格，list[dict] → 表格，str → 原樣。"""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        lines = [f"| 欄位 | 值 |", f"|------|---|"]
        lines += [f"| {k} | {v} |" for k, v in content.items()]
        return "\n".join(lines)
    if isinstance(content, list) and content and isinstance(content[0], dict):
        headers = list(content[0].keys())
        lines = [f"| {' | '.join(headers)} |", f"| {' | '.join(['---'] * len(headers))} |"]
        lines += [f"| {' | '.join(str(row.get(h, '')) for h in headers)} |" for row in content]
        return "\n".join(lines)
    return str(content)
```

### 步驟 5：CSV 轉換規則

```python
def _to_csv(content) -> str:
    """list[dict] → CSV 字串。"""
    if isinstance(content, list) and content and isinstance(content[0], dict):
        import csv, io
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=content[0].keys())
        writer.writeheader()
        writer.writerows(content)
        return buf.getvalue()
    return str(content)
```

## Workflow 串接範例

```yaml
# 報表產出最後一步
- id: save_report
  type: skill
  skill: file_export
  params:
    format: "markdown"
    content: "{{ outputs.report.rendered }}"
    output_path: "artifacts/reports/daily_{{ today }}.md"
  output: saved

# 資料備份
- id: backup_data
  type: skill
  skill: file_export
  params:
    format: "csv"
    content: "{{ outputs.query.rows }}"
    output_path: "artifacts/backup/data_{{ today }}.csv"
  output: backup
```

## 注意事項

- 輸出路徑使用 `pathlib.Path`，自動建立父目錄
- CSV 格式僅支援 `list[dict]` 輸入
- Markdown 表格自動從 dict/list[dict] 轉換
- 不指定 output_path 時只回傳文字內容（不存檔）
- 複雜格式（PDF/Word/Excel）請使用對應的 ark-*-tool
