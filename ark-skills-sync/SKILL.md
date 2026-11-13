---
name: ark-skills-sync
description: |
  ark-agent-skills（https://github.com/igs-paddyyang-tw/ark-agent-skills.git）的 skills 生命週期技能：
  專案（消費端）安裝、更新、健檢、移除自己需要的 skills，回貢修改到上游，以及上游的稽核、整併、發列車。
  規範：每個專案只裝自己需要的 skill，以實體複本進自己的 git；更新來源是本機上游 clone 或 GitHub，
  一律用 scripts/skills_sync.py（status／plan／update／install／remove／doctor／residue）。
  使用此 skill 當使用者或 agent 提及「更新 skill」「安裝 skill」「skill 有沒有新版」「skills 落後」
  「對齊上游」「同步 skill 庫」「清殘留」「移除舊 skill」「接手者」「skill 空殼」「skills doctor」
  「啟動檢查 skills」「這個 agent 的 skill 是哪一版」「回貢上游」「改 skill 推上游」「發列車」「release train」
  「稽核 skill 庫」「整併 skills」「合併重複 skill」「回填 skill metadata」「檢查觸發詞衝突」
  「alignment directive」「對齊 ark-agent-skills」「對齊 team 的 skill 版本」「升版 skill」，
  單一 skill 的建立／優化不用此 skill（改用 ark-skill-creator）。
metadata:
  version: "3.0.0"
  author: paddyyang
  schema_version: "1.2"
  category: ops
  form: executor
  domain: general
  outputs:
    - { format: md, audience: ai }
    - { format: data, audience: ai }
  render: none
  depends_on:
    - { name: ark-md-report, version: "^1.0.0" }
  status: active
  updated: 2026-11-13
---

# ark-skills-sync

skills 的整個生命週期都在這裡：**專案端**怎麼裝、怎麼更新、怎麼檢查，**上游**怎麼收修改、怎麼發版。
2026-11-13 由 `ark-skills-align`（上游維護工具）整併而來，舊名保留為轉址 stub。
與 ark-skill-creator 分工：creator 管**單一 skill 的內容**，本 skill 管**skill 在各專案之間怎麼流動**。

## 規範（唯一一份 —— 不要再抄進各 agent 的 SOUL／MEMORY）

1. **只裝需要的**：每個專案在 `.kiro/skills`（`.ark` 佈局為 `.ark/skills`）與 `agents/*/.kiro/skills` 只放自己需要的 skill；
   根目錄的清單寫在 `skills-manifest.yaml`，各 agent 的子集以「已安裝的」為準（角色刻意不同）
2. **實體複本、進自己的 git**：不 symlink 到別的專案的複本（對方客製或刪除都會害到你）
3. **更新來源只有上游**：本機 `~/kiro-cli/github/shared/ark-agent-skills`，或 GitHub 公開 repo（自動 clone 到 `~/.cache/ark-agent-skills`）；
   覆寫用 `--upstream` 或 `$ARK_SKILLS_UPSTREAM`。🔴 `~/kiro-cli/.kiro/skills` 是 kiro-bot 自己的複本，**不是上游**
4. **本地改過（LOCAL）不覆蓋**：專案特有設定留本地；通用修正回貢上游（SOP B）；上游舊版才 `--accept-upstream`
5. **不 commit 不 push 的腳本**：所有腳本只改工作樹；提交照共用工作樹規則（pathspec、commit／push 分開看 rc）

## 情境路由

| 情境 | 讀 | 跑 |
|---|---|---|
| 看本專案 skills 狀況、有沒有新版 | `references/sop-consumer-update.md` | `skills_sync.py status` |
| 更新到上游最新 | 同上 | `skills_sync.py plan` → `update --apply` |
| 裝新 skill／移除不需要的／清舊名殘留 | `references/sop-install-remove.md` | `install`／`remove`／`update --apply --prune`／`residue` |
| 服務啟動檢查（ark-agent-os 套件呼叫）、空殼 | `references/sop-startup-doctor.md` | `skills_sync.py doctor [--bundle] [--repair]` |
| 把本地修改回貢上游 | `references/sop-contribute-upstream.md` | 上游 clone 開 worktree |
| 發列車、對齊通知 | `references/sop-release-train.md` | `gen_manifest.py`／`notice_build.py` |
| 整併 skill、稽核、回填 metadata | `references/alignment-workflow.md`、`judgment-checklist.md`、`metadata-schema.md`、`taxonomy.md`；踩坑與判準 `references/ops-playbook.md` | `audit_skills.py`／`backfill_metadata.py` |

## 模式一：專案（消費端），在專案根執行

```bash
S=.kiro/skills/ark-skills-sync/scripts          # 已安裝本 skill 時；否則用上游 clone 裡的同一支
python3 $S/skills_sync.py status                 # 每個目錄：需要／已裝／缺少／空殼／舊名／STALE／LOCAL
python3 $S/skills_sync.py update --apply         # 補裝缺的與空殼 → 對齊 STALE（LOCAL 不動）
python3 $S/skills_sync.py install ark-foo --to agents/qa-agent
python3 $S/skills_sync.py doctor --json          # 離線健檢（套件啟動時就是跑這個）
```

腳本：`skills_sync.py`（入口）· `upstream.py`（上游解析，C-1）· `skilltree.py`（雜湊、frontmatter、健全性，C-3／C-4）·
`mirror_sync.py`（逐檔 blob 歷史對齊，規格 `references/mirror-sync.md`）· `ark_layout.py`（`.ark`／`.kiro` 佈局）。

## 模式二：upstream 維護（維護者／CI，在上游 repo 根執行）

管**庫的一致性 + 版本基底**。

