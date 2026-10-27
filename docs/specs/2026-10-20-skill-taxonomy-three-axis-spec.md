---
title: Skill 分類三軸化（category × form × domain）規格
type: spec
status: accepted
created: 2026-10-20
author: paddyyang
schema_version_target: "1.2"
---

# Skill 分類三軸化規格

## 1. 問題

`metadata.category` 一個欄位塞了三種互相獨立的維度：

| 混入的維度 | category 值 | 本來該回答的問題 |
|---|---|---|
| 職能（產出物） | process / scaffolder / pipeline / view / document / ops | 這個 skill **產出什麼** |
| 形態（手段） | `executor` | agent **怎麼用它**（跑腳本 vs 照指示做） |
| 領域 | `domain` | 這個 skill **屬於哪個業務** |

後果（2026-10-20 盤點，61 個 active）：

- **違反自己的判準**：`references/taxonomy.md` 明定「判準是**產出物**而非**手段**」，`executor` 正是手段
- 5 個 game-* 是遊戲領域，卻歸 `executor`；`domain` 只剩 2 個，領域資訊實際上丟失
- `pipeline` 16 個裡 13 個沒有腳本（產碼食譜），另有 community-cli（9 支腳本）、weknora-cli（ops，6 支）其實是直接執行型 —— 「怎麼用」這件事無處可標
- 受控詞彙有 **4 份複本**（`audit_skills.py`、`gen_readme.py`、`prompt_lint.py`、`backfill_metadata.py`），規格文件有 **3 份**且互相矛盾（兩份 category 清單沒有 `executor`；三份都沒定義 `schema_version: "1.1"`、`status: experimental`）
- `schema_version: "1.1"` 只有 executor 在用，但同為 executor 的 github-cli 是 `"1"` —— 版號沒有可執行的規則

## 2. 決策

拆成三個正交欄位，**產出格式沿用既有的 `outputs`**（不新增第四軸）：

| 欄位 | 回答 | 受控詞彙 |
|---|---|---|
| `category` | 產出什麼（職能） | `process` `scaffolder` `pipeline` `view` `document` `ops` |
| `form`（新） | agent 怎麼用 | `executor` `instruction` |
| `domain`（新） | 屬於哪個業務 | `general` `game` |

### 2.1 form 判準

- `executor`：**主要產出由 skill 自帶的 `scripts/` 決定性產生**，agent 以 bash 呼叫、讀 stdout 契約
- `instruction`：主要產出由 LLM 依 SKILL.md 指示產生；即使附有腳本，也只是守門、渲染或輔助（例：md-report 的 lint、html-report 的戳記、release-notes 的骨架）

> 只看「主要產出誰做的」，不看有沒有 `scripts/` 目錄、也不看呼叫次數。

### 2.2 domain 判準

- `game`：內容綁遊戲業務（遊戲製程、玩家、遊戲行銷、遊戲 QA）
- `general`：換成非遊戲專案照樣能用
- 詞彙刻意只有兩個；出現第三個業務且有 ≥ 2 個 skill 時才擴充（擴充要同步 §4 的唯一詞彙來源）

### 2.3 category 收斂

`executor`、`domain` 不再是合法 category。舊值依產出物重新歸類（§3），**不設自動別名**（同一個舊值對應多個新值，需人判）。

## 3. 歸類結果

### 3.1 category 變動（12 個）

| skill | 舊 | 新 | 理由（產出物） |
|---|---|---|---|
| ark-db-query | executor | pipeline | 查詢結果資料 |
| ark-wiki-engine | executor | pipeline | 檢索結果與 wiki 頁 |
| ark-grafana-query | executor | ops | 監控資料 |
| ark-github-cli | executor | ops | git 收尾、平台文件同步 |
| ark-mobile-adb | executor | ops | 裝置操作、QA 驗證報告 |
| ark-game-spec | executor | document | 遊戲規格書 |
| ark-game-prob | executor | document | 機率規格書 |
| ark-game-report | executor | document | 上線成效報告 |
| ark-game-proto | executor | view | 可玩 H5 雛型（給人看） |
| ark-game-quicktest | executor | process | 三向驗證 verdict |
| ark-marketing | domain | document | 行銷策略文件 |
| ark-retention-analysis | domain | document | 留存分析報告 |

