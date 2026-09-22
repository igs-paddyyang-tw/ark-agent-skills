# 知識庫治理評分標準（knowledge-governance-scoring，v1.0）

> ark-agent-init 產出/檢查 team 知識庫的**完整度評分標準**。
> 萃取自跨 agent 通用權威 SOP `knowledge-management-spec.md`（nana-team knowledge/shared/raw）。
> 用途：`build_kiro.py --validate` 的品質檢查參照；人工評一個 team 知識庫治理成熟度。

---

## 零、三層資源分工（先分清才不會放錯）

| 資源 | 位置 | 是什麼 | 權限 |
|------|------|--------|------|
| 程序記憶 | `.kiro/skills/` | 你「會做」的流程 | 讀：自動載入；寫：僅提案 |
| 經驗記憶 | `memory/` | 你「經歷過」的事 | 讀：自動；寫：直接 |
| 參考知識 | `knowledge/` | 你「查得到」的資料 | 讀：檢索；寫：僅提交 `raw/` |

**寫入去向判斷**（問一句話）：經歷的事→`memory/`；可重複引用的知識→`knowledge/*/wiki/`；
要交付的產出→`docs/`；使用者沒說要存知識庫→不寫 wiki。
核心判準：**「三個月後有人問同樣問題，這份資料還能直接引用嗎？」** 能→wiki；不能→docs。

---

## 評分標準（總分 100）

| # | 維度 | 檢查項 | 配分 |
|---|------|--------|:---:|
| A | **五類來源到位** | github / 產品 / shared / 私有 / weknora 各 4 分（依 team 定位，不適用標 N/A 不扣）| 20 |
| B | **shared 五件套** | schema/index/log/raw/wiki 齊全 | 15 |
| C | **私有層五件套** | 每個 agent 私有庫五件套齊，層名 = json 檔名（instance 名）| 15 |
| D | **查詢優先序宣告** | team.yaml 有 `knowledge_search_order` | 10 |
| E | **schema 規範** | 每層 schema.md 有 tag 白名單 + frontmatter 契約 + 適合存放類型 | 10 |
| F | **蒸餾規範接線** | BRAIN/AGENTS 有知識蒸餾小節，指向 distill-rules SOP | 10 |
| G | **GitHub 設定（若適用）** | `github-sources.yaml` 宣告 + 路徑不寫死（`ARK_GITHUB_ROOT`）+ pull 流程可跑 | 8 |
| H | **weknora 設定（若適用）** | ark-weknora-cli 裝好 + .env 齊 + 讀寫驗證過 | 7 |
| I | **index/log 維護紀律** | log.md append-only 有紀錄、index 與 wiki 同步 | 5 |

### 評級

| 分數 | 等級 | 意義 |
|------|:---:|------|
| 90–100 | 🟢 A | 治理完整 |
| 75–89 | 🟡 B | 可用，少量缺件 |
| 60–74 | 🟠 C | 結構有缺，來源不全 |
| < 60 | 🔴 D | 治理不完整，需補建 |

> **N/A 處理**：team 定位不需某來源（如純本地團隊不需 github）→ 該項標 N/A，
> 分母按實際適用維度重算（不因「用不到」被扣分）。

---

## 引用守則（評分外的操作紀律）

- 事實/規格/評價類問題走檢索流程（private → 產品 → github → shared），信任度遞減。
- 引用標來源：`📚 參考：{頁面}` / `🧠 記憶：{日期}` / `🔗 來源：{URL}`；無法確認標 `💡 一般知識，未經知識庫驗證`。
- **數字型結論一律以 L2 業務資料源實查為最終裁判**（搭 ark-db-query）；wiki / weknora 口徑僅供對照。

## 🔴 紅線（違反直接扣對應維度）

- 對話記錄**只進 memory，絕不進 knowledge/**
- `knowledge/wiki/` 只有使用者明確要求才寫入，且**只能由 ingest 產出，禁止手寫**
- `raw/` 只新增，不改既有；改 wiki 後同步 `index.md`；`log.md` append-only
- 分析報告放 `docs/reports/`（ark-md-report 格式），不直接複製進 wiki
- **不在知識庫寫入秘密**（token/密碼/個資）

## 放置位置（各 team steering 接線）

- **BRAIN.md** 的「知識庫規則」段引用本評分 + `knowledge-sources-map.md`
- **AGENTS.md** 的「知識庫怎麼查」段列五類來源與查詢序
- 權威全文（跨 team 通用）：`knowledge-management-spec.md`（nana-team knowledge/shared/raw）
