# ark-agent-skills 目錄

> 單一真相來源：`igs-paddyyang-tw/ark-agent-skills`。
> 各專案以 `sync_default_skills.py` 或逐 skill 複製取用。

**目錄章節由 `scripts/gen_readme.py` 依各 `SKILL.md` 的 frontmatter 產生。**
新增／移除 skill 後執行一次，不要手改表格 —— 手動維護的索引必定過期
（2026-08-12 實測：標題寫 66、表格列 57、目錄實際 63，三個數字互不相同）。

---

## Changelog

### 2026-08-12

| 動作 | Skill | 說明 |
|------|-------|------|
| ✅ 新增 | `ark-md-report` | Content 軌報告引擎（5 類型 × frontmatter 契約 × AI 寫作規則） |
| ✅ 新增 | `ark-md-report/scripts/` | Deterministic 守門：report_lint + report_pair + report_register |
| ✅ 新增 | `ark-md-report/references/agent-operating-guide.md` | 三件套運作契約 + 各 agent 提詞 |
| ✅ 新增 | `ark-html-report` | View 軌呈現引擎（5 風格 token × 17 元件 × Chart.js） |
| ✅ 新增 | `ark-api-doc-sync` | FastAPI route → docs API 表格自動同步 |
| ✅ 新增 | `ark-eval-runner` | LLM 輸出回歸評測 |
| ✅ 新增 | `ark-ingest-guard` | 知識入庫 prompt injection 消毒 |
| ✅ 新增 | `ark-data-contract` | 管線元件間 schema 契約驗證 |
| ✅ 新增 | `ark-release-notes` | git log → 結構化 changelog |
| ❌ 移除 | `ark-report-template` | → 被 `ark-md-report` + `ark-html-report` 雙軌取代 |
| ❌ 移除 | `ark-postmortem` | → 併入 `ark-md-report` type: incident |
| ❌ 移除 | `ark-ai-bot-builder` | → 與 `ark-agent-builder` 完全重複 |
| ❌ 移除 | `ark-daily-decision-digest` | 廢棄（依賴 decision_manager 硬編碼） |
| ❌ 移除 | `ark-policy-translate` | 廢棄（統一繁中不需翻譯） |
| 🟡 整合 | `ark-data-dashboard` | 加 `depends_on: [ark-html-dashboard]`（降級為 profile） |
| 🔧 修正 | `ark-code-spec-validator` | 四段工作流鏈優化（17 任務：評分公式 + 方向分流 + AC-ID） |
| 🔧 修正 | `ark-superpowers` | 15 任務優化（鏈級交接 + 驗證器可信化 + slug + 一致性） |
| 🔧 修正 | `ark-html-dashboard` | theme: auto/dark/light（自動建議風格） |
| 🔧 修正 | `ark-data-dashboard` | theme: auto |
| 🔧 修正 | `ark-webapp-generator` | theme: auto |
| 📋 治理 | 全庫 SKILL.md | 回填 category / outputs frontmatter（`ark-agent-builder` 2026-08-12 補上） |
| 📋 治理 | 5 組觸發詞衝突 | ⏳ **未完成** —— `docs/trigger-matrix.md` 尚未建立 |

### 2026-08-05~07

| 動作 | Skill | 說明 |
|------|-------|------|
| ✅ 新增 | `ark-grill-me` | 實作前拷問設計（加入預設 skills） |
| ✅ 新增 | `ark-spec-executor` | 執行 plan.md 任務清單（加入預設 skills） |
| 🔧 修正 | `ark-wiki-engine` | 本地化 7 scripts（ingest/query/lint/graph/index/build/validate） |

---


<!-- BEGIN GENERATED CATALOGUE -->

> **63 個 Skill**，兩層分類（職能角色 × 受眾）。
> 本節由 `scripts/gen_readme.py` 依各 `SKILL.md` 的 frontmatter 產生，**不要手動編輯**。

## ① 流程鏈 Process

> 輸出：MD 給 AI｜`category: process`｜9 個

