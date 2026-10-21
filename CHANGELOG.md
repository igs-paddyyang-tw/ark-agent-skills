# ark-agent-skills Changelog

> 各專案同步 skills 時參考此檔案。格式：日期 + 動作 + 影響範圍。

---

## 2026-10-21 (ark-game-report 0.2.6：並行測試改量重疊)

- `test_query_parallel_export` 不再比總耗時（Windows 起 Python 慢時 28 秒 > 門檻 23.4 秒，但並行其實有效）；改由假 bq_export 每支寫一個起訖時間檔，驗 workers 4 時同時在跑 ≥ 3 支
- 多程序同寫一個 log 檔在 Windows 會併行掉行 → 每支一檔

---

## 2026-10-21 (佈局契約 v3.5 補充：1 MB 額度不計 html)

- ark-game-spec 2.6.1：`data_total_kb` 1 MB 額度不含 `game/`、`review/` 與 `*.html` View 軌（使用者決議，比照 `single_file_kb` 排除 html）
- ark-game-prob 1.4.8：`ps_layout` L-SIZE 新增定版家總量檢查（依上述口徑，超過 → warning），`facts.size` 多 `data_kb`／`data_limit_kb`；測試 `test_layout_data_budget_excludes_html`
- 實測 HuffNPuff：含 html 1,242 KB → 依新口徑 633 KB

---

## 2026-10-20 (佈局契約 v3.5：拍板包不與各階段產出重疊)

規格：aidev `docs/specs/2026-10-20-review-pack-dedup-spec.md`；分析：`docs/reports/review/2026-10-20-huffnpuff-review-overlap-analysis.md`。

### ark-game-proto 1.3.0（review_build）
- `publish_docs`：定版家 md 旁產同名 html（`content-src` 戳記、冪等、不覆寫他工具的成對 html）
- `clean_review`：白名單外舊檔清掉（1.2.4 起複製進來的 docs/、prob-spec.html、proto.html 與孤兒檔）
- 成品改 `../<stage>/…` 相對連結，不複製；清冊多 `links`、來源改相對 repo 路徑；結案報告不進送審包
- `--export <資料夾>` 產可帶走的完整包（拒寫 data/）；輸出 `broken_links` 檢查人工章節寫死的舊路徑

### ark-game-prob 1.4.7（ps_layout）
- L-STAMP 掃描擴到 analysis/report、spec、quicktest/qt-report、game；L-REVIEW 同時驗清冊 `links`

### ark-game-spec 2.6.0（佈局契約 v3.5）
- review/ 只放拍板書、checks/、定版家放不下的自足單檔；spec／game 允許 md 旁的 html

### ark-superpowers 1.0.3（doc_lint）
- 🔴 修：SP-001 把 frontmatter（`type: spec`、`language: zh-TW`）、章節標題、表格標題列／分隔列、粗體標籤行當成模板殘留 → **每份文件都 P0**。結構行改為豁免
- SP-002：行內 code 裡的 `{slug}` 等字面路徑不算 placeholder；測試子程序加 `-X utf8`（Windows cp950）

### 結果
HuffNPuff 拍板包 5,004 KB → 4,433 KB、與定版家重複 0、斷連結 0；ps_layout L-STAMP／L-REVIEW 0 error

## 2026-10-20 (depends_on 帶版本範圍 + AL-105／依賴環守門)

### 資料（20 個 skill、38 條依賴）
- `depends_on` 全部由字串改為 `{ name, version }`：範圍預設 `^<上游主版號>.0.0`；文件寫明最低版本的兩條用該版本
  （game-proto → game-prob `^1.4.0`、game-spec → html-report `^1.2.0`）
- **拆 ark-game-prob ⇄ ark-game-quicktest 依賴環**：game-prob 只讀 quicktest 的產出檔（qt 模式的 rtp-report），
  不呼叫其程式 → 移除 prob → quicktest；quicktest → prob（`--probspec` 呼叫 `ps_run.py`）保留
- 版號：上述 20 個升 patch；ark-skills-align 2.4.0（守門規則）

