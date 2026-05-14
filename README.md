# ark-kiro-skills

38 個 Kiro Skills 食譜集，用自然語言觸發產出智能助理功能。

## 安裝

```bash
# 直接 clone 為 .kiro/skills（repo root = skills 目錄）
git clone https://github.com/igs-paddyyang-tw/ark-kiro-skills.git .kiro/skills
```

## Skills 總覽（37 個）

### 核心開發流程（5 個）

| Skill | 說明 |
|-------|------|
| `ark-superpowers` | 7 階段開發方法論（brainstorm→spec→plan→TDD→review→finish→archive） |
| `ark-code-spec-validator` | 驗證程式碼是否符合 spec |
| `ark-skill-creator` | 建立新 Skill |
| `ark-wiki-engine` | 知識庫管理（Schema v3.0） |
| `ark-kiro-init` | 產出 .kiro/ workspace 配置 |

### 團隊與應用（5 個）

| Skill | 說明 |
|-------|------|
| `ark-agent-teams-builder` | 產出多 Agent 團隊系統（team.yaml + runtime） |
| `ark-webapp-generator` | FastAPI + Skill 插件系統 + Web Chat UI |
| `ark-chatbot-generator` | Telegram Bot + LLM（Gemini/Kiro/Ollama） |
| `ark-scheduler-generator` | WorkflowEngine + ScheduleEngine |
| `ark-env-doctor` | 開發環境診斷、修復、DevContainer 產出 |

### 文件與報告（8 個）

| Skill | 說明 |
|-------|------|
| `ark-docx-tool` | Word 文件操作 |
| `ark-pptx-tool` | PowerPoint 簡報 |
| `ark-pdf-tool` | PDF 處理 |
| `ark-xlsx-tool` | Excel 試算表 |
| `ark-report-template` | 報表模板產出 |
| `ark-html-dashboard` | HTML 儀表板 |
| `ark-doc-coauthoring` | 文件協作 |
| `ark-file-export` | 檔案匯出 |

### 資料與分析（5 個）

| Skill | 說明 |
|-------|------|
| `ark-db-query` | 資料庫查詢 |
| `ark-etl-pipeline` | ETL 管道 |
| `ark-data-dashboard` | 數據儀表板 |
| `ark-chart-generator` | 圖表產出 |
| `ark-cost-tracker` | 成本追蹤 |

### 開發工具（8 個）

| Skill | 說明 |
|-------|------|
| `ark-code-review` | Code Review |
| `ark-test-runner` | 測試執行 |
| `ark-security-audit` | 安全掃描 |
| `ark-mcp-builder` | MCP Server 建構 |
| `ark-frontend-design` | 前端設計 |
| `ark-llm-tools` | LLM 工具整合 |
| `ark-game-design-doc` | 遊戲設計文件 |
| `generate-uml` | Mermaid UML 圖表 |

### 通訊與其他（7 個）

| Skill | 說明 |
|-------|------|
| `ark-browser-tool` | 瀏覽器操作 |
| `ark-web-scraper` | 網頁爬取 |
| `ark-telegram-notify` | Telegram 通知 |
| `ark-internal-comms` | 內部通訊 |
| `ark-translator` | 翻譯 |
| `ark-canvas-design` | Canvas 設計 |
| `ark-theme-factory` | 主題工廠 |

## 使用方式

Skills 會自動觸發（依 description 匹配），也可用 slash command 手動觸發：

```
> /ark-superpowers
> /ark-kiro-init
> /ark-agent-teams-builder
```

## 版本

- **v2.1** (2026-05-14) — 扁平化 repo 結構 + 新增 ark-env-doctor（共 38 Skills）
- **v2.0** (2026-05-14) — 新增 5 個核心 Skills + ark-superpowers 升級為 7 階段方法論
- **v1.0** (2026-04) — 初版 32 個 Skills

## License

MIT
