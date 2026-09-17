---
name: ark-book
description: |
  教學產出專用 skill：把一個主題（skill 用法、流程、工具、案例）寫成「一本書」，雙軌輸出——
  Content 軌 Markdown 章節給 AI 當知識庫（chunk 自足、frontmatter 契約、受控 tags，可被 ark-wiki-engine ingest），
  View 軌單檔 HTML 書給人閱讀（目錄、章節導覽、閱讀進度；六種可擴充風格 library/felt/neon/shonen/manga/console，與 ark-html-report 同一套 token 契約）。
  每本書會登錄到 library/catalog.json，未來由圖書館網站以「一本一本的書」上架。
  內建教學引擎（蒸餾自 hung-yi-lee-skill：先給問題再給方法、直覺先於形式、每章有 punchline、常見誤解、動手做、三句回顧）
  與 deterministic 守門腳本：book_lint.py（契約與教學結構驗證）、book_build.py（MD→HTML 書 + 雙軌戳記）、
  book_register.py（圖書館目錄登錄）。
  使用此 skill 當使用者要求「寫一本書」「做教材」「教學文件」「新人手冊」「onboarding 教程」「把這個 skill 的用法寫成教學」
  「整理成一本可以放進圖書館的書」「教學網站」「給成員學的知識庫」，或任何要同時給 AI 與人讀的教學內容。
  分析報告（時點快照、有 verdict）請用 ark-md-report；單頁報告網頁請用 ark-html-report；本 skill 管「會被反覆閱讀與教學」的長期內容。
metadata:
  author: paddyyang
  schema_version: 1
  version: 1.0.0
  updated: 2026-09-17
  category: document
  outputs:
    - { format: md, audience: ai }
    - { format: html, audience: human }
    - { format: data, audience: ai }
  render: self
  depends_on: [ark-html-report, ark-wiki-engine]
  status: active
---

# ark-book

把一個教學主題寫成一本書。核心原則：

- **MD 是 source of truth**（Content 軌）；HTML 書是它的渲染視圖（View 軌），由 `book_build.py` 產生，不手寫
- **教學不是文件**：文件回答「這是什麼」，教材回答「你遇到什麼問題、怎麼辦、怎麼想出來的、記住哪一句」。每章必須有問題、有路線圖、有 punchline、有誤解、有動手做、有回顧
- **書是長期演化的知識**，與報告（時點快照）分工：報告是書的素材，書是把多份素材織成有脈絡的教學路徑
- **一本書進一格書架**：`book_register.py` 登錄 `library/catalog.json`，圖書館網站據此上架；書的 HTML 用 ark-html-report 的 token 變數，換圖書館主題只換 `:root`

## 與其他 skill 的分工

| | ark-book | ark-md-report | ark-wiki-engine |
|---|---|---|---|
| 管什麼 | 文體：教學內容怎麼寫成書 | 文體：分析報告怎麼寫 | 庫：儲存、索引、檢索 |
| 生命週期 | draft → review → published，可改版（`version` 遞增） | 時點快照，產出後不改 | seedling → mature |
| 讀者 | 人為主、AI 為輔（章節可獨立檢索） | AI 為主 | AI |
| 關係 | 章節是 wiki 的 ingest 素材；書可引用報告作證據 | 報告是書的素材 | 書與報告都是 source |

## 工作流程

### 0. 先把「這本書在教誰做什麼」講清楚

不確定就先用 ark-grill-me 拷問。至少回答四件事，寫進 `book.yaml`（範本見 `assets/book.yaml.example`；若有主題本人/負責人的訂正，另存 `_calibration.md`，範本見 `assets/_calibration.md.example`）：

- `audience`：誰讀（新成員 / 已會用 Agent 的人 / 主管）
- `outcomes`：讀完能**做**什麼（動詞開頭，2–5 條，可驗證）
- `prerequisites`：需要先會什麼；沒有就寫 `[]`，不寫「基礎概念」這種空話
- `scope_out`：明確不教什麼 —— 這條讓書不蔓延

