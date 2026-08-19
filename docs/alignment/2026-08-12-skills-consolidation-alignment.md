---
type: decision
title: ark-agent-skills 整併與對齊指令（Alignment Directive）
date: 2026-08-12
status: approved
verdict: consolidate
score: null
source_skill: ark-skills-align
repo: https://github.com/igs-paddyyang-tw/ark-agent-skills.git
baseline:
  skill_count: 58
  metadata_schema: "name/description/metadata.author（無 category/outputs）"
target:
  skill_count_range: [50, 52]
  metadata_schema_version: 1
findings_count: { P0: 1, P1: 4, P2: 5, P3: 3 }
tags: [skills, taxonomy, consolidation, metadata, trigger-governance]
sources:
  - skills-reorg-plan.md（2026-08-11 draft）
  - repo HEAD 實測（2026-08-12 clone）
audience: ai
render: none
---

# ark-agent-skills 整併與對齊指令

## 0. Verdict（結論先行）

裁決：**consolidate**。ark-agent-skills 現有 58 個 skill，執行本指令後收斂至 50–52 個（含 M2 新增的 ark-md-report / ark-html-report 兩個呈現引擎）。全庫 frontmatter 升級至 metadata schema v1（新增 category / outputs / render / depends_on / status 欄位）。所有決策編號 D-x，動作編號 A-x，執行 agent 依 Phase 順序執行，每個 Phase 結束必須跑 `audit_skills.py` 且 P0/P1 清零才能進入下一 Phase。

本文件是 skills-reorg-plan.md（2026-08-11）的**執行版超集**：吸收原計畫 M1–M3，並納入整併分析新增的移除/合併決策。與原計畫衝突時**以本文件為準**（衝突點：D-3 theme-factory 移除取代原 M3.1 三方分工、D-5 data-dashboard 收編取代原 M1.5 depends_on 宣告）。

## 1. 分類法與 metadata schema v1（全庫適用）

### 1.1 category 受控詞彙（七類）

| code | 中文 | 定義 |
|------|------|------|
| `proc` | 流程鏈 | 開發流程文件產出（spec/plan/驗收/drift） |
| `scaffold` | 平台生成器 | 產出專案骨架 code |
| `pipeline` | 管線元件 | Python 模組 / 結構化資料，給 workflow 消費 |
| `present` | 呈現層 | HTML / 視覺產出，給人看 |
| `doc` | 文件輸出 | MD / Office 文件，人與 AI 皆讀 |
| `sop` | 領域 SOP | 策略 / 分析 MD |
| `ops` | 維運 | 環境診斷、健康檢查 |

### 1.2 frontmatter schema v1（每個 SKILL.md 必備）

```yaml
---
name: <必須等於目錄名>
description: |
  <觸發描述，遵循第 3 節觸發詞治理>
metadata:
  author: paddyyang
  schema_version: 1
  category: <七類 code 之一>
  outputs:
    - { format: md|html|png|pdf|code|data|office, audience: ai|human|both }
  render: html|none            # 報告類必填；預設 none
  depends_on: []               # 選填，skill 名稱陣列
  status: active|deprecated    # 預設 active
---
```

規則：
- `name` 與目錄名不一致 → P0
- 缺 `category` 或 `outputs` → P1
- `category` 不在受控詞彙 → P1
- deprecated stub 目錄只需 README.md（含遷移說明與日期），SKILL.md 若保留必須標 `status: deprecated` 且 description 首行為 `[DEPRECATED → 指向新 skill]`

### 1.3 雙軌輸出約定（MD-first）

- 所有「產報告/文件」類 skill 必產 MD（Content 軌，frontmatter 遵循 docs/report-frontmatter-standard.md）；HTML 為可選渲染（View 軌），統一由 ark-html-report 負責
- 禁止只改 HTML 造成兩軌漂移；MD 改動後 HTML 必須可重渲染
- **基底 + 領域特化規則（新增，schema 級規則）**：領域特化不開新 skill，收為基底 skill 的 `references/<domain>-preset.md`。本規則寫入 docs/skill-metadata-schema.md，M4 之後新 skill 一律適用

