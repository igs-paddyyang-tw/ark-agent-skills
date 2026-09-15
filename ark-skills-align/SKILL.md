---
name: ark-skills-align
description: |
  ark-agent-skills repo（https://github.com/igs-paddyyang-tw/ark-agent-skills.git）的
  對齊、同步與稽核專用 skill。依 Alignment Directive（對齊指令文件）執行整併：
  合併重複 skill、建 deprecated stub、全庫 frontmatter 回填 schema v1
  （category/outputs/render/depends_on/status）、觸發詞衝突治理、README 分類表同步，
  並以 deterministic 稽核腳本 audit_skills.py 守門（P0/P1 清零才放行）。
  使用此 skill 當使用者要求「對齊 ark-agent-skills」「同步 skill 庫」「稽核 skill 庫」
  「整併 skills」「合併重複 skill」「回填 skill metadata」「檢查觸發詞衝突」
  「執行 skills 整併計畫 / alignment directive」，或任何需要批次修改、驗證、
  重組 ark-agent-skills repo 的場景。單一 skill 的建立/優化不用此 skill（改用 ark-skill-creator）。
metadata:
  author: paddyyang
  schema_version: 1
  category: ops
  outputs:
    - { format: md, audience: ai }
    - { format: data, audience: ai }
  render: none
  depends_on: [ark-md-report]
  status: active
  updated: 2026-09-09
---

# ark-skills-align

ark-agent-skills 庫的**庫級**維運 skill：對齊指令 → 批次執行 → 稽核守門 → drift report。
與 ark-skill-creator 分工：creator 管**單一 skill** 的建立與優化；align 管**整個庫**的一致性。

## 核心原則

1. **指令文件是 source of truth**：所有結構性改動（合併/移除/降級）必須對應 Alignment Directive 的 D-x 編號；文件沒有的決策不執行，先回報
2. **Deterministic 守門**：每個 Phase 結束跑 `scripts/audit_skills.py`，P0/P1 清零才進下一 Phase
3. **Stub 而非刪除**：被合併/移除的 skill 目錄留 README stub（遷移說明 + deprecation 日期 + 6 個月保留期），引用不斷鏈
4. **metadata 與 description 分開改**：schema 回填只加 `metadata` 欄位（零觸發風險）；description 改動獨立 commit 且逐 skill 附 3 個觸發測試 prompt

## 工作流程

### 0. 取得輸入

- Clone/pull repo：`git clone https://github.com/igs-paddyyang-tw/ark-agent-skills.git`（已存在則 `git pull`）
- 找 Alignment Directive：優先讀 repo 內 `docs/alignment/` 最新一份；使用者另有提供則以提供版為準
- 沒有 directive 時：**只跑稽核不做改動**，產出 audit 報告讓使用者決定

### 1. 基線稽核

```bash
python scripts/audit_skills.py --repo <repo> --json baseline-audit.json
```

記下 findings 基線。腳本檢查七項：frontmatter 可解析、name=目錄名（P0）、
category/outputs 齊全且在受控詞彙（P1）、description 重複（相似度>0.90，P1）、
獨占觸發詞衝突（P1）、stub 格式（P2）、README 一致性（P2）。
獨占詞矩陣內建於腳本，可用 `--config audit_config.yml` 擴充（格式見 `references/ops-playbook.md`）。

### 2. 依 Phase 執行 Directive

讀 `references/alignment-workflow.md` 取得每類操作的標準手順：

| 操作 | 手順章節 |
|------|----------|
| 合併 skill（D-1、D-2 類） | §merge：觸發詞移交 → 資產遷移 → stub 化 |
| 移除/降級（D-3、D-4 類） | §demote：內容轉 reference 或 docs/ → stub 化 |
| 收編為 preset（D-5、D-8 類） | §preset：領域內容 → 基底 skill references/<domain>-preset.md |
| schema v1 回填 | §backfill：跑 `scripts/backfill_metadata.py`（半自動 + 人工複核 category） |
| 觸發詞治理 | §triggers：按矩陣改 description，逐 skill 附測試 prompt |
| README 重寫 | §readme：兩層分類表由 frontmatter 生成，不手寫 |

分類歸屬**以各 skill 的 frontmatter 為唯一真相**（決策 C，2026-08-12）——
`references/taxonomy.md` 只定義受控詞彙與 outputs 規格，不再維護歸屬名冊。
要看全庫歸屬快照跑 `scripts/audit_skills.py`。
frontmatter 欄位規格見 `references/metadata-schema.md`。

### 2.5 移除／改名前後：反向掃消費端（強制）

```bash
python scripts/check_consumers.py --name ark-foo   # 動手前：誰在用？
python scripts/check_consumers.py                  # 動手後：還有誰指著已刪的名字？
```

🔴 **上游做移除，就要由上游負責掃消費端。** 消費端各自的 `sync_skills.py --check`
本來就會擋，但它們在別的 repo、甚至別台機器上 —— 「消費端自己會檢查」在多 repo
情境下等於沒有檢查。2026-09-14 併掉兩個 skill 後，3 個矩陣 10 處、9 份 SOUL.md、
12 份已部署複本、1 份蒸餾設定全部靜默指著舊名（sync 印一行「跳過」、蒸餾掃出零筆）。

四個掃描面：角色矩陣（`sync_skills.py` 的 MATRIX/COMMON）· 已部署複本
（`**/.kiro/skills/`）· 人格清單（SOUL.md 條列）· 蒸餾來源（`distill-sources.yaml`）。
專案自建 skill（`LOCAL_ONLY`）不算懸空。**消費端根目錄不存在時明說跳過，不假裝通過。**

