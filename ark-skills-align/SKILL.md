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

### 3. Phase 收尾（強制，不可跳過）

1. `audit_skills.py` P0/P1 = 0
2. 產 drift report：ark-md-report `review` 型，存 `docs/reports/review/{date}-align-phase-{X}.md`，
   frontmatter `findings_count` 直接引用 audit JSON
3. 獨立 commit，message 格式：`align(phase-A): D-1 D-2 merge + trigger governance [refs: alignment-directive]`

### 4. 全部完成後

- 對照 Directive 第 6 節成功指標逐條驗證
- 觸發測試：衝突矩陣每組獨占詞出 3 個測試 prompt，確認只觸發 owner（配 ark-skill-creator 的 evals 機制）
- 產最終 alignment report 給使用者（含 before/after skill 數、findings 曲線）

## 邊界

- **不重寫任何 skill 的核心邏輯**：只動 description、frontmatter、reference 結構、stub
- **不動 Office 四工具**（docx/pptx/xlsx/pdf 源自官方，保持可升級性）
- Directive 標 `Phase B 條件執行` 的項目：前置驗證不過 → 記 `status: deferred` 回報，不強行執行
- 單一 skill 的新建與 eval → 交 ark-skill-creator