### 守門（audit_skills.py）
- 🔴 修：斷鏈檢查與反向依賴原本用 `str(ref)` 取名稱 —— 物件格式會變成 `"{'name': ...}"` 而**靜默跳過**。改用 `dep_name()`
- 補實作 **AL-105**（P0，v2 規格 AC-07 只登記代號）：上游現行版本不滿足範圍
- 新增 AL-030 依賴環（P1）、AL-031 範圍無法解析（P1）—— `semver.satisfies()` 對亂寫的範圍只回 False，不先驗語法會誤報成 P0
- 新增 `scripts/tests/test_depends_on.py`（8 項：含物件格式斷鏈回歸、P0／P1 分流、環偵測、全庫可滿足且無環）

### 結果
audit P2 41 → **3**（剩 tested_against 2、孤兒 asset 1）；manifest `skills-2026.10-r4`

---

## 2026-10-20 (分類三軸化：category × form × domain，schema 1.2)

規格：`docs/specs/2026-10-20-skill-taxonomy-three-axis-spec.md`。
1.1 把「形態」（`executor`）與「領域」（`domain`）塞進 `category`，違反 taxonomy.md 自己的
「判準是產出物而非手段」；受控詞彙 4 份複本、規格文件 3 份互相矛盾。

### 欄位（全庫 61 個 SKILL.md）
- 新增 `form`（executor 17／instruction 44）、`domain`（game 9／general 52）；`schema_version` 全部升 `"1.2"`
- `category` 移除 `executor`、`domain`，12 個依產出物重歸類：db-query／wiki-engine → pipeline；
  grafana-query／github-cli／mobile-adb → ops；game-spec／game-prob／game-report／marketing／retention-analysis → document；
  game-proto → view；game-quicktest → process
- 版號：metadata 變動 → 全部升 patch；ark-skills-align 2.3.0、ark-prompt-spec-validator 1.1.0（守門規則變更）

### 守門
- `audit_skills.py`：`FORM_CODES`／`DOMAIN_CODES`；1.2 缺 form／domain → P1，舊 schema → P3；
  category 為 executor／domain → P2 `category-axis-mixed`（AL-025~029）；舊別名 `sop` 改指 `document`（原指向已移除的 domain）
- `prompt_lint.py` PL-010、`quick_validate.py`、`backfill_metadata.py` 同步新詞彙
- 新增 `scripts/tests/test_taxonomy_vocab.py`：四份詞彙複本一致、全庫三軸齊全、舊別名不懸空

### 文件
- `references/metadata-schema.md` 為欄位唯一權威（補 schema_version 表、版號規則、status: experimental、upstream 等實際在用的欄位）
- `references/taxonomy.md` 補 form／domain 判準；`docs/skill-metadata-schema.md` 改指路頁
- README 每列顯示形態／領域；manifest 重產 `skills-2026.10-r3`

---

## 2026-10-20 (版號治理：manifest 自我參照、漏升版、列車 r2)

起點是全庫盤點：manifest 落後 SKILL.md 4 個 skill、9 個 skill 升版後仍有修改未升版、
本檔停在 09-04（一個半月未登錄）。

### 守門
- `gen_manifest.py`／`align_sync.py`：tree_hash **排除頂層 `release/`**（`HASH_EXCLUDE_DIRS`）——
  manifest 放在 `ark-skills-align/release/`，原本每次重產都讓 ark-skills-align 自己的 tree_hash 變動卻沒升版（自我參照）。兩支腳本同規則，已驗證 hash 一致、改 release/ 不影響 hash