| Skill | 定位 |
|-------|------|
| `ark-code-spec-validator` | 驗證 code 與 spec/design 文件的一致性，產出 Drift Report。 |
| `ark-doc-coauthoring` | 引導使用者透過結構化工作流共同撰寫文件。 |
| `ark-grill-me` | 在實作前拷問設計：AI 逐一提問決策樹的每個分支，直到人類與 AI 達成共識。 |
| `ark-planning-with-files` | 持久化任務追蹤：複雜任務（3+ 步驟）自動建立 3-File Pattern（task_plan.md / findings.md / progress.md）， 防止 context 丟失、goal… |
| `ark-project-planning` | 標準化專案計畫流程。 |
| `ark-skill-creator` | 建立新 Skill、修改和改善既有 Skill、測量 Skill 效能。 |
| `ark-spec-executor` | 讀取 plan.md（含任務表+AC+依賴），自動拆解→角色切換執行→AC 驗收→產出驗收報告。 |
| `ark-superpowers` | 產出工程標準化文件（Spec 規格、Design 設計/ADR、Execution Plan 執行計畫）， 基於 power-engineer-skills 框架，協助資深工程師與技術領導者 將技術決… |
| `ark-ux-spec-validator` | 驗證 Telegram Bot UX 實作與 UX Spec 文件的一致性。 |

## ② 平台生成器 Scaffolders

> 輸出：專案骨架｜`category: scaffolder`｜10 個

| Skill | 定位 |
|-------|------|
| `ark-agent-builder` | 快速產出完整 AI Agent Bot Workspace（1~6 階段漸進式）。 |
| `ark-agent-team-builder` | 一鍵產出完整 AI Agent 團隊平台（五層架構：Entry + OS + Collaboration + Execution + Knowledge）。 |
| `ark-chatbot-generator` | 在既有 Web 專案上加入 Telegram Bot + LLM 對話能力 + Kiro CLI Agent 整合 + 呼叫 Skill 執行，可獨立運作。 |
| `ark-docker-deploy` | 產出容器化部署配置（Dockerfile + docker-compose.yaml + .dockerignore + 部署腳本）， 支援 Python / Node / Go 專案自動偵測，mul… |
| `ark-kiro-init` | 產出完整的 .kiro/ workspace 配置（agents、steering、prompts、skills、settings）， 根據使用者指定的角色自動生成。 |
| `ark-llm-cli` | 統一封裝多個 LLM CLI Agent 為標準化 Skill，支援 Gemini CLI、Kiro CLI、Claude CLI、Antigravity CLI。 |
| `ark-mcp-builder` | 建立高品質 MCP（Model Context Protocol）Server 的指南， 讓 LLM 能透過設計良好的 Tools 與外部服務互動。 |
| `ark-scheduler-generator` | 在既有專案上加入 WorkflowEngine 工作流引擎、ScheduleEngine 排程引擎， 並產出範例 Workflow YAML、排程定義與 agent-browser MCP Serve… |
| `ark-telegram-bot` | Telegram Bot 開發完整 SOP（python-telegram-bot）：傳送圖片/檔案/相簿、 Web App 整合、Menu 命令設定、InlineKeyboard 互動、訊息格式化與… |
| `ark-webapp-generator` | 產出完整 Web 專案骨架，包含 FastAPI Server、Web Chat UI、BaseSkill 插件系統 與 1 個最小範例 Skill（echo）。 |

## ③ 管線元件 Pipeline

> 輸出：結構化資料｜`category: pipeline`｜20 個

