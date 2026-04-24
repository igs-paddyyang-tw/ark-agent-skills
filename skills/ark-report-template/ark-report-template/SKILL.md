---
name: ark-report-template
description: |
  產出標準化報表模板引擎 Skill，使用 Jinja2 將資料 + 圖表組裝成完整報表。
  支援 Markdown、HTML、DOCX、PDF 輸出格式。
  內建常用模板（日報/週報/月報），支援自訂模板。
  使用此 Skill 當使用者提及報表模板、報告產生、report template、
  日報、週報、月報、或任何需要將資料組裝成格式化報表的場景。
---

# ark-report-template

產出 `src/skills/internal/report_template.py`，標準化報表模板引擎，可獨立運作。

## 觸發條件

- 「報表模板」、「報告產生」、「report template」
- 「日報」、「週報」、「月報」

## 輸入參數

| 參數 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `template_name` | `str` | ❌ | `"daily"` | 模板名稱：`daily` / `weekly` / `monthly` / 自訂路徑 |
| `data` | `dict` | ✅ | — | 報表資料 |
| `charts` | `list[str]` | ❌ | `[]` | 圖表路徑清單 |
| `output_format` | `str` | ❌ | `"md"` | 輸出格式：`md` / `html` |
| `output_name` | `str` | ❌ | `"report"` | 輸出檔名 |

## 產出指引

### Skill 類別

```python
class ReportTemplateSkill(BaseSkill):
    skill_id = "report_template"
    skill_type = SkillType.PYTHON
    description = "標準化報表模板引擎（Jinja2）"
    version = "1.0.0"
    input_schema = ReportTemplateParams
```

### 內建模板

- `daily`：日報（標題 + 摘要 + 資料表格 + 圖表 + 結論）
- `weekly`：週報（本週重點 + 數據比較 + 趨勢圖 + 下週計畫）
- `monthly`：月報（月度總結 + KPI 達成 + 圖表集 + 建議）

### 輸出

```json
{
  "report_path": "artifacts/reports/daily_2026-04-17.md",
  "format": "md",
  "template": "daily"
}
```

## Workflow 串接

```yaml
- id: report
  type: skill
  skill: report_template
  params:
    template_name: "daily"
    data: "{{ outputs.transform }}"
    charts: ["{{ outputs.chart.chart_path }}"]
    output_format: "md"
  output: report
```

## 注意事項

- 模板使用 Jinja2 語法
- 自訂模板放在 `templates/reports/` 目錄
- 圖表以 Markdown 圖片語法嵌入（`![](path)`）
- 搭配 `ark-docx-tool` 或 `ark-pdf-tool` 可轉換為 Word/PDF

## 踩坑紀錄

### 模板路徑計算（2026-04-17）

模板目錄路徑必須用 `Path(__file__).resolve()` 從 Skill 檔案位置往上計算，不能用相對路徑（因為 cwd 可能不同）。

```python
TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "templates" / "reports"
```

### 已驗證的模板

- `daily_report.md` — 每日市場報表（遊戲數量、廠商 Top 3、圖表附件）
- `quality_report.md` — 品質管線報告（測試結果、覆蓋率、審查分數、安全風險）