### 補升版（升版後仍有修改的 9 個）
| skill | 版本 | 原因 |
|---|---|---|
| ark-agent-team-builder | 3.0.0 → **3.1.0** | validate_team 新檢查（a99036e）+ tested_against |
| ark-agent-team-design | 1.1.0 → **1.2.0** | gen_team 新功能（a99036e）+ r2 對齊 |
| ark-agent-role-profile | 1.3.0 → 1.3.1 | 改引用的 skill 舊名 |
| ark-superpowers | 1.0.0 → 1.0.1 | 改引用的 skill 舊名 |
| ark-prompt-spec-validator | 1.0.0 → 1.0.1 | ignore 指令被 HTML 註解尾吃掉（7e0c72c） |
| ark-agent-bot-builder | 3.1.0 → 3.1.1 | tested_against |
| ark-db-query | 3.0.0 → 3.0.1 | tested_against；category 行內註解移到獨立行（逐行解析的工具會誤讀） |
| ark-github-cli | 0.2.0 → 0.2.1 | 測試檔改唯一檔名 |
| ark-skills-align | 2.2.0 → 2.2.1 | 本次 tree_hash 修正 |

### 資料
- manifest 重產為 **`skills-2026.10-r2`**（60 個 active；experimental 的 ark-game-report 依規則不收），SKILL.md ↔ manifest 版本 0 不一致
- README 重產（`gen_readme --check` 原為紅）

### 已知未修
- `scripts/tests/test_cli_contract.py`：`ark-game-report/gr_run.py --help` 回 2（origin 既有，非本次引入）
- audit P2=41（38 個 depends_on 無版本範圍、2 個缺 tested_against、1 個孤兒 asset）
- category 混用三軸（形態／產出／領域）—— 另案出規格

### 09-05 ~ 10-20 未登錄期間的版本快照
> 本檔 09-04 後未更新；以下為各 skill 現行版本與最後一次修改，作為補登基準（逐筆沿革見 git log）。

