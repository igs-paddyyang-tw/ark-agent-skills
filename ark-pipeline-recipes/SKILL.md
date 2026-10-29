---
name: ark-pipeline-recipes
description: |
  資料管線與 LLM 工具的產碼食譜集：照食譜在專案裡寫出標準模組（圖表、ETL 轉換與匯出、
  KPI 計算、異常偵測與告警、LLM 成本追蹤、翻譯、LLM 摘要／分析／意圖解析、管線資料契約）。
  使用此 Skill 當使用者提及圖表、chart、matplotlib、ETL、資料轉換、資料清洗、匯出 CSV／JSON、
  KPI 計算、DAU、ARPU、RTP、留存率、LTV、異常偵測、告警規則、指標異常、
  成本追蹤、token 使用量、API 費用、翻譯、translate、i18n、
  LLM 摘要、意圖解析、智能問答、資料契約、schema 驗證，
  或任何需要「寫一個資料處理／LLM 工具模組進專案」的場景。
  不適用於：可互動的儀錶板請用 ark-html-dashboard；從資料庫取數請用 ark-db-query；
  呼叫 LLM CLI 後端或派 sub-agent 請用 ark-agent-cli；留存的深入分析請用 ark-retention-analysis。
metadata:
  version: "1.0.0"
  schema_version: "1.2"
  status: active
  updated: 2026-10-29
  category: pipeline
  form: instruction
  domain: general
  replaces: [ark-anomaly-detector, ark-chart-generator, ark-cost-tracker, ark-etl-pipeline, ark-kpi-calculator, ark-llm-tools, ark-translator, ark-data-contract]
  outputs:
    - format: md
      audience: ai
  author: paddyyang
---

# ark-pipeline-recipes

8 份「照著寫進專案」的產碼食譜。本檔只做路由：**先在下表找到情境，再只讀那一頁**，不必全部載入。

## 你要做什麼 → 讀哪一頁

| 情境 | 讀這頁 | 產出 |
|---|---|---|
| 把數據畫成靜態圖（折線／長條／散點／圓餅／直方） | [`references/chart-generator.md`](references/chart-generator.md) | `chart_generator.py` → `artifacts/charts/*.png` |
| 把原始資料轉成圖表格式、篩選聚合、匯出 CSV／JSON／MD | [`references/etl-pipeline.md`](references/etl-pipeline.md) | `etl_pipeline.py` |
| 定義上下游元件的 schema 契約並驗證 | [`references/data-contract.md`](references/data-contract.md) | 契約定義＋驗證步驟 |
| 計算 DAU／MAU／ARPU／RTP／留存／LTV／轉換率 | [`references/kpi-calculator.md`](references/kpi-calculator.md) | KPI 模組＋MCP Tool＋pytest |
| 偵測指標異常（Z-score／IQR／移動平均）並告警 | [`references/anomaly-detector.md`](references/anomaly-detector.md) | detector＋alert_rules.yaml＋notifier |
| 記錄 LLM API 的 token 用量與費用 | [`references/cost-tracker.md`](references/cost-tracker.md) | 成本追蹤模組 |
| 繁簡英日互譯，保留 Markdown 與程式碼區塊 | [`references/translator.md`](references/translator.md) | `translator.py` |
| LLM 摘要、分析、問答、意圖解析（provider 抽象） | [`references/llm-tools.md`](references/llm-tools.md) | llm_summarize／analyze／qa／parse_intent |

常見串法：取數（`ark-db-query`）→ `etl-pipeline` → `kpi-calculator` → `anomaly-detector` → `chart-generator`，
元件之間的格式用 `data-contract` 約定。

> 各頁內文保留併入前的寫法，提到的舊 skill 名（`ark-chart-generator`、`ark-kpi-calculator`…）
> 都等於本 skill 的對應頁。

## 共同約定

- **產出落點**：程式碼寫進專案的模組目錄（bot 型是根 `skills/` 插件、其他專案依各自結構），
  圖檔與匯出檔寫 `artifacts/` 或 `output/`，不寫進 skill 目錄
- **必附測試**：每個產出的模組至少一個 pytest，跑過才算完成
- docstring 用繁體中文；路徑用 `pathlib.Path`；金鑰從環境變數讀，不寫死
- 食譜寫出的程式碼屬專案的**腳本層**（綁本專案）。同一份程式碼被第二個專案需要時，
  依五層架構的升格規則抽掉寫死值，做成本 skill 的可執行腳本（`form` 轉 executor）

## 版本

| 版本 | 日期 | 變更 |
|---|---|---|
| 1.0.0 | 2026-10-29 | 由 8 個產碼食譜合併而成（anomaly-detector、chart-generator、cost-tracker、etl-pipeline、kpi-calculator、llm-tools、translator、data-contract）；各原 SKILL.md 正文原樣搬到 `references/<名稱>.md`，原目錄改為轉址 stub |
