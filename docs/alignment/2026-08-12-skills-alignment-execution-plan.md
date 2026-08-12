---
type: plan
title: ark-agent-skills 對齊執行計畫（Execution Plan）
date: 2026-08-12
status: ready
directive: docs/alignment/2026-08-12-skills-consolidation-alignment.md
executor_skill: ark-skills-align
repo: https://github.com/igs-paddyyang-tw/ark-agent-skills.git
baseline: { skill_count: 58, audit: { P0: 0, P1: 123, P2: 67 } }
target: { skill_count_range: [50, 52], audit: { P0: 0, P1: 0, P2: 0 } }
total_estimate: 5.5d
waves: 6
gates: 5
tags: [skills, consolidation, execution-plan]
audience: ai
render: none
---

# ark-agent-skills 對齊執行計畫

## 執行模型

- **Wave 制**：W0–W5 依序執行，每個 Wave 結束有 Gate（`audit_skills.py` 守門 + 該 Wave AC 驗收），Gate 不過不得進下一 Wave
- **決策來源**：所有結構性改動引用 Directive 的 D-x / A-NEW-x 編號；計畫外決策 → 停下回報，不自行發揮
- **Commit 規範**：每個 D-x 一個 commit，`align(wave-N): D-x <摘要> [refs: alignment-directive]`；每個 Gate 過後打 tag `align-w{N}-done`
- **可中斷性**：任一 Wave 結束都是穩定狀態，可暫停數天再續，靠 tag 定位進度

## 前置條件（開工檢查清單）

- [ ] ark-skills-align skill 可用（含 audit_skills.py / backfill_metadata.py）
- [ ] Directive 已 commit 至 repo `docs/alignment/`（本計畫的 frontmatter `directive` 路徑有效）
- [ ] repo 工作區乾淨（`git status` 無未提交變更），從 main 切出 `align/2026-08` 分支
- [ ] ark-html-report 與 ark-md-report 雛形可取得（W3 收編用）

---

## W0 — 基線與腳手架｜估時 0.5d

| # | 任務 | 產出 | 估時 | AC |
|---|------|------|------|-----|
| 0.1 | 收編 ark-skills-align 進 repo（第 59 個目錄，category: ops） | `ark-skills-align/` | 20min | quick_validate 通過；audit 可從 repo 內執行 |
| 0.2 | 跑基線稽核並存檔 | `docs/alignment/baseline-audit.json` | 10min | findings 與計畫 frontmatter baseline 一致（P1=123±新增 skill 差異）；偏差過大 → 停下回報 |
| 0.3 | 建 `docs/alignment/audit_config.yml`（空 exclusive_triggers，供後續擴充） | 同左 | 10min | audit 可帶 --config 跑通 |
| 0.4 | 建 `docs/reports/review/` 目錄結構（drift report 存放處） | 目錄 + .gitkeep | 5min | 存在 |
| 0.5 | 全庫引用掃描：對 5 個將 stub 化的 skill（ai-bot-builder / chatbot-generator / theme-factory / markdown-formatter / data-dashboard）各跑 grep，記錄引用清單 | `docs/alignment/ref-scan-w0.md` | 30min | 每個 skill 的外部引用點列表完整，W1 據此改鏈 |

**Gate 0**：audit 跑通、基線存檔、引用清單完成。

---

## W1 — Phase A 結構整併（D-1 ~ D-5）｜估時 1d

依 ark-skills-align 的 `references/alignment-workflow.md` 手順執行：

