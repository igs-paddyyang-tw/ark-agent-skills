---
name: ark-html-dashboard
description: |
  產出 Self-contained 互動式 HTML 數據儀錶板，使用 Chart.js 圖表、
  KPI 卡片、篩選器、排序表格，所有資料內嵌於單一 HTML 檔案。
  零伺服器依賴，可直接用瀏覽器開啟或嵌入 Web UI。
  支援暗黑科技風格與亮色主題。
  使用此 Skill 當使用者提及 dashboard、儀錶板、互動圖表、
  HTML 報表、數據面板、Chart.js、KPI 卡片、
  或任何需要產出可分享的互動式數據視覺化頁面的場景。
  不適用於靜態 PNG 圖表（請使用 ark-chart-generator）。
metadata:
  category: view
  outputs:
    - format: html
      audience: human
  depends_on: [ark-html-report]
  author: paddyyang
---

# ark-html-dashboard

產出 Self-contained 互動式 HTML 數據儀錶板，單一檔案零伺服器依賴。

## 觸發條件

- 「dashboard」、「儀錶板」、「互動圖表」
- 「HTML 報表」、「數據面板」、「KPI 卡片」
- 「Chart.js」、「互動式視覺化」

## 與其他 Skill 的區別

| Skill | 技術 | 輸出 | 用途 |
|-------|------|------|------|
| ark-html-dashboard | Chart.js（Canvas HTML） | 互動式 HTML | Web 嵌入、分享、Dashboard |
| ark-chart-generator | Matplotlib（Python） | 靜態 PNG | 報表附件、PDF、Telegram |
| ark-frontend-design | React/Tailwind | 完整前端應用 | 複雜 SPA |

## 產出檔案

```
artifacts/dashboards/{name}.html    # 單一 HTML 儀錶板
```

或整合到既有專案：

```
src/skills/python_skills/html_chart.py    # Runtime Skill
```

---

## 產出指引

### 步驟 1：參數模型

```python
from pydantic import Field
from src.skills.base import SkillParam

class HtmlDashboardInput(SkillParam):
    """HTML Dashboard 輸入參數。"""
    title: str = Field(default="Dashboard", description="儀錶板標題")
    theme: str = Field(default="auto", description="主題：auto / dark / light（auto 依內容自動判斷）")
    kpis: list[dict] = Field(default_factory=list, description="KPI 卡片資料")
    charts: list[dict] = Field(default_factory=list, description="圖表設定")
    table_data: list[dict] = Field(default_factory=list, description="表格資料")
    table_columns: list[dict] = Field(default_factory=list, description="表格欄位定義")
    filters: list[dict] = Field(default_factory=list, description="篩選器設定")
    output_path: str = Field(default="", description="輸出路徑")
```

### 步驟 2：Skill 類別

```python
class HtmlDashboardSkill(BaseSkill):
    skill_id = "html_dashboard"
    skill_type = SkillType.PYTHON
    description = "產生 Self-contained 互動式 HTML 數據儀錶板"
    input_schema = HtmlDashboardInput
```

### 步驟 3：HTML 結構

儀錶板由四個區塊組成：

```
┌─────────────────────────────────────┐
│ Header（標題 + 篩選器）              │
├──────┬──────┬──────┬───────────────┤
│ KPI  │ KPI  │ KPI  │ KPI           │
├──────┴──────┴──────┴───────────────┤
│ Chart（折線/柱狀/圓餅/雷達）         │
├─────────────────────────────────────┤
│ Table（排序 + 分頁）                 │
└─────────────────────────────────────┘
```

### 步驟 4：Chart.js 整合

使用 CDN 載入，支援六種圖表：

| 類型 | Chart.js type | 用途 |
|------|--------------|------|
| 折線圖 | line | 趨勢、時間序列 |
| 柱狀圖 | bar | 分類比較 |
| 圓餅圖 | doughnut | 佔比分佈 |
| 雷達圖 | radar | 多維度比較 |
| 散點圖 | scatter | 相關性分析 |
| 水平柱狀 | bar (horizontal) | 排名（>8 項自動切換） |

