# Skill 選用地圖（大腦範本）

> **用途**：建 agent 時把這張表放進專案根目錄 `AGENTS.md`（或 steering 的共用規範），
> 讓 agent 主動知道「遇到什麼問題該用哪個 skill、怎麼串鏈」。
>
> **設計原則**：base_skills（見 `role-skills-map.md`）已讓每個 agent 都是「萬能 AI +
> 軟體工程師」——備齊需求→規格→執行→驗證→知識→報告的完整武器。這張地圖不是加能力，
> 是**教會大腦調度既有武器**：先找現成 skill，別重造輪子。
>
> 各專案套用時：只保留該專案實際裝的 skill 列（依 `sync_skills.py` 的 MATRIX 裁剪）。

## 🔧 完整開發鏈（Loop 五件套，從需求到交付）

```
需求不清 → ark-grill-me（反詰拷問，逼出決策）
   ↓
訂規格/設計 → ark-superpowers（Spec/Design/ADR/執行計畫）
   ↓
依規格實作 → ark-spec-executor（讀 plan.md 自動拆解執行 + AC 驗收）
   ↓
驗證 ┬ code 對不對規格 → ark-code-spec-validator（Drift Report；--sync 反向同步 API 文件）
     └ 提詞/AI內文對不對 → ark-prompt-spec-validator（frontmatter/觸發詞/行為 eval）
   ↓
查知識 → ark-wiki-engine（wiki_query）｜交付報告 → ark-md-report（給 AI）/ ark-html-report（給人）
```

> 這 8 個正是 `base_skills`（全員底座）。任何 agent 都能走完這條鏈。

## 🎯 依問題類型選 skill

| 遇到的問題 | 先用的 skill | 屬性 |
|---|---|---|
| 環境跑不起來 / ModuleNotFoundError / venv | `ark-env-doctor` | role: admin/devops |
| code 品質 / PR 審查 / lint / 安全掃描 | `ark-code-review` | role: coder/qa |
| 跑測試 / 覆蓋率 | `ark-test-runner` | role: qa |
| 查資料庫 / BQ 取數 | `ark-db-query` | role: analyst/data-eng |
| 資料清洗轉換 / 匯出檔案(md/csv/json) | `ark-etl-pipeline` | role: analyst/data-eng |
| 建新 skill / 改 skill / 測 skill 效能 | `ark-skill-creator` | role: ai-dev/coder |
| 建/校整庫 skill、metadata 稽核 | `ark-skills-align` | role: admin |
| 做前端介面 / 設計系統 | `ark-frontend-design` | role: designer |
| 互動數據儀表板 | `ark-html-dashboard`；圖表 → `ark-chart-generator` | role: analyst |
| 建新 agent workspace(.kiro 骨架) | `ark-agent-init` | 一次性任務 |
| 建 bot / team daemon 專案骨架 | `ark-agent-bot-builder` / `ark-agent-team-builder` | 一次性任務 |
| 上網查資料 / 大規模抓取 | `ark-web-scraper`；瀏覽器互動/截圖/E2E → `ark-browser-tool` | role: researcher |
| Office 檔(.docx/.xlsx/.pptx/.pdf) | `ark-docx-tool` / `ark-xlsx-tool` / `ark-pptx-tool` / `ark-pdf-tool` | 按需 |
| git log → changelog / 版本說明 | `ark-release-notes` | 按需 |

> 領域專屬 skill（如遊戲 `ark-game-design-doc`、`ark-kpi-calculator`）由各專案在
> `sync_skills.py` 的 MATRIX 依角色補，見 `role-templates-gamedev.md`。

## 串鏈原則

- **簡單問題直接答**，不硬套 skill；需要動手且有現成 skill 才調度。
- **一次性小修**可跳過完整 Loop；**多檔/複雜任務**才走 grill→superpowers→executor→validator 全鏈。
- skill 的產物落 `artifacts/`；報告雙軌：給 AI 看走 md-report、給人看走 html-report。
- 不確定用哪個 → 先 `ark-wiki-engine` 查知識庫，再上網查。
