# ark-kiro-skills

45 個 Kiro Skills 食譜集，用自然語言觸發產出智能助理功能。

## 安裝

```bash
# 直接 clone 為 .kiro/skills（repo root = skills 目錄）
git clone https://github.com/igs-paddyyang-tw/ark-kiro-skills.git .kiro/skills

# 更新
cd .kiro/skills && git pull
```

---

## Skills 總覽（45 個）

### ⚡ 核心開發流程（6）

| Skill | 說明 |
|-------|------|
| `ark-superpowers` | 7 階段開發方法論（Brainstorm→Spec→Plan→TDD→Review→Finish→Archive） |
| `ark-project-planning` | 標準化派工流程（釐清→規格→拆解→派工→追蹤→驗收） |
| `ark-code-spec-validator` | 驗證程式碼是否符合 Spec |
| `ark-code-review` | 自動化 Code Review |
| `ark-test-runner` | 測試執行與覆蓋率分析 |
| `ark-security-audit` | 安全漏洞掃描 |

### 🤖 團隊與應用建構（6）

| Skill | 說明 |
|-------|------|
| `ark-agent-team-builder` | 產出多 Agent 團隊系統（team.yaml + scheduler + 目錄） |
| `ark-kiro-init` | 產出 .kiro/ workspace 配置 |
| `ark-webapp-generator` | FastAPI + Skill 插件 + Web Chat UI |
| `ark-chatbot-generator` | Telegram Bot + LLM（Gemini/Kiro/Ollama） |
| `ark-scheduler-generator` | WorkflowEngine + ScheduleEngine |
| `ark-env-doctor` | 開發環境診斷、修復、DevContainer |

### 📄 文件與報告（8）

| Skill | 說明 |
|-------|------|
| `ark-docx-tool` | Word 文件操作 |
| `ark-pptx-tool` | PowerPoint 簡報 |
| `ark-pdf-tool` | PDF 處理 |
| `ark-xlsx-tool` | Excel 試算表 |
| `ark-report-template` | 報表模板產出 |
| `ark-html-dashboard` | HTML 互動儀表板 |
| `ark-doc-coauthoring` | 文件協作 |
| `ark-file-export` | 多格式檔案匯出 |

### 📊 資料與分析（5）

| Skill | 說明 |
|-------|------|
| `ark-db-query` | 多資料庫查詢 |
| `ark-etl-pipeline` | ETL 資料管道 |
| `ark-data-dashboard` | 數據視覺化儀表板 |
| `ark-chart-generator` | Matplotlib 圖表產出 |
| `ark-cost-tracker` | LLM 成本追蹤 |

### 🔧 開發工具（8）

| Skill | 說明 |
|-------|------|
| `ark-browser-tool` | 瀏覽器自動化 MCP + 視覺測試驗證（Playwright） |
| `ark-mcp-builder` | MCP Server 建構（Python/Node） |
| `ark-frontend-design` | 前端 UI/UX 設計 |
| `ark-llm-tools` | LLM 工具整合 |
| `ark-skill-creator` | 建立/評估/優化 Skill |
| `ark-wiki-engine` | 知識庫管理（Schema v3.0） |
| `ark-uml-generator` | Mermaid UML 圖表 |
| `ark-planning-with-files` | 持久化任務追蹤（3-File Pattern） |

### 🌐 通訊與媒體（6）

| Skill | 說明 |
|-------|------|
| `ark-telegram-bot` | Telegram Bot 完整 SOP（python-telegram-bot）+ 推送通知 |
| `ark-web-scraper` | 網頁爬取 |
| `ark-internal-comms` | 內部通訊文案 |
| `ark-translator` | 多語言翻譯 |
| `ark-canvas-design` | Canvas 圖像設計 |
| `ark-theme-factory` | 主題配色方案 |

### 🎮 遊戲與營運（6）

| Skill | 說明 |
|-------|------|
| `ark-game-design-doc` | 遊戲設計文件（GDD） |
| `ark-landing-page` | 高轉換率 Landing Page |
| `ark-marketing` | 遊戲行銷與成長策略 |
| `ark-community-ops` | 社群營運 SOP |
| `ark-retention-analysis` | 玩家留存與 LTV 分析 |
| `ark-ui-design-system` | 設計系統自動生成 |

---

## 版本異動

### v2.2 (2026-05-18) — 整合重複 Skills + 新增 8 個

**合併（需移除舊版）：**

| 舊 Skill（已刪除） | 合併到 | 說明 |
|-------------------|--------|------|
| `ark-agent-teams-builder` | `ark-agent-team-builder` | 統一為單一版本 |
| `ark-telegram-notify` | `ark-telegram-bot` | 推送功能整合到 Bot SOP |
| `ark-dev-browser` | `ark-browser-tool` | 視覺測試整合到 MCP 工具 |
| `ark-telegram`（舊名） | `ark-telegram-bot` | 改名 + 升級 |
| `generate-uml`（舊名） | `ark-uml-generator` | 統一命名 |

**新增：**

| Skill | 說明 |
|-------|------|
| `ark-community-ops` | 遊戲社群營運 SOP |
| `ark-landing-page` | Landing Page 產出 |
| `ark-marketing` | 遊戲行銷策略 |
| `ark-planning-with-files` | 持久化任務追蹤 |
| `ark-retention-analysis` | 玩家留存分析 |
| `ark-ui-design-system` | 設計系統生成 |
| `ark-project-planning` | 標準化派工流程 |
| `ark-env-doctor` | 環境診斷修復 |

### v2.1 (2026-05-14) — 扁平化 repo

- repo 結構從 `skills/{name}/` 改為根層 `{name}/`
- 安裝方式：`git clone ... .kiro/skills`（repo root = skills 目錄）

### v2.0 (2026-05-14) — 38 Skills

- 新增 ark-agent-teams-builder, ark-code-spec-validator, ark-kiro-init, ark-superpowers v2.0, generate-uml
- 全部 SKILL.md 加入 `author: paddyyang`

### v1.0 (2026-04) — 初版 32 Skills

---

## 遷移指南

### 從 v2.0/v2.1 升級到 v2.2

如果你的 `.kiro/skills/` 是舊版，需要移除已合併的 Skills：

```bash
cd .kiro/skills

# 移除已合併的舊 Skills（現在由新名稱取代）
rm -rf ark-agent-teams-builder    # → 已合併到 ark-agent-team-builder
rm -rf ark-telegram-notify        # → 已合併到 ark-telegram-bot
rm -rf ark-dev-browser            # → 已合併到 ark-browser-tool
rm -rf ark-telegram               # → 已改名為 ark-telegram-bot
rm -rf generate-uml               # → 已改名為 ark-uml-generator

# 拉取最新
git pull
```

### 各團隊部署建議

| 團隊 | 建議部署的 Skills | 說明 |
|------|-----------------|------|
| **全員** | superpowers, wiki-engine, skill-creator, code-spec-validator | 核心方法論 |
| **Leader/PM** | + project-planning | 派工流程標準化 |
| **遊戲團隊** | + game-design-doc, retention-analysis, community-ops, marketing, landing-page | 遊戲專用 |
| **開發團隊** | + browser-tool, test-runner, security-audit, env-doctor | 開發工具 |
| **營運團隊** | + telegram-bot, internal-comms, chart-generator, html-dashboard | 通訊報表 |

---

## License

MIT
