---
name: ark-chart-generator
description: |
  產出 chart_generator.py 標準化圖表 Skill，使用 Matplotlib 將結構化數據轉換為圖表，
  輸出至 artifacts/charts 目錄。支援折線圖、長條圖、散點圖、圓餅圖、直方圖五種圖表類型。
  適用於報表生成、數據分析與 Workflow 自動化流程，可供 PDF 報表或 Dashboard 使用。
  使用此 Skill 當使用者提及圖表、chart、視覺化、折線圖、長條圖、圓餅圖、
  散點圖、直方圖、matplotlib、報表圖表、數據圖表、
  或任何需要將數據轉換為圖片的場景。
---

# ark-chart-generator

產出 `src/skills/internal/chart_generator.py`，將結構化數據轉換為標準化圖表（Matplotlib），可獨立運作。

## 觸發條件

使用者提及以下關鍵字時觸發：
- 「圖表」、「chart」、「視覺化」
- 「折線圖」、「長條圖」、「圓餅圖」、「散點圖」、「直方圖」
- 「matplotlib」、「報表圖表」、「數據圖表」
- 「產生圖表」、「畫圖」

## 使用情境

- 將數據轉換為圖表（趨勢圖 / 分佈圖 / 比較圖）
- 產生每日報表圖表
- Workflow 中進行視覺化輸出
- 提供 PDF 報表或 Dashboard 使用圖像

## 輸入參數

| 參數 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `chart_type` | `str` | ❌ | `"line"` | 圖表類型：`line` / `bar` / `scatter` / `pie` / `hist` |
| `title` | `str` | ❌ | `"Chart"` | 圖表標題 |
| `x` | `list` | ❌ | `[]` | X 軸資料（pie/hist 時可省略） |
| `y` | `list` | ❌ | `[]` | Y 軸資料（pie 時為各扇區數值） |
| `labels` | `list` | ❌ | `[]` | 資料標籤（pie 的扇區名稱、legend 標籤） |
| `x_label` | `str` | ❌ | `""` | X 軸標題 |
| `y_label` | `str` | ❌ | `""` | Y 軸標題 |
| `output_name` | `str` | ❌ | `"chart"` | 輸出檔名（不含副檔名） |

## 產出檔案

- `src/skills/internal/chart_generator.py`

---

## 產出指引

### 步驟 1：建立參數模型

```python
from src.skills.base import SkillParam

class ChartGeneratorParams(SkillParam):
    """chart_generator 輸入參數。"""
    chart_type: str = "line"       # line / bar / scatter / pie / hist
    title: str = "Chart"
    x: list = []
    y: list = []
    labels: list = []
    x_label: str = ""
    y_label: str = ""
    output_name: str = "chart"
```

### 步驟 2：實作 Skill 類別

```python
class ChartGeneratorSkill(BaseSkill):
    skill_id = "chart_generator"
    skill_type = SkillType.PYTHON
    description = "將結構化數據轉換為標準化圖表（line/bar/scatter/pie/hist）"
    version = "1.0.0"
    input_schema = ChartGeneratorParams
```

### 步驟 3：實作 execute 方法

```python
async def execute(self, params: dict) -> SkillResult:
    try:
        validated = ChartGeneratorParams(**params)
        chart_path = self._render(validated)
        return SkillResult(
            success=True,
            data={"chart_path": str(chart_path), "chart_type": validated.chart_type},
        )
    except Exception as e:
        return SkillResult(success=False, error=f"圖表產生失敗: {e}")
```

### 步驟 4：實作五種圖表渲染

使用 `matplotlib.use("Agg")` 支援無 GUI 環境。

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

CHARTS_DIR = Path("artifacts/charts")

def _render(self, p: ChartGeneratorParams) -> Path:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 6))

    if p.chart_type == "line":
        ax.plot(p.x, p.y, marker="o")
    elif p.chart_type == "bar":
        ax.bar(p.x, p.y)
    elif p.chart_type == "scatter":
        ax.scatter(p.x, p.y)
    elif p.chart_type == "pie":
        ax.pie(p.y, labels=p.labels or p.x, autopct="%1.1f%%", startangle=90)
        ax.axis("equal")
    elif p.chart_type == "hist":
        ax.hist(p.y, bins="auto", edgecolor="black")

    ax.set_title(p.title)
    if p.chart_type != "pie":
        if p.x_label:
            ax.set_xlabel(p.x_label)
        if p.y_label:
            ax.set_ylabel(p.y_label)
        ax.grid(True, alpha=0.3)

    path = CHARTS_DIR / f"{p.output_name}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path
```

### 步驟 5：驗證

```bash
python -c "
from src.skills.internal.chart_generator import ChartGeneratorSkill
import asyncio
skill = ChartGeneratorSkill()
result = asyncio.run(skill.execute({
    'chart_type': 'bar',
    'title': 'Test',
    'x': ['A', 'B', 'C'],
    'y': [10, 20, 15],
    'output_name': 'test_bar',
}))
print(result)
"
```

---

## 輸出格式

```json
{
  "success": true,
  "data": {
    "chart_path": "artifacts/charts/test_bar.png",
    "chart_type": "bar"
  }
}
```

## 五種圖表類型

| 類型 | 用途 | 必要參數 |
|------|------|---------|
| `line` | 趨勢分析、時間序列 | `x` + `y` |
| `bar` | 分類比較 | `x` + `y` |
| `scatter` | 相關性分析 | `x` + `y` |
| `pie` | 佔比分佈 | `y`（數值）+ `labels`（名稱） |
| `hist` | 頻率分佈 | `y`（數據集） |

## 整合到 Workflow

在 Workflow YAML 中使用：

```yaml
- id: draw_chart
  type: skill
  skill: chart_generator
  params:
    chart_type: "bar"
    title: "每日新遊戲數量"
    x: "{{ outputs.fetch.games | map(attribute='provider') | list }}"
    y: "{{ outputs.fetch.games | map(attribute='stars') | list }}"
    output_name: "daily_games"
  output: chart
```

## 注意事項

- 使用 `matplotlib.use("Agg")` 支援無 GUI 環境（Docker / CI）
- 圖表輸出至 `artifacts/charts/` 目錄，自動建立
- `dpi=150` 確保圖片清晰度
- `bbox_inches="tight"` 避免標題被裁切
- pie 圖自動加百分比標註
- hist 圖使用 `bins="auto"` 自動計算分組

## 踩坑紀錄

### matplotlib 中文字型（2026-04-17）

matplotlib 預設字型 DejaVu Sans 不支援 CJK 字元，中文標題會顯示為方塊。

解決方案：在 import 後設定中文字型：

```python
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
matplotlib.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "SimHei", "Arial"]
matplotlib.rcParams["axes.unicode_minus"] = False
```

- Windows：`Microsoft JhengHei`（微軟正黑體）
- Linux/Docker：需安裝 `fonts-noto-cjk` 或使用 `Noto Sans CJK TC`
- macOS：`PingFang TC`