```bash
# 稽核（P0/P1 清零才放行；穩定規則 ID AL-xxx）
python ark-skills-sync/scripts/audit_skills.py --repo . --json baseline.json
# 版本回填 semver + depends_on 物件化
python ark-skills-sync/scripts/backfill_metadata.py --repo . --versions
# 產 release manifest + index（audit 全綠才打 tag）
python ark-skills-sync/scripts/gen_manifest.py --repo . --release skills-YYYY.MM-rN --out ark-skills-sync/release
#   ⚠️ 不帶 --out 會寫到 repo 根 release/（錯位置）；在乾淨工作樹最後產
#   🔴 manifest **另開一個 commit**（`chore: 列車 rN manifest`），不要 amend 進內容 commit ——
#      amend 會讓 manifest 記的 commit 變成孤兒（r12～r18 都是）；align_sync 以「含該 manifest 的 commit」為準
# 移除/改名前後反向掃消費端
python ark-skills-sync/scripts/check_consumers.py --name ark-foo
#   不帶 --name：列懸空引用＋「已併入、stub 仍在」的舊名（矩陣／SOUL 還寫舊名、或複本旁沒有接手者 → 回 1）
# 與上一班列車比 major 升版 → Alignment Notice
python ark-skills-sync/scripts/check_consumers.py --impact --json impact.json
python ark-skills-sync/scripts/notice_build.py impact.json --out docs/reports/review/<date>-align-notice.md
```

守門規則（`AL-xxx` 穩定 ID，exit 0/1/2）:既有 AL-001~024（frontmatter/category/觸發詞/
stub/orphan/懸空…）+ 版本系列 AL-101（version 非 semver，過渡 P2）/AL-104（depends_on 無範圍）/
AL-107（消費端型缺 tested_against）。改動走 Alignment Directive 的 D-x，文件沒有的決策不執行。

## 模式三：v2 matrix（align_sync，🔻 停用中，只剩 aidev）

> 2026-11-13 起新專案一律用模式一的 `skills_sync.py`＋`skills-manifest.yaml`；以下保留給尚未遷移的 matrix 部署（契約：`references/consumer-contract.md`）。

管**這個 team 手上 skill 的版本對齊**。資料在 `skills-matrix.yaml`（git）、狀態在
`.kiro/skills.lock.json`（本機不進 git，每機一份）。

```bash
python .kiro/skills/ark-skills-sync/scripts/align_sync.py plan --waves      # 列差異，不改檔
python .kiro/skills/ark-skills-sync/scripts/align_sync.py apply --wave 1 --yes --upstream <ark-agent-skills clone>
#   私訊 manager 確認才升（C-5）；從「manifest 是該列車的那個 commit」git archive 取檔，tree_hash 對上 manifest 才換上、寫 lock
#   上游路徑也可寫在 skills-matrix.yaml 的 upstream.local_clone；找不到列車 → 先在 clone 裡 git fetch
python .kiro/skills/ark-skills-sync/scripts/align_sync.py verify             # AL-203 drift/AL-301 base tier
python .kiro/skills/ark-skills-sync/scripts/align_sync.py verify --remote    # 對上游 manifest，出 lag/breaking
python .kiro/skills/ark-skills-sync/scripts/align_sync.py heartbeat          # 送 team 頻道（同版只寫 health）
python .kiro/skills/ark-skills-sync/scripts/align_sync.py resolve <path>     # 這個複本是哪版？
```

沒接 align_sync（無 matrix／lock，或 `local_mirror` 指向別台）的 team，用**本機鏡像同步**：
逐檔比 git blob 歷史，過期才對齊、上游從未有過的本地修改不覆蓋（規格 `references/mirror-sync.md`）。

```bash
python ark-skills-sync/scripts/mirror_sync.py plan  --upstream <skills repo> --target <team 根>   # 列 STALE/LOCAL/NEWER
python ark-skills-sync/scripts/mirror_sync.py apply --upstream <skills repo> --target <team 根> --keep kb_registry.json --yes
```

LOCAL（本地修改）先判斷是否回貢上游，**不要用 --keep 蓋過真修正**；審過確認只是上游歷史之前的舊版，才用 `--accept-upstream <skill>` 覆蓋。

對齊單位是 **release train**（`skills-YYYY.MM-rN`），個別 skill 只能例外 pin（附 reason）。
tier 策略:base 全隊同版（Loop 五件套，major 不一致 P0）· role 走範圍 · domain（local_only）自由。
升級走波次:wave 1 manager → wave 2 leaders → wave 3 workers，每波 verify P0/P1=0 才下一波。

## 版本感知（套件實例，排程呼叫）

套件（ark_team_agent/ark_bot_agent）預設段掛排程，每日 `verify --remote` + `heartbeat`:
拉上游 manifest 反查本機版本 → 寫 lock → 一行 heartbeat 送 team 頻道 + `/api/health`。
上游 `pre-push` 只在 major/契約變更時廣播 Alignment Notice（`notice_build.py`）。
> 🔴 套件預設段/scheduler/api-health 在 paddy 開發源（交接項），本 skill 只提供 align_sync 腳本。

## 收尾（強制）

1. audit P0/P1=0 + check_consumers 對本次移除的名字回 0（併入改 stub 時：`--impact` 列出要通知的消費端；mirror_sync 不會自動裝接手者）
2. drift/verify report:ark-md-report review 型，存 `docs/reports/review/{date}-align-*.md`
3. 獨立 commit（pathspec，不 `git add -A`），message 帶 `[refs: alignment-directive]` 或 D-x

## 邊界

- 不重寫任何 skill 核心邏輯;只動 description/frontmatter/reference/stub/版本
- 不動 Office 四工具（保持官方可升級）
- 單一 skill 建立/eval → ark-skill-creator