### 3. Phase 收尾（強制，不可跳過）

1. `audit_skills.py` P0/P1 = 0，且 `check_consumers.py` 對本次移除的名字回 0 處
2. 產 drift report：ark-md-report `review` 型，存 `docs/reports/review/{date}-align-phase-{X}.md`，
   frontmatter `findings_count` 直接引用 audit JSON
3. 獨立 commit，message 格式：`align(phase-A): D-1 D-2 merge + trigger governance [refs: alignment-directive]`

### 4. 全部完成後

- 對照 Directive 第 6 節成功指標逐條驗證
- 觸發測試：衝突矩陣每組獨占詞出 3 個測試 prompt，確認只觸發 owner（配 ark-skill-creator 的 evals 機制）
- 產最終 alignment report 給使用者（含 before/after skill 數、findings 曲線）

## 邊界宣告：逐案補，不設規則（2026-09-14 定）

`description` 的「不適用於 …請用 ark-X」是**路由用的**：agent 選 skill 時只讀 description。
2026-09-14 盤點時 31/50 沒有邊界宣告，**刻意沒有做成守門規則** ——
多數 skill 根本沒有可混淆的鄰居，強制只會產生填充文字，而填充文字會稀釋真正的邊界。

判準：**指名「會被誤觸的那一個」，指不出來就不要寫。**

補了 23 個，都是有具體鄰居的：

| 群 | 誰會被誤觸 |
|---|---|
| 查資料 | db-query（結構化）／ weknora-cli（口徑問答）／ wiki-engine（本機 wiki） |
| 指標 | kpi-calculator（怎麼算）／ anomaly-detector（算完之後的異常）／ retention-analysis（深入分析）／ marketing（策略，不是分析） |
| 健檢 | dashboard-health（已部署端點）／ env-doctor（開發機環境） |
| 程式碼檢查 | code-review（風格可讀性）／ security-audit（弱點）／ code-spec-validator（對不對得上 spec） |
| 資料管線 | db-query 取數 → etl-pipeline 轉換 → chart-generator 靜態圖／html-dashboard 互動 |
| 產 HTML | frontend-design（產品介面）／ html-report（報告頁）／ html-dashboard（儀錶板） |
| 文件 | superpowers（Spec/ADR）／ doc-coauthoring（一來一往起草）／ game-design-doc（遊戲企劃）／ md-report（分析結論） |
| 「計畫」三義 | project-planning（需求到交付的流程）／ spec-executor（拿到 plan 之後執行）／ planning-with-files（跨 session 不忘記） |

**刻意不加的 8 個**（沒有鄰居會被誤觸，加了是雜訊）：
`ark-cost-tracker` · `ark-docker-deploy` · `ark-translator` · `ark-uml-generator` ·
`ark-mcp-builder` · `ark-pdf-tool` · `ark-pptx-tool`（Office 系以副檔名區分，本身就不會混）
以及 `ark-xlsx-tool`（它其實已經有邊界，只是寫法沒用「請用 ark-」，掃描沒認出來）。

⚠️ 寫的時候會撞到**觸發詞衝突矩陣**：在「不適用於」句裡寫別人的獨占詞
（`派工`、`寫 spec`、`覆蓋率`…）一樣會被 audit 判 P1 —— 那不是誤判，
因為 agent 路由讀的是整段文字，不會分辨那句是正面還是反面。換個說法即可。

## 多 session 同時作業（2026-09-14 實測出來的協定）

那天有**兩個 agent 同時在改這個 repo**，撞出四種代價，每一種都有對應做法：

| 撞到什麼 | 做法 |
|---|---|
| `git add` 後被別人清掉 index，`commit` 變成空的 | **只用 pathspec commit**：`git commit -m ... -- <明確檔案>`（stage+commit 原子完成，不經 index）。禁用 `git add -A` |
| `commit && push` 串接：commit 失敗但 push 照跑，**推上去的是別人的東西** | commit 與 push 分開下，**看 rc**；push 前確認 `rev-list --left-right --count HEAD...origin/main` 的 ahead 只有自己那幾個 |
| 為了排除別人的檔案而 `git reset`，把對方在飛的工作一起清掉 | 要退只退自己的：`git reset -- <自己的檔案>` |
| 主樹有別人的未提交變更、又落後遠端很多，無法 rebase | 用獨立 worktree cherry-pick 後推，主樹全程不動；之後 `git reset --keep origin/main` 對齊 |

🔴 **別靠「機器上只有一個 peer」推論那些 commit 是誰做的** —— commit 的 author
是同一個人類帳號，對辨識 agent 身分沒有資訊量。要認人看它留下的工作面
（報告檔、commit 觸及的目錄），不是看還有誰在線上。當天我就據此認錯了對象。

💡 分工用**檔案面**切，不要用「任務」切：
盤點／移除／整併與消費端同步是一面，`audit_skills.py` 規則與各 skill 的測試是另一面。
兩邊都會動 `SKILL.md`，所以**動到別人那一面的檔案時，只 commit 自己改的那幾個**。

## 邊界

- **不重寫任何 skill 的核心邏輯**：只動 description、frontmatter、reference 結構、stub
- **不動 Office 四工具**（docx/pptx/xlsx/pdf 源自官方，保持可升級性）
- Directive 標 `Phase B 條件執行` 的項目：前置驗證不過 → 記 `status: deferred` 回報，不強行執行
- 單一 skill 的新建與 eval → 交 ark-skill-creator
