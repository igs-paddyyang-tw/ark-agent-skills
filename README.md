# ark-kiro-skills

**55 個** Kiro Skills 食譜集，用自然語言觸發產出智能助理功能。

## 安裝

```bash
# 直接 clone 為 .kiro/skills（repo root = skills 目錄）
git clone https://github.com/igs-paddyyang-tw/ark-kiro-skills.git .kiro/skills

# 更新
cd .kiro/skills && git pull
```

---

## 建置流程（Flow Build）

### 從零建立 AI Agent Team（Script 驅動）

> **設計原則：** Script 產出確定性結構，AI 只做串聯和功能疊加。初始就有可以運作的版本。

```
Step 1: ark-agent-team-builder
  └─ scripts/build_team.py → 一鍵產出完整可運作專案
     team.yaml + scheduler.yaml + start.py + start-team.bat/sh
     src/ark_team_core/（16 模組）+ src/{pkg}/（業務層）
     agents/ + tasks/ + docs/ + secrets/ + knowledge/
     .kiro/（admin 基礎配置）

Step 2: ark-kiro-init
  └─ scripts/build_kiro.py → 批次產出所有 agent .kiro/
     .kiro/（admin 完整版：SOUL + TEAM + KIRO + mcp.json）
     agents/{name}/.kiro/（每個 agent 完整配置）
     --clone-skills → clone 共用 Skills 倉庫
     --validate → 驗證結構完整性

Step 3: 手動設定
  └─ .env（Telegram Bot Token）+ team.yaml（group_id / topics）

Step 4: 啟動
  └─ start-team.bat（Windows）/ start-team.sh（Mac/Linux）
     → 6/6 agents running，Telegram Bot 就緒
```

### 日常開發流程（SDD — Spec-Driven Development）

```
① ark-superpowers     → 產出 Spec / Design / Plan
② ark-skill-creator   → 建立可重用 Skill
③ ark-code-spec-validator → 驗證 code 與 spec 一致性（drift > 70）
④ ark-wiki-engine     → 歸檔經驗到知識庫
```

### 核心 4 Skills（全員必裝）

| Skill | 用途 |
|-------|------|
| `ark-superpowers` | 文件產出（spec / design / plan / one-pager） |
| `ark-wiki-engine` | 知識庫管理（Schema v3.0，ingest / query） |
| `ark-skill-creator` | 建立/評估/優化 Skill |
| `ark-code-spec-validator` | 驗證 code 與 spec 一致性 |

---

## Skills 總覽（52 個）

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
| `ark-agent-team-builder` | 一鍵產出完整可運作 Agent Team（build_team.py + 業務層 vendored） |
| `ark-kiro-init` | 批次產出所有 agent .kiro/（build_kiro.py + assets 模板） |
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

### 🔧 開發工具（10）

| Skill | 說明 |
|-------|------|
| `ark-browser-tool` | 瀏覽器自動化 MCP + 視覺測試驗證（Playwright） |
| `ark-mcp-builder` | MCP Server 建構（Python/Node） |
| `ark-frontend-design` | 前端 UI/UX 設計 |
| `ark-llm-tools` | LLM 工具整合 |
| `ark-llm-cli` | 統一封裝多個 LLM CLI（Gemini/Kiro/Claude/Antigravity） |
| `ark-skill-creator` | 建立/評估/優化 Skill |
| `ark-wiki-engine` | 知識庫管理（Schema v3.0） |
| `ark-uml-generator` | Mermaid UML 圖表 |
| `ark-planning-with-files` | 持久化任務追蹤（3-File Pattern） |
| `ark-news-daily` | 科技日報 HTML 卡片產出 |

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

### 🧠 AI 進階（5）

| Skill | 說明 |
|-------|------|
| `ark-conversational` | 多輪對話管理 |
| `ark-critic-loop` | 自我審查品質迴圈 |
| `ark-plan-execute-verify` | 三階段工作流（計畫→執行→驗證） |
| `ark-spec-first` | 先確認規格再執行 |
| `ark-openai-tool` | OpenAI API 整合 |

---

## 各團隊部署建議

| 團隊 | 建議部署的 Skills | 說明 |
|------|-----------------|------|
| **全員** | superpowers, wiki-engine, skill-creator, code-spec-validator | 核心方法論 |
| **Leader/PM** | + project-planning, doc-coauthoring, planning-with-files | 派工 + 文件 |
| **遊戲團隊** | + game-design-doc, retention-analysis, community-ops, marketing | 遊戲專用 |
| **開發團隊** | + browser-tool, test-runner, security-audit, env-doctor, mcp-builder, llm-cli | 開發工具 |
| **營運團隊** | + telegram-bot, internal-comms, chart-generator, html-dashboard, news-daily | 通訊報表 |
| **數據團隊** | + db-query, etl-pipeline, data-dashboard, cost-tracker | 資料分析 |