| Skill | 定位 |
|-------|------|
| `ark-anomaly-detector` | 產出 KPI 異常偵測模組 + 告警規則引擎 + MCP Tool + 排程整合。 |
| `ark-api-doc-sync` | 當使用者需要將 FastAPI route 定義同步到 docs/ 目錄下的 API 文件表格時使用此技能。 |
| `ark-browser-tool` | 瀏覽器自動化工具：使用 Microsoft Webwright（terminal-native web agent 框架）。 |
| `ark-chart-generator` | 產出 chart_generator.py 標準化圖表 Skill，使用 Matplotlib 將結構化數據轉換為圖表， 輸出至 artifacts/charts 目錄。 |
| `ark-code-review` | 產出程式碼審查 Skill，支援 Python/TypeScript 程式碼品質檢查、 風格一致性驗證、安全性掃描、PR 審查報告產生。 |
| `ark-cost-tracker` | 產出 API 呼叫成本追蹤 Skill，記錄 LLM API 的 token 使用量和費用。 |
| `ark-data-contract` | 當使用者需要驗證管線元件間的 schema 契約時使用此技能。 |
| `ark-db-query` | 產出 db_query.py Skill，支援多種資料庫查詢並回傳標準格式（list[dict]）， 可直接串接 etl-pipeline 和 chart-generator。 |
| `ark-etl-pipeline` | 產出 etl_pipeline.py 資料轉換 Skill，將任何資料來源（CSV、JSON、API 回傳、 Skill 輸出、資料庫查詢）轉換為 chart_generator 可直接使用的標準格式… |
| `ark-eval-runner` | 當使用者需要對 LLM 輸出進行回歸評測時使用此技能。 |
| `ark-file-export` | 產出檔案匯出 Skill，將記憶體中的資料（dict/list/str）輸出為 Markdown、CSV、JSON 檔案。 |
| `ark-ingest-guard` | 當知識庫入庫前需要進行 prompt injection 消毒時使用此技能。 |
| `ark-kpi-calculator` | 產出標準化 KPI 計算引擎模組 + MCP Tool，支援遊戲類指標（DAU/MAU/ARPU/RTP/留存率/LTV） 與通用指標（轉換率/流失率/NPS）。 |
| `ark-llm-tools` | 產出 LLM 通用工具 Skills（summarize、analyze、qa、intent_parse）， 搭配 GeminiAdapter 或 LLMAdapter 進行文字摘要、資料分析、問答、… |
| `ark-news-daily` | 產出科技日報 HTML 卡片，將新聞素材結構化後套用模板。 |
| `ark-security-audit` | 產出 security_audit.py 安全性掃描 Skill，對專案進行程式碼安全性檢查與弱點偵測。 |
| `ark-test-runner` | 產出 test_runner.py 自動化測試執行 Skill，執行 pytest 測試並產生覆蓋率報告。 |
| `ark-translator` | 產出 translator.py 多語言翻譯 Skill，搭配 Gemini LLM 進行高品質翻譯， 支援繁體中文、簡體中文、英文、日文互譯。 |
| `ark-web-scraper` | 產出進階網頁爬蟲 Skill，基於 Scrapling 框架。 |
| `ark-wiki-engine` | 產出 Wiki 知識庫引擎，以 Markdown 為基礎的知識管理系統。 |

## ④ 呈現層 View

> 輸出：HTML / 視覺（給人看）｜`category: view`｜8 個

| Skill | 定位 |
|-------|------|
| `ark-canvas-design` | 使用設計哲學創作精美的視覺藝術，輸出 .png 和 .pdf 文件。 |
| `ark-data-dashboard` | 產出博奕遊戲標準化面板，包含遊戲資訊抓取、數值規格解析、網頁視覺化 Dashboard。 |
| `ark-frontend-design` | 產出獨特、生產級品質的前端介面，具備高設計水準。 |
| `ark-html-dashboard` | 產出 Self-contained 互動式 HTML 數據儀錶板，使用 Chart.js 圖表、 KPI 卡片、篩選器、排序表格，所有資料內嵌於單一 HTML 檔案。 |
| `ark-html-report` | 產出專業的單檔 HTML 報告（技術報告、日報/週報、數據分析、競品分析、專案總結、N-M-P-Q 報告）。 |
| `ark-landing-page` | 快速產出高轉換率 Landing Page：遊戲預註冊頁、活動頁、產品介紹頁。 |
| `ark-theme-factory` | 為 artifacts 套用主題樣式的工具包。 |
| `ark-ui-design-system` | 設計系統自動生成：分析專案需求後產出完整設計系統（色彩、字型、元件、間距）， 確保 UI 產出不是 AI 預設風格（紫色漸層）而是專業、一致的設計。 |

## ⑤ 呈現層 Content

> 輸出：結構化 MD（給 AI 讀）｜`category: presentation-content`｜1 個

| Skill | 定位 |
|-------|------|
| `ark-md-report` | 產出「給 AI 看」的結構化分析報告 Markdown（Content 軌），與 ark-html-report（View 軌）成對。 |

## ⑥ 文件輸出 Document

> 輸出：MD / Office｜`category: document`｜9 個

