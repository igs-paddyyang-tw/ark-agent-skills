---
name: ark-etl-pipeline
description: |
  產出 etl_pipeline.py 資料轉換 Skill，將任何資料來源（CSV、JSON、API 回傳、
  Skill 輸出、資料庫查詢）轉換為 chart_generator 可直接使用的標準格式
  （x/y/labels 陣列）。支援欄位選取、篩選、排序、聚合、分組統計。
  適用於 Workflow 中串接資料來源與圖表產生。
  使用此 Skill 當使用者提及 ETL、資料轉換、資料清洗、data transform、
  資料管線、資料前處理、轉換格式、
  或任何需要將原始資料轉換為圖表標準格式的場景。
---

# ark-etl-pipeline

產出 `src/skills/internal/etl_pipeline.py`，將任何資料來源轉換為 `chart_generator` 可直接使用的標準格式，可獨立運作。

## 觸發條件

使用者提及以下關鍵字時觸發：
- 「ETL」、「資料轉換」、「資料清洗」
- 「data transform」、「資料管線」
- 「資料前處理」、「轉換格式」
- 「轉成圖表格式」

## 核心概念

```
任何資料來源 → etl_pipeline → 標準格式 → chart_generator → 圖表
```

標準輸出格式（對齊 chart_generator 輸入）：

```json
{
  "x": ["A", "B", "C"],
  "y": [10, 20, 15],
  "labels": ["系列A", "系列B", "系列C"],
  "title": "自動產生的標題",
  "chart_type": "bar"
}
```

## 輸入參數

| 參數 | 型別 | 必要 | 預設值 | 說明 |
|------|------|------|--------|------|
| `source` | `dict \| list` | ✅ | — | 原始資料（dict/list/Skill 輸出） |
| `x_field` | `str` | ❌ | — | X 軸欄位名稱 |
| `y_field` | `str` | ❌ | — | Y 軸欄位名稱 |
| `group_by` | `str` | ❌ | — | 分組欄位（聚合統計用） |
| `agg` | `str` | ❌ | `"count"` | 聚合方式：`count` / `sum` / `avg` / `min` / `max` |
| `sort_by` | `str` | ❌ | — | 排序欄位 |
| `sort_desc` | `bool` | ❌ | `False` | 是否降序 |
| `filter_expr` | `str` | ❌ | — | 篩選表達式（如 `"rtp > 95"`） |
| `limit` | `int` | ❌ | — | 限制筆數 |
| `chart_type` | `str` | ❌ | `"bar"` | 建議圖表類型 |
| `title` | `str` | ❌ | — | 圖表標題（自動產生如未指定） |

## 產出檔案

- `src/skills/internal/etl_pipeline.py`

---

## 產出指引

### 步驟 1：建立參數模型

```python
from src.skills.base import SkillParam

class EtlPipelineParams(SkillParam):
    """etl_pipeline 輸入參數。"""
    source: dict | list
    x_field: str | None = None
    y_field: str | None = None
    group_by: str | None = None
    agg: str = "count"           # count / sum / avg / min / max
    sort_by: str | None = None
    sort_desc: bool = False
    filter_expr: str | None = None
    limit: int | None = None
    chart_type: str = "bar"
    title: str | None = None
```

### 步驟 2：實作 Skill 類別

```python
class EtlPipelineSkill(BaseSkill):
    skill_id = "etl_pipeline"
    skill_type = SkillType.PYTHON
    description = "將任何資料來源轉換為 chart_generator 標準格式（x/y/labels）"
    version = "1.0.0"
    input_schema = EtlPipelineParams
```

### 步驟 3：實作 execute 方法

```python
async def execute(self, params: dict) -> SkillResult:
    try:
        p = EtlPipelineParams(**params)
        rows = self._normalize(p.source)
        rows = self._filter(rows, p.filter_expr)
        if p.group_by:
            x, y = self._aggregate(rows, p.group_by, p.y_field, p.agg)
        else:
            x = [r.get(p.x_field, i) for i, r in enumerate(rows)] if p.x_field else list(range(len(rows)))
            y = [r.get(p.y_field, 0) for r in rows] if p.y_field else []
        if p.sort_by:
            x, y = self._sort(x, y, p.sort_desc)
        if p.limit:
            x, y = x[:p.limit], y[:p.limit]
        title = p.title or self._auto_title(p)
        return SkillResult(success=True, data={
            "x": x, "y": y, "labels": x,
            "title": title, "chart_type": p.chart_type,
        })
    except Exception as e:
        return SkillResult(success=False, error=f"ETL 失敗: {e}")
```

### 步驟 4：實作資料處理方法

#### _normalize — 統一資料格式

```python
def _normalize(self, source: dict | list) -> list[dict]:
    """將各種資料來源統一為 list[dict]。"""
    if isinstance(source, list):
        if source and isinstance(source[0], dict):
            return source
        return [{"value": v} for v in source]
    if isinstance(source, dict):
        # Skill 輸出格式：{"games": [...], "count": N}
        for key in ("games", "items", "data", "results", "rows"):
            if key in source and isinstance(source[key], list):
                return source[key]
        # 單一 dict → 轉為 key-value list
        return [{"key": k, "value": v} for k, v in source.items()
                if isinstance(v, (int, float, str))]
    return []
```