| # | 任務 | 手順 | 估時 | AC |
|---|------|------|------|-----|
| 1.1 | D-1：ai-bot-builder → agent-builder 合併 | §merge | 40min | 重複偵測清零；stub 含遷移說明 + 2026-08-12 + 保留至 2027-02-12 |
| 1.2 | D-2：chatbot-generator → agent-builder 合併；channel 場景寫入 `agent-builder/references/channels.md` | §merge | 60min | 「chatbot / 聊天機器人」只在 agent-builder description |
| 1.3 | D-3：theme-factory 移除；套主題操作說明併入 ark-html-report 的 styles reference（W3 收編前先暫存 `docs/alignment/theme-ops-pending.md`） | §demote | 40min | stub 完成；暫存文件標記 W3 遷移目標 |
| 1.4 | D-4：markdown-formatter 降級 → `docs/md-style-guide.md` | §demote | 40min | ≥3 個報告類 SKILL.md 引用新路徑 |
| 1.5 | D-5：data-dashboard 收編 → `html-dashboard/references/gaming-preset.md`；「博奕/老虎機/遊戲面板」觸發詞併入 html-dashboard | §preset | 60min | 用 data-dashboard 原典型 prompt 測 html-dashboard，能觸發且讀到 preset |
| 1.6 | 依 0.5 引用清單修復全庫斷鏈（引用 stub 化 skill 的文件改指新去向） | — | 40min | grep 5 個舊名，除 stub README 外零命中 |

**Gate 1**：audit `duplicate-description` 清零；active skill 數 = 53；5 個 stub 通過 `stub-format` 檢查。

---

## W2 — schema v1 回填 + 觸發詞治理｜估時 1d

| # | 任務 | 估時 | AC |
|---|------|------|-----|
| 2.1 | `backfill_metadata.py --dry-run` → 人工複核 category 歸屬與 outputs 例外（對照 taxonomy.md 例外清單） | 30min | dry-run 輸出 0 UNMAPPED / 0 PARSE_FAIL |
| 2.2 | 實跑回填，獨立 commit（只加 metadata，零 description 改動） | 20min | audit 的 missing-category / missing-outputs / missing-schema-version 清零；`git diff` 確認無 description 行變動 |
| 2.3 | 觸發詞治理：依 Directive 第 3 節矩陣逐條改 description（§triggers 手順），含實測新增的兩條（news-daily「爬蟲」、grill-me「產 spec」） | 2.5hr | audit `trigger-conflict` 清零 |
| 2.4 | 規劃三分工落地（superpowers / project-planning / planning-with-files 各加分工表 + 「不適用於 → 改用 X」）；doc-coauthoring 與 superpowers 互斥聲明 | 60min | 「寫 spec」只觸發 superpowers、「派工」只觸發 project-planning（各 3 個測試 prompt 記入 commit message） |
| 2.5 | D-9：llm-cli / llm-tools description 互斥 | 30min | 「CLI 骨架」只觸發 llm-cli、「LLM 工具函式」只觸發 llm-tools |

**Gate 2**：audit P1 = 0（全類）；每個 description 改動 commit 附 3 個觸發測試 prompt。

---

## W3 — 呈現引擎收編 + README 重寫｜估時 1d

| # | 任務 | 估時 | AC |
|---|------|------|-----|
| 3.1 | A-NEW-1：收編 ark-html-report（5 風格 token + 17 元件庫），並把 1.3 暫存的 theme 操作說明併入其 styles reference | 60min | skill 可獨立產任一風格單檔 HTML；theme-ops-pending.md 刪除 |
| 3.2 | A-NEW-2：收編 ark-md-report（Content 軌契約） | 40min | frontmatter 符合 schema v1；與 html-report 的 depends_on 互相宣告 |
| 3.3 | 制定 `docs/report-frontmatter-standard.md`（type/date/title/tags/score?/source_skill），wiki-engine ingest 章節對齊引用（原 M2.5） | 60min | 標準文件存在；wiki-engine SKILL.md 引用它 |
| 3.4 | news-daily 改消費 html-report token 與元件，刪自帶樣式（原 M2.2） | 60min | news-daily 產出可一鍵換 5 風格 |
| 3.5 | html-dashboard 主題變數名對齊 token（不改色值，原 M2.3） | 60min | dashboard 與 report CSS 變數名一致；視覺零變動（截圖 before/after 比對） |
| 3.6 | README 依 frontmatter 生成兩層分類表 + deprecated 清單（§readme 手順） | 40min | audit `readme-missing` 清零；分類表與 frontmatter 100% 一致 |

**Gate 3**：audit P0–P2 全清零；active = 55（53 + 2 新收編，不含 align skill 則 54）；同一份週報資料走 md-report → html-report 渲染 5 風格內容一致。

---

## W4 — Phase B 條件執行（D-6 ~ D-8）｜估時 1d

