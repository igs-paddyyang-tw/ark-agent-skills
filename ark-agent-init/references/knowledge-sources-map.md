# 知識來源地圖（knowledge-sources-map，v1.0）

> ark-agent-init 產出 team 時的**五類知識來源**定義。承接需求單
> `2026-09-22-shared-package-change-requests.md`（B1）。
> 目的：讓每個 team 有一致的來源分層與 `knowledge_search_order`，
> 消滅「每個 team 各自手工補、格式分歧」的根因。

---

## 五類來源總表（L1–L5）

| 代號 | 來源 | 目錄 / 位置 | 進 search_order？ | 誰維護 | 讀寫 |
|------|------|------------|:----------------:|--------|------|
| **private** | 各 instance 私有 | `knowledge/<instance>/`（子 agent）或 `agents/<name>/knowledge/` | ✅ 最前（信任最高） | 各 agent 自己 | 讀寫（wiki 由 ingest 產） |
| **L2 產品庫** | 該 team 的專案產品知識庫（層名**依產品命名**） | `knowledge/<product>/`（如 `hoyeah`、`tiger`；`hoyeah` 只是案例名） | ✅ 次之 | 排程蒸餾 + 人工 | 讀為主；raw 增量 |
| **L1 github** | 外部 repo 淺 clone 蒸餾來源 | `$ARK_GITHUB_ROOT/`（排程蒸餾）或 `knowledge/github/`（`ark-github-cli` 即時同步） | ✅ 再次 | 排程 pull→蒸餾 / `ark-github-cli` sync | 唯讀來源；蒸餾進 raw |
| **shared** | 跨 agent 共用知識 | `knowledge/shared/` | ✅ 最後（信任基線） | 排程 digest + 人工 | 讀寫（wiki 由 ingest 產） |
| **L5 weknora** | 外部 RAG 服務（ark-weknora-cli） | 外部服務（非本地櫃） | ❌ **不進**（見下） | 研七/自建 KB | 外部查詢；見 `weknora-checklist.md` |

> 🔴 **「L1/L2/L5」是需求單的來源分類代號**，不是搜尋優先序。搜尋優先序由
> `knowledge_search_order` 決定（見下），信任度遞減：`private → L2(產品) → github → shared`。

### 🔬 private 層命名機制（套件硬編碼 vs skill 規範 —— 釐清改哪裡有效）

private 私有層有**兩個名字**，責任分屬不同層：

| 名稱 | 誰定義 | 出處 | 可否改 |
|------|--------|------|:---:|
| 櫃子別名 `private` | 🔴 **ark-team-agent 套件硬編碼** | `team_mcp.py`：`_add("agents/{instance}/knowledge","private")` + `_add("knowledge/{instance}","private")` | ❌ 改 skill/設定無效，要改套件 |
| 實際目錄名 = instance 名 | 🔴 套件硬編碼代入 | 同上，`{instance}` 從 team.yaml 代入 | 由 instance 名決定 |
| 「層名 = json 檔名」文字規範 | ark-agent-init | 本 skill 文件描述既成事實 | 文件，非產生機制 |

- 套件**同時接受兩種私有路徑**：`agents/{name}/knowledge/`（子 agent）與 `knowledge/{name}/`（dir=. manager，歷史相容）——兩者櫃子別名都是 `private`。
- 🔴 **目錄實體名必須 = instance 名**，否則 `knowledge/{instance}` 對不上（套件用 instance 名拼路徑，且不報錯）。
- `knowledge_search_order` 寫 `private` 是引用這個硬編碼別名，不是寫某個目錄名。

---

## `knowledge_search_order` 語意（對齊 team-agent A1/A2）

- `knowledge_search_order` 列的是**本地 BM25 櫃名**，各對應 `knowledge/<櫃名>/`。
- 🔴 **它只影響「同分排序」**，不是「硬跳層/查無往下」——不同分的結果由 BM25 決定，
  order 只在分數相同時決定誰先。部署端規範不要照「不可跳層」寫（那是誤解，見需求單 A2）。
- **信任度遞減預設**（未宣告時 team-agent 套用，見需求單 A1）：
  ```
  private → <product>（L2） → github → shared
  ```
  private 最高（自己剛學的）、shared 最低（共用基線）。
- 未宣告時 team-agent 會用預設並在啟動 log 印「使用預設 search_order」提示（A1，屬套件層）。

## 🔴 為什麼 weknora（L5）不進 search_order

`knowledge_search_order` 只排**本地 BM25 櫃子**。weknora 是**外部 RAG 查詢**
（走 `ark-weknora-cli` 的 agent-chat / kb-chat），不是本地 wiki 櫃 →
它屬於**外部查詢決策樹**（何時查 weknora vs 查本地 wiki），由 skill 獨立呼叫，
不由 `_search_domains` 的櫃子集合管。接入方式見 `weknora-checklist.md`。

---

## 依 team 定位選來源層

不是每個 team 都需要全部五類。產出時依定位選：

| team 定位 | private | L2 產品 | L1 github | shared | L5 weknora |
|-----------|:-------:|:-------:|:--------:|:------:|:----------:|
| 純研發/工具（如 nana、paddy） | ✅ | — | 選配 | ✅ | 選配 |
| 遊戲產品團（如 slot/fish/hoyeah） | ✅ | ✅（產品名） | ✅ | ✅ | 選配 |
| 營運/BI（如 aibi） | ✅ | ✅ | 選配 | ✅ | ✅（研七 KB） |
| 資訊收集（如 ninja/director） | ✅ | — | ✅（多 repo） | ✅ | — |

> `build_kiro.py` 產出時依所選來源層建立目錄骨架，並把選到的（扣除 weknora）
> 寫入 `team.yaml` 的 `knowledge_search_order`（見 B2）。

---

## 目錄骨架（team 根層）

```
knowledge/
├── shared/                 ← 跨 agent 共用（Wiki 引擎與 start.py 讀這層）
│   ├── raw/ wiki/ schema.md index.md log.md
├── <product>/              ← L2 產品庫（層名依產品，選配）
│   ├── raw/ wiki/ schema.md index.md log.md
└── <instance>/             ← private（各 instance；子 agent 走 agents/<name>/knowledge/）
    └── raw/ wiki/ schema.md index.md log.md

# L1 github 來源不在 knowledge/ 內，在 $ARK_GITHUB_ROOT/（宣告於 github-sources.yaml）
# L5 weknora 是外部服務，設定在 .env（見 weknora-checklist.md）
```

## 相關檔案

- `knowledge-governance-scoring.md` — 🆕 知識庫治理評分標準（100 分 9 維度 + 三層資源分工 + 紅線）
- `knowledge-schema-template.md` — 單一櫃的 schema.md 模板（frontmatter/規則）
- `github-sources.md` — L1 github 統一 schema（`ARK_GITHUB_ROOT` + repos[]，B3）
- `weknora-checklist.md` — L5 weknora 接入 checklist（B5）
- `architecture-drift-feedback.md` — 為何一定要有 shared/ 層（歷史踩坑）
- **權威全文（跨 team 通用）**：`knowledge-management-spec.md`（nana-team `knowledge/shared/raw/local/governance/`）—— 本地圖與評分皆萃取自此
