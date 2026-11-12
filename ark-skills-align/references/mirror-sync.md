# mirror_sync — 本機鏡像同步（規格）

> 適用：消費端 team 的 `.kiro/skills` 是**整份複製**的 skill 子集，沒有接 `align_sync`
> （無 `skills-matrix.yaml` / lock，或 matrix 的 `local_mirror` 指向別台機器）。
> 有接 align_sync 的 team 一律走 align_sync；本工具不讀也不寫 matrix / lock。

## 為什麼需要

2026-10-15 對齊 nana-team（7 個 `.kiro/skills`）時發現：

- 只比 `metadata.version` 不夠 —— 64 個差異中 **35 個同版號但內容不同**。
- 「內容不同」有兩種，處置相反：
  - **過期**：本地內容曾經存在於上游（舊版殘留）→ 直接對齊。
  - **本地修改**：上游從未有過這份內容 → 可能是待回貢的修正（實例：aikb 的
    wiki-engine ingest 修正，已收回上游 3.0.1），**不可覆蓋**。
- 從上游**工作樹**複製會帶入 git 忽略的測試產物（實例：wiki `.index/`）。

## 判定（逐檔，以 git blob hash 為準）

上游內容 = `git archive HEAD`（只含已提交、已追蹤的檔）；歷史 = `git rev-list --all --objects` 的 blob 集合。
比較時忽略 `__pycache__/` 與 `*.pyc`。

**換行正規化（2.6.0）**：文字檔（不含 NUL）比對內容前把 CRLF 統一成 LF；查上游歷史時，本地檔的原始、LF、CRLF
三種版本任一命中即算「上游曾有」。Windows checkout 的 CRLF 不再被誤判為 local-mod。含 NUL 的二進位檔只比原始位元組。

| 檔案情況 | 本地 blob 在上游歷史？ | 判定 | apply 時 |
|---|---|---|---|
| 兩邊都有、內容相同（含只差 CRLF／LF） | — | same | 不動 |
| 兩邊都有、內容不同 | 是 | stale | 換成上游 |
| 兩邊都有、內容不同 | 否，且符合 `--keep` | keep | 保留本地 |
| 兩邊都有、內容不同 | 否，且 skill 在 `--accept-upstream` | stale（人已審過） | 換成上游 |
| 兩邊都有、內容不同 | 否 | **local-mod** | 整個 skill 不動，列出待審 |
| 只有本地有、符合上游 `.gitignore` | — | ignored（測試產物等） | 不保留 |
| 只有本地有、符合**消費端** `.gitignore`（含執行時產生的巢狀 `.gitignore`） | — | ignored-local（不列入報告） | **保留**（可能是 `.env`、本機設定） |
| 只有本地有 | 是 | obsolete | 刪除 |
| 只有本地有 | 否 | local-data | 保留 |
| 只有上游有 | — | missing | 補上 |

skill 狀態：

| 狀態 | 條件 | apply |
|---|---|---|
| `SAME` | 無任何差異 | 跳過 |
| `NEWER` | 本地 `metadata.version` 大於上游 | 跳過（疑似本地已升版，待回貢） |
| `LOCAL` | 含任一 local-mod 檔 | 跳過，列出檔案 |
| `STALE` | 其餘有差異者 | 對齊（保留 keep / local-data） |

缺 `metadata.version` 視為最舊。

## 介面

```bash
python ark-skills-align/scripts/mirror_sync.py plan  --upstream <skills repo> --target <team 根> [--root-only] [--keep PATH ...] [--json]
python ark-skills-align/scripts/mirror_sync.py apply --upstream <skills repo> --target <team 根> [--root-only] [--keep PATH ...] [--only SKILL ...] --yes
```