---

## 參考資源

| 資源 | 連結 | 說明 |
|------|------|------|
| **ark-kiro-skills**（本 repo） | https://github.com/igs-paddyyang-tw/ark-kiro-skills | 52 個基礎 Skills |
| **agency-agents** | https://github.com/msitarzewski/agency-agents | AI 配置能力參考（Agent 角色定義模式） |
| **Skills Hub** | https://skills-hub.ai/ | 4,700+ Skills 聚合平台 |
| **Anthropic Skills（官方）** | https://github.com/anthropics/skills | Anthropic 官方 Skills 公開 repo |

---

## 版本異動

### v2.5 (2026-06-05) — Script 化 Wiki Engine + 新增 3 Skills

**新增 Skills（52 → 55）：**
- `ark-ai-bot-builder`：一鍵產出完整 AI Agent Bot Workspace（build_bot.py + assets + templates）
- `ark-team-runtime`：Agent Team runtime 啟動程式產出
- `ark-executive-assistant`：部長個人助理（工作紀錄 + 5 維度追問 + 日誌提醒）

**Script 化：**
- `ark-wiki-engine`：新增 `build_wiki.py`（一鍵產出 8 Skills + 知識庫 schema）+ `validate_wiki.py`
- `ark-ai-bot-builder`：完整 assets/scripts/templates（18 個檔案）
- `ark-chatbot-generator`：SKILL.md 大幅更新（permissions、memory_search、user_profiler、skill_tracker、排程 CRUD）

**更新 Skills：**
- `ark-agent-team-builder`（SKILL + refs + build_team.py）
- `ark-kiro-init`（SKILL + SOUL-admin + route-message）
- `ark-telegram-bot`（SKILL）
- `ark-llm-cli`（SKILL）
- `ark-md-to-pixi-ast`（7 個 Python 腳本）

### v2.4 (2026-05-27) — build_team/build_kiro Script 化 + 新增 2 Skills

**核心改動：**
- `ark-agent-team-builder`：`build_team.py` v2.0 — 一鍵產出完整可運作專案（含業務層 telegram_adapter/api/event_log）、`start-team.sh`、validate 業務層
- `ark-kiro-init`：`build_kiro.py` v1.0 — 批次產出所有 agent .kiro/、admin mcp.json P0 Bug 修復、assets 模板（SOUL-admin/leader/worker + TEAM + KIRO）
- `TeamConfig`：加 `name` + `examples` 欄位，telegram_adapter 動態讀取（不再 hardcode）
- `team.yaml` 模板：加入 `name:` + `examples:` 欄位

**新增 Skills（50 → 52）：**
- `ark-llm-cli`：統一封裝多個 LLM CLI（Gemini/Kiro/Claude/Antigravity）
- `ark-news-daily`：科技日報 HTML 卡片產出

**更新 Skills：**
- `ark-agent-team-builder`、`ark-kiro-init`、`ark-chatbot-generator`、`ark-env-doctor`、`ark-scheduler-generator`、`ark-team-runtime`、`ark-telegram-bot`、`ark-webapp-generator`

### v2.3 (2026-05-20) — GA Team 經驗回補

- `ark-agent-team-builder`：加入 admin 目錄、純私聊模式、Skills 部署規則
- `ark-kiro-init`：加入 KIRO.md、admin 角色、AGENTS.md 模板更新
- `ark-chatbot-generator`、`ark-telegram-bot`：更新
- README 加入 Flow Build 文件 + 參考資源

### v2.2 (2026-05-18) — 整合重複 Skills + 新增 8 個

**合併（需移除舊版）：**

| 舊 Skill（已刪除） | 合併到 |
|-------------------|--------|
| `ark-agent-teams-builder` | `ark-agent-team-builder` |
| `ark-telegram-notify` | `ark-telegram-bot` |
| `ark-dev-browser` | `ark-browser-tool` |

**新增：** community-ops, landing-page, marketing, planning-with-files, retention-analysis, ui-design-system, project-planning, env-doctor

### v2.1 (2026-05-14) — 扁平化 repo

- repo 結構從 `skills/{name}/` 改為根層 `{name}/`
- 安裝方式：`git clone ... .kiro/skills`（repo root = skills 目錄）

### v2.0 (2026-05-14) — 38 Skills

### v1.0 (2026-04) — 初版 32 Skills

---

## License

MIT


## 安裝

```bash
# 直接 clone 為 .kiro/skills（repo root = skills 目錄）
git clone https://github.com/igs-paddyyang-tw/ark-kiro-skills.git .kiro/skills

# 更新
cd .kiro/skills && git pull
```

---

## 建置流程（Flow Build）

### 從零建立 AI Agent Team

