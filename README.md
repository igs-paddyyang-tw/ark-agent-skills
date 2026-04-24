# ark-kiro-skills

32 個 Kiro Skills 食譜集，用自然語言觸發產出智能助理功能。

## 安裝

```bash
# 在 Kiro IDE 專案中
git clone https://github.com/igs-paddyyang-tw/ark-kiro-skills.git .kiro/skills
```

## Skills 總覽（32 個）

### 專案建構（3 個）

| Skill | 功能 |
|-------|------|
| ark-webapp-generator | FastAPI + Web Chat UI + Skill 系統 |
| ark-chatbot-generator | Telegram Bot + LLM 對話 + 五層管線 |
| ark-scheduler-generator | WorkflowEngine + ScheduleEngine |

### 資料處理（5 個）

| Skill | 功能 |
|-------|------|
| ark-etl-pipeline | 資料轉換（compare/aggregate/filter） |
| ark-chart-generator | Matplotlib 靜態圖表（PNG） |
| ark-html-dashboard | Chart.js 互動式 HTML 儀錶板 |
| ark-data-dashboard | 遊戲資料面板（fetch + parse） |
| ark-db-query | 多資料庫查詢（SQLite/MongoDB/MSSQL/BigQuery） |

### 文件產出（6 個）

| Skill | 功能 |
|-------|------|
| ark-docx-tool | Word 文件 |
| ark-pptx-tool | PowerPoint 簡報 |
| ark-xlsx-tool | Excel 試算表 |
| ark-pdf-tool | PDF 處理 |
| ark-report-template | Jinja2 報表模板引擎 |
| ark-file-export | MD/CSV/JSON 檔案匯出 |

### 設計與內容（4 個）

| Skill | 功能 |
|-------|------|
| ark-canvas-design | 視覺藝術（PNG/PDF） |
| ark-frontend-design | 前端 UI 設計 |
| ark-theme-factory | 主題樣式套用 |
| ark-game-design-doc | 遊戲企劃文件（GDD） |

### 開發工具（7 個）

| Skill | 功能 |
|-------|------|
| ark-skill-creator | 建立/改善 Kiro Skill |
| ark-mcp-builder | MCP Server 開發 |
| ark-browser-tool | agent-browser MCP 封裝 |
| ark-code-review | 程式碼審查 |
| ark-security-audit | 安全性掃描 |
| ark-test-runner | 測試執行 + 覆蓋率 |
| ark-web-scraper | 網頁爬蟲 |

### 溝通（4 個）

| Skill | 功能 |
|-------|------|
| ark-doc-coauthoring | 文件共同撰寫 |
| ark-internal-comms | 內部溝通文件 |
| ark-translator | 多語言翻譯 |
| ark-telegram-notify | Telegram 推送通知 |

### 知識 + LLM + 追蹤（3 個）

| Skill | 功能 |
|-------|------|
| ark-wiki-engine | Wiki 知識庫引擎（8 個 Runtime Skills） |
| ark-llm-tools | LLM 通用工具（摘要/分析/問答/意圖） |
| ark-cost-tracker | LLM 成本追蹤 |

## 搭配 ark-agent-core

```bash
pip install ark-agent-core
ark init my-agent
```

## 授權

MIT