### 3.2 form: executor（17 個，其餘 44 個為 instruction）

community-cli、db-query、env-doctor、game-prob、game-proto、game-quicktest、game-report、game-spec、github-cli、grafana-query、mobile-adb、prompt-spec-validator、skills-align、spec-executor、telegram-sender、weknora-cli、wiki-engine

### 3.3 domain: game（9 個，其餘 52 個為 general）

community-cli（日本社群玩家回饋）、game-prob、game-proto、game-quicktest、game-report、game-spec、marketing（遊戲行銷）、mobile-adb（遊戲 AI QA）、retention-analysis（玩家留存）

> retention-analysis 與 kpi-calculator 的界線：kpi-calculator 同時涵蓋通用指標 → `general`。

## 4. 唯一詞彙來源

- 受控詞彙的**程式權威**：`ark-skills-align/scripts/audit_skills.py`（`CATEGORY_CODES`、`FORM_CODES`、`DOMAIN_CODES`）
- `gen_readme.py`、`prompt_lint.py` 各自的複本保留（三支腳本互不 import，跨 skill import 會破壞可單獨同步），但**必須與 audit 一致**；新增一致性測試守住
- **文件權威**：`ark-skills-align/references/metadata-schema.md`（欄位）＋ `references/taxonomy.md`（詞彙與判準）。`docs/skill-metadata-schema.md` 改為指路頁

## 5. schema_version

| 值 | 意義 |
|---|---|
| `"1"` | 初版欄位（無 version 規範） |
| `"1.1"` | 受控詞彙全名化＋ executor 分類（2026-09-04；**已廢止的 category 用法**） |
| `"1.2"` | 三軸：`form`、`domain` 必填，category 不含 executor／domain |

全庫一次升到 `"1.2"`。audit 規則：

| 狀況 | 嚴重度 |
|---|---|
| schema `"1.2"` 缺 `form` 或 `domain` | P1 |
| `form`／`domain` 值不在詞彙內 | P1 |
| schema `"1"`／`"1.1"` 缺 `form`／`domain` | P3（舊複本過渡期容忍） |
| category 為 `executor`／`domain` | P2 `category-axis-mixed`（提示改用 form／domain；舊複本過渡期不擋） |

## 6. 版號

所有 61 個 SKILL.md 的 metadata 都會變 → tree_hash 變 → **全部升 patch**（依「hash 變就要升版」規則，避免 index 出現同版號兩個 hash）。工具有行為變更的另外升：

- ark-skills-align：audit、gen_manifest 規則變更 → minor
- ark-prompt-spec-validator：PL-010 詞彙變更 → minor

## 7. 驗收

- [x] audit：P0／P1 = 0，`category-axis-mixed` = 0（P2=41 皆既有：depends_on 無範圍 38、tested_against 2、孤兒 asset 1）
- [x] 61 個 SKILL.md 皆有 `form`、`domain`，schema `"1.2"`（executor 17／instruction 44；game 9／general 52）
- [x] 四份詞彙複本一致（`scripts/tests/test_taxonomy_vocab.py`）
- [x] `gen_readme --check` 綠；README 每列顯示 form／domain
- [ ] 全庫測試：僅 origin 既有的 `ark-game-report/gr_run.py --help` 失敗
- [x] manifest 重產 `skills-2026.10-r3`，SKILL.md ↔ manifest 0 不一致

## 8. 不在範圍

- `ark_team_agent.site_exporter` 讀 `metadata.category` 只做展示，新值仍是合法字串，不需改套件
- 消費端舊複本：不強制，下次 `mirror_sync` 自然對齊；audit 對舊 schema 降級容忍
