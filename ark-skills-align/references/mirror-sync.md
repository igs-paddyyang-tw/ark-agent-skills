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

| 檔案情況 | 本地 blob 在上游歷史？ | 判定 | apply 時 |
|---|---|---|---|
| 兩邊都有、內容相同 | — | same | 不動 |
| 兩邊都有、內容不同 | 是 | stale | 換成上游 |
| 兩邊都有、內容不同 | 否，且符合 `--keep` | keep | 保留本地 |
| 兩邊都有、內容不同 | 否 | **local-mod** | 整個 skill 不動，列出待審 |
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
python ark-skills-align/scripts/mirror_sync.py plan  --upstream <skills repo> --target <team 根> [--keep PATH ...] [--json]
python ark-skills-align/scripts/mirror_sync.py apply --upstream <skills repo> --target <team 根> [--keep PATH ...] [--only SKILL ...] --yes
```

- 掃描 `<team 根>/.kiro/skills` 與 `<team 根>/projects/*/.kiro/skills`；symlink 目錄跳過。
- 只處理上游也有的 skill；本地獨有的 skill（domain / local_only）不碰。
- `--keep PATH`：skill 內相對路徑或其前綴（可重複），例如 `kb_registry.json`、`artifacts`。
- `apply` 必須帶 `--yes`；不帶時等同 plan 並 exit 2。
- 不做 git 操作；提交由呼叫端以 pathspec 執行（刪除大量檔時 pre-push 可能阻擋，屬預期）。
- exit：0 正常；2 參數錯誤／未帶 `--yes`；3 上游不是 git repo。

## 驗收

1. 過期副本 → `STALE`，apply 後與上游 `HEAD` 逐檔相同。
2. 本地獨有且不在歷史的檔 → apply 後仍在。
3. 內容不在上游歷史的修改 → `LOCAL`，apply 不動該 skill。
4. `--keep` 命中的修改 → 不再判 `LOCAL`，apply 保留本地版本。
5. 本地版號較新 → `NEWER`，apply 不動。
6. 上游工作樹的未追蹤／忽略檔不會被帶入。
7. `--help` exit 0 且不在 cwd 產生檔案。