| skill | 現行版本 | status | 09-05 後 commit 數 | 最後一次 |
|---|---|---|---:|---|
| `ark-agent-bot-builder` | 3.1.1 | active | 8 | 2026-09-18 `652f21a` feat(metadata): 補 3 個消費端型 skill 的 tested_against + 定義該欄位形狀 |
| `ark-agent-cli` | 1.0.0 | active | 4 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-agent-init` | 2.3.1 | active | 41 | 2026-10-19 `468b6d2` fix(ark-agent-init): 2.3.1 bot 根 skills/ 是 BaseSkill 插件包慣例，分 |
| `ark-agent-role-profile` | 1.3.1 | active | 10 | 2026-10-07 `2a5de92` feat(ark-game-spec): v2.0.0 五合一整併（遊戲製程 skill 7→3 Phase B） |
| `ark-agent-team-builder` | 3.1.0 | active | 24 | 2026-09-18 `652f21a` feat(metadata): 補 3 個消費端型 skill 的 tested_against + 定義該欄位形狀 |
| `ark-agent-team-design` | 1.2.0 | active | 6 | 2026-09-30 `23fd7ca` chore(ark-skills-align): 全庫版號對齊 release train r2 + 修 gen_man |
| `ark-anomaly-detector` | 1.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-book` | 1.1.0 | active | 2 | 2026-10-19 `6d4bcc5` feat(review): 拍板包導覽修正＋三隻小豬繪本風格（ark-game-proto 1.2.4、ark-book |
| `ark-browser-tool` | 3.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-chart-generator` | 1.0.0 | active | 3 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-code-review` | 1.0.0 | active | 4 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-code-spec-validator` | 1.0.0 | active | 6 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-community-cli` | 1.1.2 | active | 5 | 2026-09-29 `0abf4ee` fix(ark-community-cli): digest 跨窗 cluster_rep 加 default 回退，修 |
| `ark-cost-tracker` | 1.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-daily-news` | 2.1.0 | active | 3 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-dashboard-health` | 1.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-data-contract` | 1.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-db-query` | 3.0.1 | active | 10 | 2026-09-18 `652f21a` feat(metadata): 補 3 個消費端型 skill 的 tested_against + 定義該欄位形狀 |
| `ark-doc-coauthoring` | 1.0.0 | active | 3 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-docker-deploy` | 1.0.0 | active | 1 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-docx-tool` | 1.0.0 | active | 4 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-env-doctor` | 1.0.0 | active | 3 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-etl-pipeline` | 1.0.0 | active | 5 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-frontend-design` | 1.0.0 | active | 5 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-game-prob` | 1.4.4 | active | 18 | 2026-10-19 `5c6c3e6` feat(game-pipeline): 拍板書——review/ 導覽頁改用 ark-book 架構 |
| `ark-game-proto` | 1.2.5 | active | 10 | 2026-10-20 `a990c3e` feat(game-pipeline): 佈局契約 v3.4 十階段（ark-game-spec 2.5.5、ark-g |
| `ark-game-quicktest` | 2.1.2 | active | 8 | 2026-10-13 `be318fe` feat(ark-game-*): G-1 gs_run --stage publish + G-2 ARK_GAME_ |
| `ark-game-report` | 0.2.2 | experimental | 3 | 2026-10-20 `4bdd2b6` feat(ark-game-report): 0.2.2——預設快速版（只撈本機，D+7 初判）＋同期分析快取 |
| `ark-game-spec` | 2.5.5 | active | 15 | 2026-10-20 `a990c3e` feat(game-pipeline): 佈局契約 v3.4 十階段（ark-game-spec 2.5.5、ark-g |
| `ark-github-cli` | 0.2.1 | active | 2 | 2026-10-08 `81f4e5d` fix: gdd_export 擋路徑越界檔名 + 測試檔重名改唯一檔名 |
| `ark-grafana-query` | 1.0.0 | active | 1 | 2026-09-17 `7d2ff1b` feat: add ark-grafana-query skill (executor 型 Grafana 監控查詢) |
| `ark-grill-me` | 1.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-html-dashboard` | 1.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-html-report` | 1.3.0 | active | 6 | 2026-10-15 `0067f75` feat: 消費端本地修改回貢 + mirror_sync --accept-upstream |
| `ark-kpi-calculator` | 1.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-llm-tools` | 1.0.0 | active | 3 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-marketing` | 1.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-mcp-builder` | 1.0.0 | active | 6 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-md-report` | 1.0.0 | active | 6 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-mobile-adb` | 2.4.0 | active | 11 | 2026-10-15 `dba7acb` feat(ark-mobile-adb): 2.3.0 → 2.4.0 gamepack 校準資料解耦（--pack-d |
| `ark-pdf-tool` | 1.0.0 | active | 5 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-planning-with-files` | 1.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-pptx-tool` | 1.0.0 | active | 5 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-project-planning` | 2.0.0 | active | 3 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-prompt-spec-validator` | 1.0.1 | active | 9 | 2026-10-12 `7e0c72c` fix(prompt-spec-validator): ignore 指令被 HTML 註解尾 -- 吃掉導致失效 |
| `ark-release-notes` | 1.0.0 | active | 3 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-retention-analysis` | 1.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-security-audit` | 1.0.0 | active | 3 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-skill-creator` | 2.0.0 | active | 7 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-skills-align` | 2.2.1 | active | 53 | 2026-10-19 `468b6d2` fix(ark-agent-init): 2.3.1 bot 根 skills/ 是 BaseSkill 插件包慣例，分 |
| `ark-spec-executor` | 2.0.1 | active | 6 | 2026-10-16 `ae62318` feat(ark-game-spec): 2.4.0 to 2.5.0 slot-game pack 1.1 + 遊戲產 |
| `ark-superpowers` | 1.0.1 | active | 12 | 2026-10-07 `2a5de92` feat(ark-game-spec): v2.0.0 五合一整併（遊戲製程 skill 7→3 Phase B） |
| `ark-telegram-sender` | 2.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-test-runner` | 1.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-translator` | 1.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-uml-generator` | 1.0.0 | active | 2 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-web-scraper` | 1.0.0 | active | 4 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-webapp-generator` | 2.0.0 | active | 6 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |
| `ark-weknora-cli` | 1.0.1 | active | 8 | 2026-10-15 `0067f75` feat: 消費端本地修改回貢 + mirror_sync --accept-upstream |
| `ark-wiki-engine` | 3.0.1 | active | 22 | 2026-10-15 `4c4eb72` fix(ark-wiki-engine): ingest 沿用 raw frontmatter 的 title / re |
| `ark-xlsx-tool` | 1.0.0 | active | 4 | 2026-09-17 `8c2811b` feat(skills-align): W0 版本基底 — 52 skill semver 回填 + release m |