```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.5.1"></script>
```

### 步驟 5：KPI 卡片

```html
<div class="kpi-card">
  <div class="kpi-label">指標名稱</div>
  <div class="kpi-value">$1.2M</div>
  <div class="kpi-change positive">+12.5% vs 上期</div>
</div>
```

KPI 資料格式：
```json
{
  "label": "總營收",
  "value": 1200000,
  "previous": 1066667,
  "format": "currency"
}
```

支援格式化：`currency`（$1.2M）、`percent`（95.0%）、`number`（12.5K）

### 步驟 6：篩選器

```html
<select id="filter-region" onchange="dashboard.applyFilters()">
  <option value="all">全部</option>
</select>
```

篩選器設定格式：
```json
{
  "id": "filter-region",
  "label": "區域",
  "field": "region",
  "type": "select"
}
```

篩選觸發時自動更新 KPI + 圖表 + 表格。

### 步驟 7：排序表格

- 點擊表頭排序（▲▼ 切換）
- 超過 100 筆自動分頁
- 數值欄位自動格式化

### 步驟 8：暗黑科技風格（預設）

```css
:root {
  --bg-primary: #020617;
  --bg-card: rgba(15,23,42,0.9);
  --text-primary: #e2e8f0;
  --text-secondary: #94a3b8;
  --accent: #22d3ee;
  --positive: #22c55e;
  --negative: #f87171;
}
```

亮色主題切換：`theme: "light"`

Auto 模式（預設）：依內容自動選擇風格：

| 內容類型 | 自動選擇 | 原因 |
|---------|---------|------|
| 技術監控 / DevOps / 伺服器 | dark | 減少視覺疲勞、數據對比度高 |
| 業務報告 / KPI / 營收 | light | 正式場合、列印友好 |
| 遊戲數據 / 玩家分析 | dark | 符合遊戲開發者習慣 |
| 行銷 / 公開簡報 | light | 受眾友好、品牌一致 |

判斷邏輯：掃描 title + KPI labels 中的關鍵字，命中 dark 類（monitoring/server/cpu/error/deploy/game/slot）→ dark，否則 → light。

```css
:root {
  --bg-primary: #f8f9fa;
  --bg-card: #ffffff;
  --text-primary: #212529;
  --text-secondary: #6c757d;
  --accent: #0891b2;
}
```

---

## 風格 Token

本 skill 的 HTML 輸出使用 ark-html-report 的共享 token 系統。
詳見：ark-html-report/references/styles.md
支援 5 種風格：boardroom / terminal / midnight / editorial / paperprint

---

## 效能指引

| 資料量 | 策略 |
|--------|------|
| < 1,000 筆 | 直接內嵌，完整互動 |
| 1,000 - 10,000 筆 | 預聚合後內嵌 |
| > 10,000 筆 | 不適合 client-side，改用 API + 分頁 |

- 折線圖限制 < 500 點/系列
- 柱狀圖限制 < 50 類別
- 散點圖限制 < 1,000 點
- 篩選更新使用 `chart.update('none')` 停用動畫

---

## Workflow 串接

```yaml
- id: dashboard
  type: skill
  skill: html_dashboard
  params:
    title: "每日市場報表"
    theme: "dark"
    kpis:
      - label: "新遊戲數"
        value: "{{ outputs.transform.count }}"
        format: "number"
    charts:
      - type: "bar"
        title: "廠商分佈"
        labels: "{{ outputs.transform.providers }}"
        data: "{{ outputs.transform.counts }}"
    table_data: "{{ outputs.transform.rows }}"
    output_path: "artifacts/dashboards/daily.html"
  output: dashboard
```

## 注意事項

- 所有資料內嵌於 HTML（`const DATA = [...]`），零 API 依賴
- Chart.js 從 CDN 載入（需網路），離線可改為 inline
- 中文字型使用系統字型（-apple-system, "Microsoft JhengHei"）
- 列印模式自動隱藏篩選器、移除陰影
- RWD 支援：手機版 KPI 2 欄、圖表單欄
