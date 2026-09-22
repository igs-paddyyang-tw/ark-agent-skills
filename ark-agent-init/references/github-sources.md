# GitHub 來源統一 schema（github-sources，v1.0）

> L1 github 來源的宣告式設定，取代 market-agent 的 `github_pull_all.sh` + scheduler
> 寫死絕對路徑。承接需求單 `2026-09-22-shared-package-change-requests.md`（B3）。
> 藍本：director 的 `distill-sources.yaml`（宣告式、好維護）。

---

## 為什麼要統一

| 現況 | 問題 |
|------|------|
| director：`distill-sources.yaml`（宣告式） | ✅ 好維護，但 `distill_root` 寫死絕對路徑 |
| market：`github_pull_all.sh` + scheduler 寫死路徑 | 🔴 脆弱：symlink 會遺失、換機器就壞、路徑散在 prompt |

→ 統一為 `github-sources.yaml`：路徑一律走環境變數 `ARK_GITHUB_ROOT`，**禁在 scheduler prompt 寫死絕對路徑**。

---

## Schema：`github-sources.yaml`

放在 team 根目錄。`build_kiro.py` 選了 L1 github 來源層時產出骨架。

```yaml
# github-sources.yaml — L1 github 來源宣告（v1）
# 路徑基準：環境變數 $ARK_GITHUB_ROOT（.env 設定，禁寫死絕對路徑）
schema_version: 1
github_root_env: ARK_GITHUB_ROOT        # 🔴 引環境變數，不寫死路徑

sources:
  - name: <來源名>                       # 唯一識別
    repo: <org>/<repo>                   # GitHub repo（org/name）
    local_path: <相對 ARK_GITHUB_ROOT>   # 淺 clone 落點（相對 $ARK_GITHUB_ROOT）
    dimension: <gamedev|infra|product|market|strategy>  # 蒸餾維度 → raw 子目錄
    owner: <負責蒸餾的 instance>          # 哪個 agent 掃這個來源
    scan_paths: [<子目錄>, ...]           # 只掃這些路徑（省 token）
    file_patterns: ["*.md", "*.py"]      # 只讀這些副檔名
    tags: [<tag>, ...]                   # 蒸餾產物的 tag（須在 schema 白名單）

# dimension → raw 目錄對應（蒸餾產物落點）
dimension_map:
  gamedev:  raw/tech/gamedev/
  infra:    raw/tech/infra/
  product:  raw/product/
  market:   raw/market/
  strategy: raw/strategy/
```

> `github_root_env` 指定「哪個環境變數存 github 根」。實際路徑 =
> `$<github_root_env>/<local_path>`。換機器只改 `.env` 一處。

## `.env` 設定

```bash
# team 根 .env（只放機密與環境路徑，不進版控）
ARK_GITHUB_ROOT=/home/<user>/kiro-cli/github
```

## 標準蒸餾流程（git pull → diff → 蒸餾）

L1 github 來源是**唯讀來源**，蒸餾成 raw/ 後由 ingest 入 wiki：

```bash
# 1. 更新來源（路徑走 $ARK_GITHUB_ROOT，不寫死）
cd "$ARK_GITHUB_ROOT/<local_path>" && git pull --ff-only

# 2. 偵測變更（只蒸餾動過的檔，省 token）
git diff --stat HEAD@{1} HEAD          # 無 git 時 fallback 用 mtime

# 3. 蒸餾變更檔 → raw/（依 dimension_map 落點）
#    只掃 scan_paths + file_patterns，每篇 raw 上限約 2000 字
#    → 寫進 knowledge/<product>/raw/tech/... 或依 dimension_map

# 4. ingest raw → wiki（走 wiki_ingest，含 guard/taxonomy 守門）
python .kiro/skills/ark-wiki-engine/scripts/wiki_ingest.py \
    --source knowledge/<product>/raw/<dim>/ --wiki_dir knowledge/<product>/wiki \
    --schema knowledge/<product>/schema.md --batch --by <owner>
```

## 紅線

- 🔴 **禁在 scheduler prompt 或任何腳本寫死絕對路徑** —— 一律 `$ARK_GITHUB_ROOT`。
- 🔴 **github 來源是唯讀** —— 只 `git pull`，不 push；蒸餾產物進 `raw/`，不改原 repo。
- 🔴 淺 clone（`--depth 1`）省空間；只 `scan_paths` 列的子目錄，別整 repo 掃。
- github 來源**不是** private/shared 那種本地 wiki 櫃 —— 它是蒸餾的**上游素材**，
  蒸餾後的 wiki 才進 `knowledge_search_order`（見 `knowledge-sources-map.md`）。