---

## 2026-09-04 (executor 分類補登記 + 兩道守門對齊)

起點是一次全庫盤點：`audit_skills.py --repo .` 回 **P1=1 / P2=3，四條全在
`ark-db-query`** —— 08-19 的 v2 executor 化改造引入了新 category 與
`schema_version: "1.1"`，但守門與規格文件都沒跟著改。

### 守門
- `audit_skills.py`：`CATEGORY_CODES` 加 `executor`；`schema_version` 檢查抽成
  `SCHEMA_VERSIONS = {"1", "1.1"}` 並改**字串比對** ——
  原本 `!= 1` 對 YAML 讀成 str 的 `"1.1"` 恆為真
- `gen_readme.py`：`SECTIONS` 登記 `executor`（不登記 db-query 會落到「⚠️ 未分類」）；
  **移除 ⑤ `presentation-content` 並重編號** —— 該值在 `audit_skills.py` 已是
  legacy 別名（P3 → `document`），這裡卻當現行分類展示且恆印「（目前無）」

### 資料
- `ark-db-query`：`outputs` 的 `json` / `jsonl/csv` → 單一 `{format: data, audience: ai}`
  （沿用既有詞彙，不放寬守門。全庫實際只用 md 44 / code 9 / html 8 / data 3）

### 文件（三處分岔，不修就會留下新的）
- `docs/skill-metadata-schema.md`：`outputs.format` 原列 `xlsx|pptx|docx` 且**缺 `data`**，
  與守門的 `OUTPUT_FORMATS` 不同 —— 照文件設會被 P2 擋下
- `README.md` 分類規格表：`processess`、`viewation-content` 兩處全域替換誤傷
- `README.md` 統計行：手寫的「60 active + 3 stubs = 63」已過期（實際 stubs=0）

### 驗收
`gen_readme.py --check` ✅（原本是紅的，stale 到 08-19 之前，db-query 定位還是 v1 描述）·
`audit_skills.py` **P0/P1/P2/P3 全 0**（rc=0）·
反證：把 `executor` 移出詞彙、`SCHEMA_VERSIONS` 縮回 `{"1"}` → 立刻回 P1×1 + P2×1

---

## 2026-08-12 (ark-skills-align W2~W5)

### 治理（W2 — schema 回填 + 觸發詞）
- 全庫 60 個 active SKILL.md 回填 `schema_version: 1` + `status: active`
- 4 個 deprecated stubs 正確跳過
- `ark-news-daily` 加 negative trigger（不適用於網頁抓取）
- `ark-grill-me` 加 negative trigger（不適用於產 spec/design/plan）
- `ark-llm-cli` / `ark-llm-tools` 加互斥邊界聲明

### 治理（W3 — 呈現引擎收編 + README 重建）
- `ark-html-report` 確認 schema_version: 1 + status: active ✅
- `ark-md-report` 確認 schema_version: 1 + status: active ✅
- `ark-news-daily` 加 `depends_on: [ark-html-report]` ✅
- `ark-html-dashboard` 對齊共享 token 系統 ✅
- `docs/report-frontmatter-standard.md` 已建立 ✅
- README.md 完整重建（60 active + 7 deprecated 分類表）

### 治理（W4 — 條件執行 D-6~D-8）
- D-6: `ark-report-template` 確認為 deprecated stub ✅
- D-7: `ark-file-export` **保留**（有獨立價值：pipeline 最後一哩寫入）+ 加邊界聲明
- D-8: `ark-cost-tracker` **保留**（有獨立資料管線：data/costs/{date}.json）

### 統計（W5）
- Active：**60**（process 9 / scaffolder 9 / pipeline 20 / view 6 / content 1 / document 8 / domain 4 / ops 3）
- Deprecated：**7**（4 有 SKILL.md + 3 stub）
- 目錄總數：**67**（+ scripts/ = 68 個子目錄）

---

## 2026-08-12 (原始變更)