## 2. 整併決策清單

### Phase A — 立即執行（無條件）

| ID | 決策 | 對象 | 方法 | AC |
|----|------|------|------|-----|
| D-1 | 合併 | ark-ai-bot-builder → ark-agent-builder | ai-bot-builder 目錄清空只留 README stub（遷移說明 + deprecation 日期 2026-08-12 + 保留至 2027-02-12）；agent-builder description 併入「ai-bot-builder」觸發詞 | 全庫僅一份該 description 的 SKILL.md；audit 重複偵測清零 |
| D-2 | 合併 | ark-chatbot-generator → ark-agent-builder | 同 stub 手法；chatbot 場景（channel 選擇）寫入 agent-builder 的 references/channels.md；「chatbot」「聊天機器人」觸發詞移交 agent-builder | 「建 chatbot」只觸發 agent-builder |
| D-3 | 移除 | ark-theme-factory | token 系統落地後「套主題 = 改一個變數檔」，不構成獨立職能。操作說明併入 ark-html-report 的 references/styles.md；留 stub | 風格類剩 frontend-design（設計哲學）+ ui-design-system（產 token），二者 description 互斥 |
| D-4 | 降級 | ark-markdown-formatter → docs/md-style-guide.md | 內容轉為全庫共用規範文件，被報告類 skill 引用；留 stub | docs/md-style-guide.md 存在且至少被 3 個報告類 SKILL.md 引用 |
| D-5 | 收編 | ark-data-dashboard → ark-html-dashboard 的 references/gaming-preset.md | 博奕領域模型（GameInfo、遊戲卡片、數值規格卡）收為基底 skill 的 preset；「博奕/老虎機/遊戲面板」觸發詞併入 html-dashboard description；留 stub | html-dashboard 含 gaming-preset.md；改基底元件不再需要同步兩處 |

### Phase B — 條件執行（先驗證再動）

| ID | 決策 | 對象 | 前置驗證 | 方法 |
|----|------|------|----------|------|
| D-6 | 退場 | ark-report-template | M2.4（MD-first 改造）驗證通過後 | 轉為 ark-md-report + ark-html-report 組合的 stub；Jinja2 模板資產遷入 ark-md-report/references/ |
| D-7 | 移除 | ark-file-export | 盤點使用紀錄：若獨特價值僅 CSV/JSON dump（etl 可覆蓋）或格式路由（description 層問題）則移除 | 留 stub，路由說明併入 etl-pipeline 與 Office 四工具 description |
| D-8 | 收編 | ark-cost-tracker → ark-kpi-calculator 的 references/cost-preset.md | 確認 cost-tracker 無獨立資料管線（僅 KPI 領域特化） | 同 D-5 手法 |

### Phase C — 觀察名單（本輪只做 description 治理，不動結構）

| ID | 對象 | 動作 |
|----|------|------|
| D-9 | ark-llm-cli vs ark-llm-tools | description 互斥：llm-cli = 生成 CLI 專案骨架（scaffold）；llm-tools = LLM 呼叫工具函式（pipeline）。互加「不適用於 → 改用 X」聲明 |
| D-10 | ark-landing-page | 若僅產單頁 HTML → 下輪收編 present 類；若含部署/SEO → 保留。本輪只在 SKILL.md 加 TODO 註記 |
| D-11 | ark-uml-generator | 若無獨立 Mermaid/PlantUML 管線 → 下輪收為 ark-superpowers reference。本輪只註記 |

### 新增 skill（依原計畫 M2.1，於 Phase A 後執行）

| ID | 動作 |
|----|------|
| A-NEW-1 | 收編 ark-html-report 進 repo（5 風格 token + 17 元件庫，現有雛形直接進） |
| A-NEW-2 | 收編 ark-md-report 進 repo（Content 軌契約，與 html-report 成對） |

原計畫 M4 的六個缺口 skill（api-doc-sync、eval-runner、ingest-guard、data-contract、release-notes、postmortem）**不在本指令範圍**，依原計畫分批，且建立時必須符合 schema v1。