| Skill | 定位 |
|-------|------|
| `ark-docx-tool` | 當使用者想要建立、讀取、編輯或操作 Word 文件（.docx 檔案）時使用此技能。 |
| `ark-game-design-doc` | > 根據遊戲構想或需求描述，產出完整的遊戲企劃文件（Game Design Document, GDD）。 |
| `ark-internal-comms` | 協助撰寫各類內部溝通文件，使用公司慣用的格式。 |
| `ark-markdown-formatter` | 將任何內容轉換為精美、結構化的 Markdown 文件。 |
| `ark-pdf-tool` | 處理 PDF 檔案的所有操作。 |
| `ark-pptx-tool` | 任何涉及 .pptx 檔案的情境皆使用此技能——無論作為輸入、輸出或兩者皆是。 |
| `ark-release-notes` | 當使用者需要從 git log 產出結構化 changelog 或版本說明時使用此技能。 |
| `ark-uml-generator` | 產出 Mermaid 格式的 UML 圖表，用於系統設計文件。 |
| `ark-xlsx-tool` | 當試算表檔案為主要輸入或輸出時，請使用此技能。 |

## ⑦ 領域 SOP Domain

> 輸出：策略分析 MD｜`category: domain`｜4 個

| Skill | 定位 |
|-------|------|
| `ark-community-ops` | 遊戲社群營運 SOP：社群平台管理、玩家互動、內容排程、危機處理、KOL 合作。 |
| `ark-executive-assistant` | 部長個人助理。 |
| `ark-marketing` | 遊戲行銷與成長策略：ASO（應用商店優化）、CRO（轉換率優化）、 文案撰寫、社群行銷、UA（用戶獲取）、LiveOps 活動規劃。 |
| `ark-retention-analysis` | 玩家留存與 LTV 分析：Cohort 分析、留存曲線、LTV 預測、流失預警。 |

## ⑧ 維運 Ops

> 輸出：診斷 / 驗證｜`category: ops`｜2 個

| Skill | 定位 |
|-------|------|
| `ark-dashboard-health` | 自動化測試 Dashboard 所有 API 端點 + SSE 連線 + 前端頁面可用性。 |
| `ark-env-doctor` | 當使用者遇到開發環境問題時使用此技能。 |

## 🗑️ 已移除（保留 stub 供遷移）

> 目錄下只剩 `README.md` 的資料夾。**不計入上方總數。**

| Skill | 遷移到 |
|-------|--------|
| `ark-ai-bot-builder` | `ark-agent-builder` |
| `ark-postmortem` | `ark-md-report`（type: incident） |
| `ark-report-template` | `ark-md-report`（Content 軌）+ `ark-html-report`（View 軌） |

<!-- END GENERATED CATALOGUE -->

---

## 分類規格

每個 `SKILL.md` 的 frontmatter 需有：

```yaml
metadata:
  author: paddyyang
  category: pipeline        # 見下表，決定它排進 README 哪一節
  outputs:
    - { format: md, audience: ai }      # format: md/html/project/png/xlsx…
  depends_on: []                        # 依賴的其他 skill
```

| category | 章節 | 產物性質 |
|----------|------|---------|
| `process` | ① 流程鏈 | 工作流程本身，產出 MD 給 AI 接手 |
| `scaffolder` | ② 平台生成器 | 專案骨架 |
| `pipeline` | ③ 管線元件 | 可被程式呼叫的元件，產出結構化資料 |
| `view` | ④ 呈現層 View | HTML／視覺，**給人看** |
| `presentation-content` | ⑤ 呈現層 Content | 結構化 MD，**給 AI 讀**（與 view 成對） |
| `document` | ⑥ 文件輸出 | MD／Office 檔案 |
| `domain` | ⑦ 領域 SOP | 特定業務領域的做法 |
| `ops` | ⑧ 維運 | 診斷、驗證 |

**新增 category 必須同時登記到 `scripts/gen_readme.py` 的 `SECTIONS`**，
否則該 skill 會落到「⚠️ 未分類」一節 —— 那一節的存在就是為了讓漏登記看得見。

> 原本此處寫「詳見 `docs/skill-metadata-schema.md`」，但該檔案（以及整個
> `docs/` 目錄）**並不存在**。規格改為就地說明，避免再指向空連結。
