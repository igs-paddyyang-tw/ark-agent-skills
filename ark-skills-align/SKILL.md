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
  「執行 skills 整併計畫 / alignment directive」，或消費端「對齊 team 的 skill 版本」
  「升版 skill」「這個 agent 的 skill 是哪一版」，
  或任何需要批次修改、驗證、重組 ark-agent-skills repo 的場景。
  單一 skill 的建立/優化不用此 skill（改用 ark-skill-creator）。
metadata:
  version: "2.0.0"
  author: paddyyang
  schema_version: 1
  category: ops
  outputs:
    - { format: md, audience: ai }
    - { format: data, audience: ai }
  render: none
  depends_on: [ark-md-report]
  status: active
  updated: 2026-09-17
---

# ark-skills-align

ark-agent-skills 庫的維運 skill，兩個模式。與 ark-skill-creator 分工:creator 管**單一 skill**，align 管**整個庫**。

> 敘事、踩坑與判準（不進排程/三段判準/邊界宣告/多 session 協定/版本對齊判準）見
> `references/ops-playbook.md` 與 `references/judgment-checklist.md`;通用判準在根 `AGENTS.md`。
> 標準手順見 `references/alignment-workflow.md`;frontmatter 規格見 `references/metadata-schema.md`;
> 消費端契約（matrix/lock schema）見 `references/consumer-contract.md`。

## 模式一:upstream（維護者/CI，在 repo 根執行）

管**庫的一致性 + 版本基底**。

```bash
# 稽核（P0/P1 清零才放行；穩定規則 ID AL-xxx）
python ark-skills-align/scripts/audit_skills.py --repo . --json baseline.json
# 版本回填 semver + depends_on 物件化
python ark-skills-align/scripts/backfill_metadata.py --repo . --versions
# 產 release manifest + index（audit 全綠才打 tag）
python ark-skills-align/scripts/gen_manifest.py --repo . --release skills-YYYY.MM-rN
# 移除/改名前後反向掃消費端
python ark-skills-align/scripts/check_consumers.py --name ark-foo
```

守門規則（`AL-xxx` 穩定 ID，exit 0/1/2）:既有 AL-001~024（frontmatter/category/觸發詞/
stub/orphan/懸空…）+ 版本系列 AL-101（version 非 semver，過渡 P2）/AL-104（depends_on 無範圍）/
AL-107（消費端型缺 tested_against）。改動走 Alignment Directive 的 D-x，文件沒有的決策不執行。

## 模式二:consumer（team 的 manager 總機 `<專案>-agent`，在 team repo 根執行）

管**這個 team 手上 skill 的版本對齊**。資料在 `skills-matrix.yaml`（git）、狀態在
`.kiro/skills.lock.json`（本機不進 git，每機一份）。

```bash
python .kiro/skills/ark-skills-align/scripts/align_sync.py plan --waves      # 列差異，不改檔
python .kiro/skills/ark-skills-align/scripts/align_sync.py apply --wave 1 --yes  # 私訊 manager 確認才升（C-5）
python .kiro/skills/ark-skills-align/scripts/align_sync.py verify             # AL-203 drift/AL-301 base tier
python .kiro/skills/ark-skills-align/scripts/align_sync.py verify --remote    # 對上游 manifest，出 lag/breaking
python .kiro/skills/ark-skills-align/scripts/align_sync.py heartbeat          # 送 team 頻道（同版只寫 health）
python .kiro/skills/ark-skills-align/scripts/align_sync.py resolve <path>     # 這個複本是哪版？
```

對齊單位是 **release train**（`skills-YYYY.MM-rN`），個別 skill 只能例外 pin（附 reason）。
tier 策略:base 全隊同版（Loop 五件套，major 不一致 P0）· role 走範圍 · domain（local_only）自由。
升級走波次:wave 1 manager → wave 2 leaders → wave 3 workers，每波 verify P0/P1=0 才下一波。

## 版本感知（套件實例，排程呼叫）

套件（ark_team_agent/ark_bot_agent）預設段掛排程，每日 `verify --remote` + `heartbeat`:
拉上游 manifest 反查本機版本 → 寫 lock → 一行 heartbeat 送 team 頻道 + `/api/health`。
上游 `pre-push` 只在 major/契約變更時廣播 Alignment Notice（`notice_build.py`）。
> 🔴 套件預設段/scheduler/api-health 在 paddy 開發源（交接項），本 skill 只提供 align_sync 腳本。

## 收尾（強制）

1. audit P0/P1=0 + check_consumers 對本次移除的名字回 0
2. drift/verify report:ark-md-report review 型，存 `docs/reports/review/{date}-align-*.md`
3. 獨立 commit（pathspec，不 `git add -A`），message 帶 `[refs: alignment-directive]` 或 D-x

## 邊界

- 不重寫任何 skill 核心邏輯;只動 description/frontmatter/reference/stub/版本
- 不動 Office 四工具（保持官方可升級）
- 單一 skill 建立/eval → ark-skill-creator