每項先跑前置驗證，**不過 → 記 `status: deferred` 寫回 Directive，跳過不強行執行**：

| # | 任務 | 前置驗證 | 估時 | AC（通過時） |
|---|------|----------|------|--------------|
| 4.1 | D-6：report-template MD-first 改造（Jinja2 先產 MD → html-report 渲染，原 M2.4），驗證通過後轉 stub、模板資產遷入 md-report/references/ | 同一資料 MD 與 HTML 內容一致、CollectorRunner 可解析 frontmatter | 2hr | stub 完成；舊 Jinja2 直出路徑保留標 deprecated（回滾口） |
| 4.2 | D-7：file-export 使用紀錄盤點 → 判定移除或保留 | 獨特價值僅 CSV/JSON dump 或格式路由 | 60min | 移除：stub + 路由說明併入 etl 與 Office 工具；保留：SKILL.md 加邊界聲明 |
| 4.3 | D-8：cost-tracker 收編為 kpi-calculator cost-preset | 無獨立資料管線 | 60min | §preset 手順 AC；原典型 prompt 回歸通過 |

**Gate 4**：audit 全清零；deferred 項目已寫回 Directive 並 commit。

---

## W5 — 觸發回歸 + 收尾報告｜估時 1d

| # | 任務 | 估時 | AC |
|---|------|------|-----|
| 5.1 | 觸發詞回歸測試：衝突矩陣每組獨占詞 3 個測試 prompt（2 應觸發 owner + 1 不應觸發），配 ark-skill-creator evals 機制執行 | 3hr | 全組通過；失敗項回修 description 後重測 |
| 5.2 | Directive 第 6 節成功指標逐條驗證 | 30min | 全數勾稽，未達項列入報告 |
| 5.3 | 最終 alignment report（ark-md-report review 型）：before/after skill 數、audit findings 曲線（123→7→0）、deferred 清單、觸發回歸結果 | 60min | 存 `docs/reports/review/2026-08-xx-align-final.md`，frontmatter 引用 final audit JSON |
| 5.4 | merge `align/2026-08` → main，通知團隊（deprecated 清單 + 新觸發詞對照表） | 30min | PR 描述含 D-x 對照表；tag `align-v1` |

**Gate 5（完工定義）**：audit P0–P3 = 0；skill 數落在 50–52（視 W4 deferred 數量）；觸發回歸 100% 通過。

---

## 依賴與關鍵路徑

```
W0 → W1 → W2 → W3 → W4 → W5
          │
          └ 2.3/2.4/2.5 可與 2.1/2.2 並行（不同檔案域：description vs metadata）
W3 的 3.4/3.5 依賴 3.1；3.3 依賴 3.2
W4 三項彼此獨立，可並行
```

關鍵路徑：W0 → 1.1~1.5 → 2.2 → 3.1 → 3.4 → 4.1 → 5.1，約 4d；總估 5.5d（單人序列）。
若雙人並行：一人走結構線（W1→W3 收編），一人走 description 線（W2 觸發治理），可壓至 ~3.5d。

## 風險與應對

| 風險 | 觸發訊號 | 應對 |
|------|----------|------|
| 基線偏差（repo 在計畫制定後被改動） | 0.2 findings 與 baseline 差距大 | 停下回報，重跑分析後更新 Directive |
| description 改動引發誤觸發 | 5.1 回歸失敗 | 只回修失敗組；每組獨立 commit 可單獨 revert |
| W3 收編的雛形與 repo 慣例不合 | quick_validate 失敗 | 收編前先過 ark-skill-creator 驗證流程 |
| W4 前置驗證全數不過 | 三項皆 deferred | 可接受：skill 數落 53–55，目標區間放寬並記錄於 final report |
| 中途需暫停支援主線開發 | — | 任一 Gate 後皆為穩定點，tag 定位續作 |

## 回滾

- W1/W2 全為文件層：`git revert` 至 `align-w0-done` 完整回滾
- W3 收編為新增目錄：刪目錄即回滾，README 重新生成
- W4 每項獨立 commit + 4.1 保留舊路徑，逐項可回滾
- 全案放棄：main 未受影響（分支制），刪 `align/2026-08` 即可
