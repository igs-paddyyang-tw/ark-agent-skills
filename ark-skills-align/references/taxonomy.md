# 分類法（schema 1.2：三軸）

三個正交欄位 ＋ 既有的產出格式：

| 欄位 | 回答 | 受控詞彙 |
|---|---|---|
| `category` | **產出什麼**（職能） | process／scaffolder／pipeline／view／document／ops |
| `form` | agent **怎麼用** | executor／instruction |
| `domain` | 屬於**哪個業務** | general／game |
| `outputs` | 產出格式 × 受眾 | 見下方「outputs 預設」 |

> 為什麼拆：1.1 把「形態」（`executor`）與「領域」（`domain`）塞進 `category`，違反本檔
> 「判準是**產出物**而非**手段**」的原則 —— 詳見 `docs/specs/2026-10-20-skill-taxonomy-three-axis-spec.md`。
> 詞彙的**程式權威**是 `scripts/audit_skills.py`；其他腳本的複本由 repo 根的 `test_taxonomy_vocab.py`（根 scripts/tests 下）守一致。

> 🔴 **歸屬以各 skill 的 frontmatter 為唯一真相**（2026-08-12 決策 C）。
> 本文件只定義**受控詞彙**與**outputs 預設／例外**，**不再維護歸屬名冊**。
> 要知道哪個 skill 屬哪類：讀該 skill 的 `metadata.category`，
> 或跑 `scripts/audit_skills.py` 取全庫快照。

## 為什麼廢掉歸屬名冊

名冊的資訊 **100% 可從 frontmatter 導出**，手寫就是第二份真相 —— 而它必然落後：

| 症狀（2026-08-12 實測） | 數字 |
|---|---|
| 名冊列出的 skill 數 vs 實際 | 56 vs 66（**落後 13**，另 3 項歸類不符） |
| 表頭宣稱數字 | `pipeline（14–15）` 實際 22；`document（7–8）` 實際 11 |
| 已 stub 卻仍列在名冊 | `ark-report-template` |
| 已 `status: deprecated` 卻仍列在名冊 | `ark-llm-cli` |

更糟的是 `backfill_metadata.py` 內建了**第三份**同樣的表，並在檢查
「是否真的有欄位要填」**之前**就用它早退 ——
**7 個 metadata 完全齊全的 skill 被誤報 `UNMAPPED`**。
同一份資訊存三處，漂移只是時間問題。

## category 受控詞彙與 outputs 預設值

| code | 中文 | outputs 預設 |
|------|------|--------------|
| process | 流程鏈 | `[{format: md, audience: ai}]` |
| scaffolder | 平台生成器 | `[{format: code, audience: both}]` |
| pipeline | 管線元件 | `[{format: data, audience: ai}]` |
| view | 呈現層 | `[{format: html, audience: human}]` |
| document | 文件輸出 | `[{format: md, audience: both}]` |
| ops | 維運 | `[{format: md, audience: ai}]` |

> 🔴 `executor`、`domain` **不是** category（schema 1.2 起）。舊複本寫這兩個值 → audit P2 `category-axis-mixed`；
> 不設自動別名（同一舊值對應多個新值），改法：形態寫 `form`、領域寫 `domain`，category 依產出物重選。

## form 判準

只看「**主要產出是誰做的**」，不看有沒有 `scripts/` 目錄、也不看呼叫次數：

| form | 判準 | 例 |
|---|---|---|
| `executor` | 自帶 `scripts/` 決定性產生主要產出，agent 以 bash 呼叫、讀 stdout 契約 | db-query、wiki-engine、game-prob |
| `instruction` | LLM 依 SKILL.md 產生主要產出；附帶腳本只做守門／渲染／輔助 | md-report（lint）、html-report（戳記）、release-notes（骨架） |

## domain 判準

| domain | 判準 |
|---|---|
| `game` | 內容綁遊戲業務（遊戲製程、玩家、遊戲行銷、遊戲 QA） |
| `general` | 換成非遊戲專案照樣能用（同時涵蓋通用與遊戲的也算，例：kpi-calculator） |

> 只在出現第三個業務且有 ≥ 2 個 skill 時才擴充；擴充要同步 audit 與各複本（測試會擋）。

**舊縮寫**（`proc`／`scaffold`／`present`／`doc`／`sop`）為 legacy alias（注意 `sop` 現對應 `document`），
過渡期由 `audit_skills.py` 報 P3 容忍，新 skill 一律用上表 canonical 值。

⚠️ `deprecated` **不是** category —— 它是 `status`。
降級請用 `metadata.status: deprecated` ＋ 標準 stub 格式。

## outputs 例外清單（backfill 時人工複核）

| skill | outputs |
|-------|---------|
| ark-chart-generator | `[{format: png, audience: both}]` |
| ark-webapp-generator 等 scaffolder 全類 | `[{format: code, audience: both}]` |
| Office 四工具 | `[{format: office, audience: human}]` |
| ark-md-report | `[{format: md, audience: ai}, {format: html, audience: human, via: ark-html-report}]` |
| 報告類（news-daily、md-report） | 另加 `render: html`；其餘預設 `render: none` |

## 待辦：Directive 註記（自原歸屬表移出，勿遺失）

原歸屬表夾帶下列 Alignment Directive 意圖註記。
**`docs/alignment/` 目前不在 repo 內**，這些是唯一殘存的線索，逐項確認前不要刪：

| 註記 | 原文脈絡 | 狀態 |
|---|---|---|
| **D-2** | scaffolder：合併 `ark-chatbot-generator` 後為 9 | ❓ 現有 9 個 scaffolder 且 chatbot-generator 仍存在 —— 待確認是否已執行 |
| **D-3 / D-5** | view 類整併 | ❓ |
| **D-4 / D-6** | document 類整併；`ark-report-template` 標 D-6 待定 | ✅ report-template 已 stub |
| **D-7** | `ark-file-export` 待定 | ❓ 仍為 active pipeline |
| **D-8** | `ark-cost-tracker` 收編（收編則 pipeline 為 14） | ❓ 仍為 active pipeline |
| **D-10** | `ark-landing-page` 觀察 | ❓ |
| **D-11** | `ark-uml-generator` 觀察 | ❓ |
| **D-14** | `ark-news-daily` 歸類修正 `pipeline` → `document` | ✅ **已完成**（見下方判準） |
| **A-NEW-2** | `ark-md-report` 新收編 | ✅ 已存在且 `category: document` |

> 取得 Directive 後請逐條核對並更新本表；全部結案即可刪除本節。

## 歸類判準範例：`ark-news-daily`（D-14）

同一個 skill 可能同時具備多種特徵，判準是**產出物**而非**手段**：

| 看起來像 | 為什麼不是 |
|---|---|
| `pipeline` | 抓新聞／聚合是**手段**，不是產出物 |
| `view` | HTML 由 `ark-html-report` 渲染（View 軌），本 skill **不自己產 HTML** |
| **`document`** ✅ | source of truth 是 **MD 檔**，人與 AI 皆讀 —— 符合 document 定義 |

**frontmatter 已把這個判準寫成機器可讀形式**：

```yaml
outputs:
  - { format: md,   audience: ai }
  - { format: html, audience: human, via: ark-html-report }   # via = 不是自己產
depends_on: [ark-html-report, ark-telegram-sender]
```

> `outputs[].via` 是關鍵欄位：**有 `via` 代表這個格式是委由別的 skill 渲染的**，
> 不應據此把 category 判成該格式所屬的類別。
> 遇到「這個 skill 到底算哪類」時，先問：**source of truth 是什麼格式？**