### 1. 收素材（sources/ 唯讀）

把逐字稿、報告、對話紀錄、程式碼、既有 skill 的 SKILL.md 放進 `books/{slug}/sources/`，視為不可改的原始層。書裡每個主張要能指回 sources 的路徑。素材不足的地方直接在章節標 `confidence: low`，不硬寫。

### 2. 排章節（先目錄再內文）

讀 `references/book-contract.md`。原則：

- 章節順序 = 讀者遇到問題的順序，不是系統架構的順序（「先教 prompting 再講原理」——相關性先於基礎）
- 一章只教一個能力；一章讀完時間 10–25 分鐘（`est_minutes`）
- 每章 frontmatter 的 `punchline` 先寫，寫不出一句就代表這章還沒想清楚
- 目錄寫進 `book.yaml` 的 `chapters`，之後 lint 會核對檔案與目錄一致

### 3. 寫章節（教學引擎）

讀 `references/teaching-engine.md`（必讀）與 `references/chapter-template.md`。寫每章前先看 `references/examples/chapter-golden.md` 與 `chapter-negative.md`，分辨「教材」與「文件」的差別。

三條鐵律（來自 hung-yi-lee-skill 的本人訪談校準，本 skill 去人格化後採用）：

1. **有脈絡，不流水帳**：概念之間要有「因為 A 撞牆所以有 B」的線，不是一條一條列
2. **每章有 punchline**：讀者一週後還記得的一句話，寫在 frontmatter 也寫在回顧
3. **教方法的來歷，不只教方法**：先給問題 → 讀者會先想到的做法 → 它哪裡不夠 → 「怎麼辦？」→ 方法登場

章節七段固定順序（lint 檢查標題存在）：

```
## 這章要解決的問題      ← 先讓問題痛，再給方法
## 路線圖                ← 三句話說這章走哪幾步
## 內文                  ← 直覺 → 例子 → 命名 → 第二個例子 → 一句話收
## 常見誤解              ← 至少一個「大家通常會以為…但其實…」
## 動手做                ← 指令 / 腳本 / 檢核，讀者能立刻試
## 重點回顧              ← 最多三句，第一句是 punchline
## 下一章                ← 一句話橋接
```

內文區塊用 GitHub alert 語法標記教學元件，renderer 會轉成對應樣式：`> [!ASK]`（你可能會想說…）、`> [!TIP]`（直覺/白話）、`> [!MYTH]`（誤解）、`> [!TRY]`（動手做）、`> [!NOTE]`、`> [!WARNING]`。

寫給 AI 讀的硬規則（與 ark-md-report 同源）：章節 chunk 自足（禁「如上所述」「前者/後者」，主詞寫全名）；`tags` 只用 wiki 受控詞彙；每個非常識主張附 sources 路徑；術語第一次出現用「命名儀式」：先描述它做什麼，再說「這個東西我們叫做 X」。

### 4. Lint 守門（deterministic，不可跳過）

```bash
python scripts/book_lint.py books/{slug}/                     # 整本
python scripts/book_lint.py books/{slug}/03-xxx.md            # 單章
python scripts/book_lint.py books/{slug}/ --wiki-schema knowledge/{proj}/schema.md   # 加驗 tags 白名單
```

lint 驗證：`book.yaml` 契約、章節 frontmatter 必要欄位與枚舉、目錄與檔案一致、章號連續、七段標題齊全且順序正確、每章 ≥1 個 `[!ASK]` 與 `[!MYTH]`、回顧 ≤3 條、punchline 非空且 ≤40 字、chunk 自足禁詞、placeholder 殘留（TODO/TBD/lorem/xxx）、內部連結與 sources 路徑存在。LLM 自評不算過，以 exit code 0 為準。

### 5. Build 成書（View 軌）