### 新增
- `ark-md-report` — Content 軌報告引擎（5 類型 × frontmatter 契約 × AI 寫作規則）
  - `scripts/report_lint.py` — 契約守門驗證（275 行）
  - `scripts/report_pair.py` — MD↔HTML 漂移檢查（119 行）
  - `scripts/report_register.py` — 索引 + 日報 log（112 行）
  - `references/agent-operating-guide.md` — 三件套運作契約
- `ark-html-report` — View 軌呈現引擎（5 風格 token × 17 元件 × Chart.js）
- `ark-api-doc-sync` — FastAPI route → docs API 表格自動同步
- `ark-eval-runner` — LLM 輸出回歸評測
- `ark-ingest-guard` — 知識入庫 prompt injection 消毒
- `ark-data-contract` — 管線元件間 schema 契約驗證
- `ark-release-notes` — git log → 結構化 changelog

### 移除（deprecated stub 保留 6 個月）
- `ark-report-template` → 被 `ark-md-report` + `ark-html-report` 取代
- `ark-postmortem` → 併入 `ark-md-report` type: incident
- `ark-ai-bot-builder` → 與 `ark-agent-builder` 完全重複
- `ark-daily-decision-digest` → 廢棄
- `ark-policy-translate` → 廢棄

### 修正
- `ark-wiki-engine` — 全面優化（受控詞彙表 + ingest guard + trust 欄位 + 雙模式路由 + 三件套銜接）
- `ark-code-spec-validator` — 四段工作流鏈優化（17 任務）
  - 評分公式定義 + 比例制 + drift 加權
  - AC-ID 約定 + loop-rules.md + 方向分流
  - pipeline 狀態檔 schema
  - evals.json
- `ark-superpowers` — 15 任務優化
  - plan 模板改 executor 相容 7 欄格式
  - checker one-pager 支援 + 空白章節攔截
  - build_docs.py --slug + upgrade 指令
  - ADR 單一來源 + hooks + parity check + evals
- `ark-html-dashboard` — theme: auto/dark/light
- `ark-data-dashboard` — theme: auto + depends_on html-dashboard
- `ark-webapp-generator` — theme: auto

### 治理
- 全庫 57 個 SKILL.md 回填 `category` / `outputs` frontmatter
- 5 組觸發詞衝突加 negative trigger 聲明
- `docs/skill-metadata-schema.md` — frontmatter 擴充規格
- `docs/report-frontmatter-standard.md` — 報告類 MD 標準
- `docs/trigger-matrix.md` — 衝突解法對照表

---

## 2026-08-05~07

### 新增
- `ark-grill-me` — 實作前拷問設計（加入預設 skills）
- `ark-spec-executor` — 執行 plan.md 任務清單（加入預設 skills）

### 修正
- `ark-wiki-engine` — 全面優化（受控詞彙表 + ingest guard + trust 欄位 + 雙模式路由 + 三件套銜接）
- `ark-wiki-engine` — 本地化 7 scripts（ingest/query/lint/graph/index/build/validate）

---

## 同步指南

```bash
# 從 kiro-cli 根目錄同步到子專案
cp -r ~/kiro-cli/.kiro/skills/ark-{skill-name} your-project/.kiro/skills/

# 批量同步核心 6 skills 到所有 agent
for agent in agents/*/; do
  for skill in ark-grill-me ark-superpowers ark-spec-executor ark-code-spec-validator ark-skill-creator ark-wiki-engine; do
    rm -rf "$agent/.kiro/skills/$skill"
    cp -r ~/kiro-cli/.kiro/skills/$skill "$agent/.kiro/skills/"
  done
done

# 同步報告雙軌
cp -r ~/kiro-cli/.kiro/skills/ark-md-report your-project/.kiro/skills/
cp -r ~/kiro-cli/.kiro/skills/ark-html-report your-project/.kiro/skills/
```

### 移除已廢棄 skills

```bash
rm -rf agents/*/.kiro/skills/ark-daily-decision-digest
rm -rf agents/*/.kiro/skills/ark-policy-translate
```