```
┌─────────────────────────────────────────────────────────────┐
│  Phase 1：團隊骨架                                           │
│  Skill: ark-agent-team-builder                               │
│  產出: team.yaml + scheduler.yaml + agents/ 目錄結構          │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 2：AI 配置                                            │
│  Skill: ark-kiro-init × N（每個 agent）                       │
│  產出: .kiro/（steering + agent.json + skills + settings）    │
│       + knowledge/（五件套）+ docs/ + output/                 │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 3：業務工具                                           │
│  Skills: ark-mcp-builder + 業務 Skills                       │
│  產出: MCP Server + 角色專屬 Skills                           │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 4：品質驗證                                           │
│  Skills: ark-test-runner + ark-code-spec-validator            │
│  產出: 測試 + Drift Report                                   │
└─────────────────────────────────────────────────────────────┘
```

### 日常開發流程（SDD — Spec-Driven Development）

```
① ark-superpowers     → 產出 Spec / Design / Plan
② ark-skill-creator   → 建立可重用 Skill
③ ark-code-spec-validator → 驗證 code 與 spec 一致性（drift > 70）
④ ark-wiki-engine     → 歸檔經驗到知識庫
```

### 核心 4 Skills（全員必裝）

| Skill | 用途 |
|-------|------|
| `ark-superpowers` | 文件產出（spec / design / plan / one-pager） |
| `ark-wiki-engine` | 知識庫管理（Schema v3.0，ingest / query） |
| `ark-skill-creator` | 建立/評估/優化 Skill |
| `ark-code-spec-validator` | 驗證 code 與 spec 一致性 |

---

## Skills 總覽（50 個）

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
| `ark-agent-team-builder` | 產出多 Agent 團隊系統（team.yaml + scheduler + 目錄 + admin） |
| `ark-kiro-init` | 產出 .kiro/ workspace 配置（steering + agent.json + knowledge 五件套） |
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

### 🧠 AI 進階（5）

| Skill | 說明 |
|-------|------|
| `ark-conversational` | 多輪對話管理 |
| `ark-critic-loop` | 自我審查品質迴圈 |
| `ark-plan-execute-verify` | 三階段工作流（計畫→執行→驗證） |
| `ark-spec-first` | 先確認規格再執行 |
| `ark-openai-tool` | OpenAI API 整合 |

---

## 各團隊部署建議

| 團隊 | 建議部署的 Skills | 說明 |
|------|-----------------|------|
| **全員** | superpowers, wiki-engine, skill-creator, code-spec-validator | 核心方法論 |
| **Leader/PM** | + project-planning, doc-coauthoring, planning-with-files | 派工 + 文件 |
| **遊戲團隊** | + game-design-doc, retention-analysis, community-ops, marketing | 遊戲專用 |
| **開發團隊** | + browser-tool, test-runner, security-audit, env-doctor, mcp-builder | 開發工具 |
| **營運團隊** | + telegram-bot, internal-comms, chart-generator, html-dashboard | 通訊報表 |
| **數據團隊** | + db-query, etl-pipeline, data-dashboard, cost-tracker | 資料分析 |

---

## 參考資源

| 資源 | 連結 | 說明 |
|------|------|------|
| **ark-kiro-skills**（本 repo） | https://github.com/igs-paddyyang-tw/ark-kiro-skills | 50 個基礎 Skills |
| **agency-agents** | https://github.com/msitarzewski/agency-agents | AI 配置能力參考（Agent 角色定義模式） |
| **Skills Hub** | https://skills-hub.ai/ | 4,700+ Skills 聚合平台 |
| **Anthropic Skills（官方）** | https://github.com/anthropics/skills | Anthropic 官方 Skills 公開 repo |

---

## 版本異動

### v2.3 (2026-05-20) — GA Team 經驗回補

- `ark-agent-team-builder`：加入 admin 目錄、純私聊模式、Skills 部署規則
- `ark-kiro-init`：加入 KIRO.md、admin 角色、AGENTS.md 模板更新（reply 必用 + 編號選項 + 終端回饋）
- `ark-chatbot-generator`：更新
- `ark-telegram-bot`：更新
- README 加入 Flow Build 文件 + 參考資源

### v2.2 (2026-05-18) — 整合重複 Skills + 新增 8 個

**合併（需移除舊版）：**

| 舊 Skill（已刪除） | 合併到 |
|-------------------|--------|
| `ark-agent-teams-builder` | `ark-agent-team-builder` |
| `ark-telegram-notify` | `ark-telegram-bot` |
| `ark-dev-browser` | `ark-browser-tool` |

**新增：** community-ops, landing-page, marketing, planning-with-files, retention-analysis, ui-design-system, project-planning, env-doctor

### v2.1 (2026-05-14) — 扁平化 repo

- repo 結構從 `skills/{name}/` 改為根層 `{name}/`
- 安裝方式：`git clone ... .kiro/skills`（repo root = skills 目錄）

### v2.0 (2026-05-14) — 38 Skills

### v1.0 (2026-04) — 初版 32 Skills

---

## License

MIT