```bash
python scripts/book_build.py --list-styles                    # 六種預設：library / felt / neon / shonen / manga / console
python scripts/book_build.py books/{slug}/                    # → books/{slug}/site/index.html，風格取 book.yaml style（預設 library）
python scripts/book_build.py books/{slug}/ --style neon --out /tmp/neon.html   # 試風格，不動 site/
python scripts/book_build.py books/{slug}/ --check            # 驗雙軌戳記，MD 改了沒重 build → STALE
```

風格選擇讀 `references/styles.md`：內容是方法論選 library、規則契約選 felt、成果展示選 neon、衝刺教程選 shonen、新人手冊選 manga、指令手冊選 console。一本書一種風格，寫進 `book.yaml style:`。新增風格只要加一個 `assets/styles/{name}.css` 並登錄 `_manifest.json`。

單一 HTML 檔：左側目錄（書脊式章節導覽）、上一章/下一章、閱讀進度、`@media print` 可印、深淺色 token。頁尾嵌每章 `content-src + sha256` 戳記，與 ark-html-report 的 `report_pair.py` 同一套偵測邏輯。渲染規則見 `references/html-book-mapping.md`：**只排版、不改寫**，HTML 不得出現 MD 沒有的內容。

### 6. 登錄圖書館

```bash
python scripts/book_register.py books/{slug}/ [--library library/]
```

寫入 `library/catalog.json`（書的 frontmatter 摘要 + 章節清單 + site 路徑 + 更新時間）、重建 `library/catalog.md`、append 一行到 `library/log.md`。圖書館網站（未來 ark-library skill 或套件預設網站）只讀 catalog.json 就能把書上架，不需解析每本書。契約見 `references/library-integration.md`。

交付訊息格式：`書已落盤 books/{slug}/｜{N} 章｜lint: PASS｜site: books/{slug}/site/index.html｜catalog: 已登錄`

## 產出檔案

```
books/{slug}/
├── book.yaml                 # 書籍契約（audience/outcomes/prerequisites/scope_out/chapters/tags/status/version/style）
├── 00-preface.md             # 序：為什麼有這本書、給誰、讀完會怎樣、全書路線圖
├── 01-{chapter-slug}.md      # 章節（七段式）
├── ...
├── 99-appendix-{slug}.md     # 選用：術語表、速查表、練習解答
├── _calibration.md           # 選用：主題本人/負責人的訂正，優先級高於所有模板規則
├── sources/                  # 唯讀素材（逐字稿、報告、對話、程式碼）
└── site/index.html           # build 產物，不手改
library/
├── catalog.json              # 圖書館目錄（機器讀）
├── catalog.md                # 圖書館目錄（人讀）
└── log.md                    # append-only 登錄紀錄
```

## 內容原則

- 一本書一個學習目標；`outcomes` 超過 5 條就拆兩本
- 例子用讀者自己的工作場景（他的專案名、他會下的指令），不用教科書例子
- 數字與規模要讓人有感（「17 個 skill」不如「照著做一次約 40 分鐘」）
- 誠實標邊界：這章沒講的、還沒定論的、要看情況的，明寫出來
- 不批評特定人事物；批評做法、指標與取捨
- `_calibration.md` 存在時，它的每一條都要在對應章節反映，lint 會 WARN 未引用的條目

## 邊界

- 風格是皮不是骨：換風格不得改章節結構或內容；要新風格加 css 並登錄 manifest，不在模板硬寫
- 不產 slides、不產報告：投影片交 pptx / 圖書館風格 HTML deck，分析結論交 ark-md-report
- 不把整本書塞進 wiki：章節是 wiki 的 ingest 素材，走 ark-wiki-engine 的 guard-first + 審核路徑
- 圖書館網站本身（多本書的書架、搜尋、借閱紀錄）不在本 skill 範圍，本 skill 只保證 catalog.json 契約穩定
- 各 agent 的提詞片段與觸發路由見 `references/agent-operating-guide.md`
