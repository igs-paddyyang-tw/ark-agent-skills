---
name: ark-github-cli
description: |
  git / GitHub 統一閘道，讀寫兩側：
  【讀｜L2 平台知識】從 GitHub repo 同步平台文件到 knowledge/github/、程式碼搜尋、issue/PR 讀取——
  知識檢索順序（對齊 knowledge-management-spec 權威、信任度遞減、同分排序）：
  private → 產品庫(如 hoyeah) → **github** → shared；weknora 是外部 RAG 不進 search_order。
  【寫｜收尾提交】任何 git 寫入都走「開發收尾」：① 標記完成 ② memory 整理瘦身（daily ≤150 字、
  memory.md ≤2000 tokens 歸檔）③ 同步 AGENTS.md / index.md ④ 具名 add → commit → pull --rebase → push。
  commit 前有 deterministic 閘門：daily 未追加、memory 超限、索引漂移 → 不 commit。
  使用此 Skill 當使用者說「查平台規格」「套件文件怎麼寫」「同步 github 文件」「看 repo docs」
  「這個 issue 說什麼」，或「收尾」「收工」「wrap up」「提交今天的改動」「整理 memory」「同步 readme」
  「push」——凡是要碰 git 的場景。
  不適用於：知識蒸餾入 wiki 請用 ark-wiki-engine（本 skill 不寫 wiki/）；產 changelog 請用
  ark-release-notes；自家業務數字口徑查詢請用 ark-db-query。
metadata:
  version: "0.2.0"
  schema_version: 1
  status: active
  updated: 2026-09-22
  category: executor
  outputs:
    - format: md
      audience: both
  depends_on: [ark-wiki-engine]
  author: paddyyang
---

# ark-github-cli — git 讀寫閘道（L2 知識 + 收尾提交）

一個原則貫穿兩側：**呼叫 git 就是在做收尾**。讀側把平台權威文件拉到本地供 L2 檢索；
寫側任何 commit 都必須先把工作狀態落盤（todo、memory、規範），閘門是腳本、判斷在 LLM。
「腳本量測搬運、LLM 只判斷」——腳本不猜「什麼過時」，LLM 不做「搬檔、算 tokens、跑 rebase」。

## 前置

| 依賴 | 用途 | 缺了 |
|------|------|------|
| `git` | 讀側 sparse-checkout、寫側提交 | 讀側不可用；寫側 ①②③ 照跑、④ 跳過 |
| `gh`（已 auth） | 程式碼搜尋、issue/PR、私有 repo | sync 仍可（public / 既有 git 認證）；search 只剩本地、issue 不可用 |

## 資產地圖

| 路徑 | 側 | 用途 |
|------|----|------|
| `scripts/gh_docs.py` | 讀 | `sync` 拉文件到 knowledge/github/、`search` 本地優先檢索、`issue` 讀 issue/PR、`list` |
| `scripts/wrapup_check.py` | 寫 | 盤點：未勾 todo、目錄/scripts 未入索引的漂移、memory 大小（唯讀） |
| `scripts/memory_optimize.py` | 寫 | `daily` 追加（≤150 字守門）、`check` token 估算、`archive` 歸檔搬運 |
| `scripts/wrapup_git.py` | 寫 | 收尾閘門 → 具名 add → commit → pull --rebase → push；衝突即停 |
| `scripts/tests/test_cli_contract.py` | — | 四支 `--help` 零依賴、守衛先於第三方 import |

---

## 讀側：L2 平台知識

```bash
python scripts/gh_docs.py sync igs-paddyyang-tw/ark_bot_agent --paths README.md docs/ --dest <ws>
python scripts/gh_docs.py search "skip_resume" --repo igs-paddyyang-tw/ark_bot_agent --dest <ws>
python scripts/gh_docs.py issue igs-paddyyang-tw/ark_bot_agent 42
python scripts/gh_docs.py list --dest <ws>
```
- 落點 `<ws>/knowledge/github/<repo>/` + `_meta.json`（sha / 每檔 blob / 抓取時間）；重跑只更新有變的檔，
  上游刪除的檔本地保留標 `stale`
- **本地優先**：先 grep 已同步檔，miss 才打 `gh search code`（省 rate limit）
- `_meta.json` 超 7 天先 sync 再答，回覆標抓取時間
- 只落 raw，**不寫 wiki/**；要蒸餾進 shared 交 ark-wiki-engine ingest
- 問的是自家業務數字口徑 → 不歸本層，轉 ark-db-query

## 寫側：開發收尾四步

### ① 標記已完成
```bash
python scripts/wrapup_check.py <ws> --todos
```
本次完成的 `- [ ]` → `- [x] …(YYYY-MM-DD)`；未完成的不動、不補理由。閘門對 todo **只警告不擋**——
「本次是否完成」腳本判斷不了，這是 LLM 的活。

### ② 整理並優化 memory
```bash
python scripts/memory_optimize.py <ws> daily "做了什麼 / 決定 / 踩坑 / 後續"   # ≤150 字，超長拒收
python scripts/memory_optimize.py <ws> check                                   # >2000 tokens exit 2
```
memory.md 只放「下個月還有用」的事實；更新時順手：補長期事實、刪重複、過時敘述改成現況。
`check` exit 2 時瘦身：LLM 挑出歷史/明細段落寫暫存檔 →
`memory_optimize.py <ws> archive <暫存檔>` → 原文進 `memory/archive/memory-archive-YYYY-MM-DD.md`、
memory.md 移除並留指針。紅線：daily/ 與 archive/ 只增不刪；memory 歷史留 memory/，不進 knowledge/。

### ③ 同步 readme / 規範
```bash
python scripts/wrapup_check.py <ws> --drift
```
新增/移除的目錄與 scripts 必須出現在 AGENTS.md / index.md / README——改敘述，不加備註。

### ④ git 提交（閘門在此）
```bash
python scripts/wrapup_git.py <ws> --paths memory/ docs/ AGENTS.md --message "wrapup: <一句話>" [--dry-run] [--no-push]
```
| 情境 | 行為 | exit |
|------|------|------|
| 無 `.git` | skipped，①②③ 已完成即算收尾 | 0 |
| 閘門：今日 daily 缺 / memory >2000 / 索引漂移 | **不 commit**，列出缺哪步 | 5 |
| `--paths` 缺、含 `-A`/`.`、含 `.env` `.key` `.pem` | 拒絕 | 1 |
| pull --rebase 衝突 | 停在衝突狀態、不 push、列衝突檔 | 3 |
| push 失敗 | commit 留本地 | 4 |
| `--no-gate "<理由>"`（hotfix） | 跳閘門，理由寫進 trailer `Wrapup-Gate: skipped (<理由>)` | — |

不 force push、不自動解衝突、不動 `.env`。閘門可繞但**必留痕**——留痕不留洞。

## 收尾完成判定（deterministic）

- `wrapup_git.py` 閘門通過（daily ✓ memory ≤2000 ✓ drift 0 ✓）
- 有 git：`git status --porcelain -- <paths>` 空、`git log origin/<branch>..HEAD` 空
- 未勾 todo 經 LLM 對照本次工作核對完畢

## 邊界

- 讀側唯讀：不 commit、不開 issue、不存 token（靠 `gh auth` / git credential）
- 不蒸餾、不寫 wiki/（ark-wiki-engine）；不產 changelog（ark-release-notes）
- 不做 code review / 測試——收尾假設工作已驗收