#### _filter — 篩選

```python
def _filter(self, rows: list[dict], expr: str | None) -> list[dict]:
    """簡易篩選：支援 'field > value' 格式。"""
    if not expr:
        return rows
    # 解析 field op value
    import re
    m = re.match(r"(\w+)\s*(>=|<=|>|<|==|!=)\s*(.+)", expr.strip())
    if not m:
        return rows
    field, op, val = m.group(1), m.group(2), m.group(3).strip().strip("'\"")
    try:
        val = float(val)
    except ValueError:
        pass
    ops = {">": lambda a, b: a > b, "<": lambda a, b: a < b,
           ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b,
           "==": lambda a, b: a == b, "!=": lambda a, b: a != b}
    fn = ops.get(op, lambda a, b: True)
    return [r for r in rows if fn(r.get(field), val)]
```

#### _aggregate — 分組聚合

```python
def _aggregate(self, rows: list[dict], group_by: str, y_field: str | None, agg: str) -> tuple[list, list]:
    """分組聚合統計。"""
    from collections import defaultdict
    groups = defaultdict(list)
    for r in rows:
        key = r.get(group_by, "unknown")
        groups[key].append(r.get(y_field, 1) if y_field else 1)
    x, y = [], []
    for key, vals in groups.items():
        x.append(key)
        nums = [v for v in vals if isinstance(v, (int, float))]
        if agg == "count":
            y.append(len(vals))
        elif agg == "sum":
            y.append(sum(nums))
        elif agg == "avg":
            y.append(sum(nums) / len(nums) if nums else 0)
        elif agg == "min":
            y.append(min(nums) if nums else 0)
        elif agg == "max":
            y.append(max(nums) if nums else 0)
    return x, y
```

#### _sort — 排序

```python
def _sort(self, x: list, y: list, desc: bool) -> tuple[list, list]:
    paired = sorted(zip(x, y), key=lambda p: p[1], reverse=desc)
    return [p[0] for p in paired], [p[1] for p in paired]
```

#### _auto_title — 自動標題

```python
def _auto_title(self, p: EtlPipelineParams) -> str:
    parts = []
    if p.group_by:
        parts.append(f"依 {p.group_by} 分組")
    if p.y_field:
        parts.append(f"{p.agg}({p.y_field})")
    if p.filter_expr:
        parts.append(f"篩選: {p.filter_expr}")
    return " — ".join(parts) if parts else "Chart"
```

---

## 輸出格式

```json
{
  "success": true,
  "data": {
    "x": ["Pragmatic Play", "NetEnt", "Play'n Go"],
    "y": [5, 3, 2],
    "labels": ["Pragmatic Play", "NetEnt", "Play'n Go"],
    "title": "依 provider 分組 — count",
    "chart_type": "bar"
  }
}
```

直接傳給 `chart_generator`：

```yaml
# Workflow YAML 串接範例
- id: transform
  type: skill
  skill: etl_pipeline
  params:
    source: "{{ outputs.fetch }}"
    group_by: "provider"
    agg: "count"
    sort_desc: true
    limit: 10
    chart_type: "bar"
    title: "今日新遊戲 — 廠商分佈"
  output: chart_data

- id: draw
  type: skill
  skill: chart_generator
  params:
    chart_type: "{{ outputs.chart_data.chart_type }}"
    title: "{{ outputs.chart_data.title }}"
    x: "{{ outputs.chart_data.x }}"
    y: "{{ outputs.chart_data.y }}"
    labels: "{{ outputs.chart_data.labels }}"
    output_name: "provider_dist"
  output: chart
```

## 支援的資料來源

| 來源 | 格式 | 範例 |
|------|------|------|
| Skill 輸出 | `{"games": [...], "count": N}` | fetch_slot_game 的回傳 |
| JSON 陣列 | `[{"name": "A", "value": 10}, ...]` | API 回傳 |
| CSV 讀取結果 | `[{"col1": "A", "col2": 10}, ...]` | pandas to_dict("records") |
| 單一 dict | `{"A": 10, "B": 20}` | 統計結果 |
| 純數值陣列 | `[1, 2, 3, 4, 5]` | hist 用 |

## 注意事項

- `_normalize` 自動偵測資料格式，支援 Skill 輸出的常見 key（games/items/data/results/rows）
- `filter_expr` 僅支援簡易比較（`field > value`），複雜篩選建議在 Skill 內處理
- `agg` 聚合時非數值資料會被忽略
- 輸出的 `x`/`y`/`labels` 長度保證一致
- 無 `group_by` 時直接提取 `x_field`/`y_field` 欄位值

## 踩坑紀錄

### Skill 輸出格式處理（2026-04-17）

`source` 參數接收其他 Skill 的輸出時，格式通常是 `{"games": [...], "count": N, "source": "..."}`。
`_normalize` 必須能自動偵測並提取內部的 list。

支援的 key 名稱（依序嘗試）：`games`、`items`、`data`、`results`、`rows`

```python
if isinstance(source, dict):
    for key in ("games", "items", "data", "results", "rows"):
        if key in source and isinstance(source[key], list):
            return source[key]
```

如果 Skill 輸出的 key 不在上述清單中，需要手動在 Workflow YAML 中指定子欄位：
```yaml
source: "{{ outputs.my_skill.custom_key }}"
```