## 3. 觸發詞治理（Phase A 同步執行）

衝突矩陣目標：每個獨占觸發詞只出現在 owner skill 的 description。

| 獨占觸發詞 | owner | 需移除該詞的 skill |
|------------|-------|---------------------|
| 覆蓋率 / line coverage / pytest --cov | ark-test-runner | ark-code-spec-validator（改用「驗收條件覆蓋」） |
| 爬蟲 / 大規模抓取 / 反爬 | ark-web-scraper | ark-browser-tool |
| 瀏覽器測試 / 截圖 / 互動自動化 | ark-browser-tool | ark-web-scraper |
| 寫 spec / 產 spec | ark-superpowers | ark-doc-coauthoring、ark-project-planning |
| 派工 / 需求到派工 | ark-project-planning | ark-superpowers |
| 共筆 / 互動式迭代文件 | ark-doc-coauthoring | ark-superpowers |
| chatbot / 聊天機器人 | ark-agent-builder | （chatbot-generator 已 stub） |
| 博奕 / 老虎機 / 遊戲面板 | ark-html-dashboard | （data-dashboard 已 stub） |
| CLI 專案 / CLI 骨架 | ark-llm-cli | ark-llm-tools |
| LLM 工具函式 / LLM API 封裝 | ark-llm-tools | ark-llm-cli |

規劃三分工（原 M3.4）：superpowers = 產文件、project-planning = 需求→派工流程編排（引用 superpowers 產物）、planning-with-files = 長任務 session 狀態。三份 SKILL.md 各加分工表與「不適用於 → 改用 X」。

**實測新增衝突（2026-08-12 audit 對 repo HEAD 掃描發現，原計畫未列）**：

| 衝突 | 處置 |
|------|------|
| ark-news-daily description 含「爬蟲」 | 改為「消費 web-scraper 產出的新聞資料」表述，移除「爬蟲」一詞 |
| ark-grill-me description 含「產 spec」 | 改為「拷問後產出決策摘要，spec 撰寫交 superpowers」，移除「產 spec」 |

## 4. 執行順序與依賴

```
Phase A（D-1~D-5 + 觸發詞治理 + schema v1 全庫回填 + README 重寫）
  └→ A-NEW-1 / A-NEW-2（呈現引擎進 repo）
       └→ 原 M2.2~2.5（news-daily / html-dashboard 對齊 token、frontmatter 標準）
            └→ Phase B（D-6~D-8，逐項驗證）
                 └→ Phase C（D-9 description 治理；D-10/D-11 只註記）
```

每 Phase 的收尾動作（強制）：
1. 跑 `scripts/audit_skills.py --repo . --json audit.json`，P0/P1 必須為 0
2. README 分類表由 audit 腳本比對 frontmatter，diff 為 0
3. 產出 drift report（ark-md-report `review` 型）存 `docs/reports/review/`，commit message 引用本文件的 D-x/A-x 編號

## 5. 風險與回滾

| 風險 | 緩解 |
|------|------|
| 全庫 frontmatter 同改造成觸發大面積變動 | schema 回填只加 metadata 欄位不動 description；description 改動集中在第 3 節且逐 skill 附 3 個觸發測試 prompt |
| stub 被舊文件引用斷鏈 | 所有 stub 保留 6 個月（至 2027-02-12），README 記 deprecation 清單 |
| D-7/D-8 誤判獨特價值 | Phase B 前置驗證不過 → 決策改記 `status: deferred` 寫回本文件，不強行執行 |
| 回滾 | Phase A/C 全為文件層，git revert 完整回滾；Phase B 逐項獨立 commit |

## 6. 成功指標（全部完成後）

- skill 數 50–52，audit P0–P3 全清零
- 任一 skill frontmatter 含 schema v1 全欄位，README 與 frontmatter 100% 一致
- 第 3 節衝突矩陣每組獨占詞經 3 個測試 prompt 驗證只觸發 owner
- 呈現層（html-dashboard / news-daily / html-report / md-report）共用同一 token reference
- 日報 CollectorRunner 以單一解析器消費所有報告類 MD frontmatter