- 掃描 `<team 根>` 與 `<team 根>/projects/*` 各自的技能複本；symlink 目錄跳過。
- **`--root-only`（2.16.0）**：只掃 `<team 根>` 本身。`projects/` 底下是**別的 repo**（例：kiro-cli 的 15 個專案）時必帶，否則會越界改寫他人複本。
- **`agents/*` 不會被掃**：多 agent team 要逐個 agent 目錄當 target（`for t in . agents/*/; do … --target $t; done`）。
- 消費端一律放**實體複本**，不要 symlink 到另一個消費端（會讀到對方的客製版、對方刪 skill 就斷；2026-11-12 ninja-bot 69 個 symlink 已改實體）。
- **佈局雙讀（2.13.0 起，ark-agent-os 3.0 前）**：該目錄有 `.ark/ark.yaml` → `.ark/skills`；否則 `.kiro/skills`。同一目錄只取一處，不會兩份都寫（判定在 `scripts/ark_layout.py`）。
- 只處理上游也有的 skill；本地獨有的 skill（domain / local_only）不碰。
- `--keep PATH`：skill 內相對路徑或其前綴（可重複），例如 `kb_registry.json`、`artifacts`。
- `--accept-upstream SKILL`：人審過 LOCAL、確認只是**上游 git 歷史之前的舊版**（無 version、舊措辭）時，明確指定用上游覆蓋。真修正先回貢上游，不可用此旗標蓋掉。
- `apply` 必須帶 `--yes`；不帶時等同 plan 並 exit 2。
- 不做 git 操作；提交由呼叫端以 pathspec 執行（刪除大量檔時 pre-push 可能阻擋，屬預期）。
- exit：0 正常；2 參數錯誤／未帶 `--yes`；3 上游不是 git repo。
- Windows：git 輸出一律以 UTF-8 解碼；`check-ignore` 以 `-z`（NUL 分隔、位元組）收送 ——
  文字模式會把 stdin 的 `
` 轉成 `
`，git 收到尾帶 `
` 的路徑而全部比對不到。不需再設 `PYTHONUTF8=1`。

## .ark 佈局：版本鎖與檢查（2.14.0）

- `.ark` 佈局的目錄 apply 後寫 `.ark/skills.lock` 的 `mirror` 區塊：上游 repo、commit、每個 skill 的 version 與 tree_hash（只鎖上游也有的 skill）。同一份檔的 `agents` 區塊屬於 align_sync，兩邊各管各的 key、互不覆蓋
- `mirror_sync.py check --target <team 根>`：複本內容與鎖不符（被手改）、鎖裡有但複本不見、`.ark` 佈局卻沒有鎖 → exit 1；legacy `.kiro` 佈局**明說跳過**（不寫鎖、不算通過也不算失敗）
- legacy 佈局的 plan／apply 行為與 2.12.0 完全相同

## 上游 clone 位置（2026-11-12 起）

- **上游開發 clone＝`~/kiro-cli/github/shared/ark-agent-skills`**（各消費端 `--upstream` 指這裡；wrapper 預設值同步改，可用 `ARK_SKILLS_UPSTREAM` 覆寫）
- kiro-cli 的 `.kiro/skills` **不再是上游 clone**，改為 kiro-bot 的客製消費端複本（進 kiro-bot repo）；`.claude/skills` 仍是指向它的 symlink
- 新 clone 要裝 pre-push hook：`ln -s ../../scripts/hooks/pre-push .git/hooks/pre-push`
- 對齊 kiro-cli 自己：`mirror_sync … --target ~/kiro-cli --root-only`

> 舊做法（clone 搬到 `.ark/skills` 保留 `.git`、`.kiro/skills` 改 symlink）已作廢。

## 驗收

1. 過期副本 → `STALE`，apply 後與上游 `HEAD` 逐檔相同。
2. 本地獨有且不在歷史的檔 → apply 後仍在。
3. 內容不在上游歷史的修改 → `LOCAL`，apply 不動該 skill。
4. `--keep` 命中的修改 → 不再判 `LOCAL`，apply 保留本地版本。
5. 本地版號較新 → `NEWER`，apply 不動。
6. 上游工作樹的未追蹤／忽略檔不會被帶入。
7. `--help` exit 0 且不在 cwd 產生檔案。
8. 本地獨有且符合上游 `.gitignore` 的檔（如 wiki `.index/`）不算本地資料，對齊後不保留。
9. `--accept-upstream` 的 skill：local-mod 改按 stale 對齊；`--keep` 仍優先。
10. `--root-only`：`projects/*` 的複本不被列出也不被改；不帶時照舊兩處都掃。
