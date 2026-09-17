# View 軌：MD 章節 → HTML 書的映射

`book_build.py` 依此表渲染。鐵律與 ark-html-report 相同：**只排版、不改寫**。HTML 不得出現 MD 沒有的字句、
不得省略章節（可折疊附錄），頁尾必含每章 `content-src + sha256` 戳記，人看到書永遠找得回 source of truth。

## 頁面結構（單檔 index.html）

```
┌──────────┬──────────────────────────────────────────────┐
│ 書脊目錄  │  章首：章號 · 標題 · est_minutes · level      │
│ (aside)  │  punchline（章首引言塊）                       │
│ 00 序    │  ─────────────────────────────────────────── │
│ 01 …     │  七段內文（h2 錨點，可被 #chapter-N/section 定位）│
│ 02 …     │  ─────────────────────────────────────────── │
│ ▶ 03 …   │  ‹ 上一章    第 3 / 7 章    下一章 ›           │
│ 99 附錄  │  頁尾：書名 v{version} · 更新 · 戳記 · catalog  │
└──────────┴──────────────────────────────────────────────┘
      閱讀進度條（頂部，跨章累計）
```

- 目錄項 = 書脊：章號 + 標題，當前章「抽出」；點擊切換章節（hash routing `#ch-03`）
- 手機（< 900px）：目錄收成頂部抽屜，內容單欄
- `@media print`：目錄隱藏，章節逐頁分頁，callout 去陰影，連結顯示 URL

## 映射表

| MD 結構 | HTML 元件 | 備註 |
|---|---|---|
| book.yaml `title/subtitle/author/version/audience/outcomes` | 封面頁（第 0 頁，在序之前） | outcomes 列成「讀完你會」清單；`level` 顯示為徽章 |
| 章節 frontmatter `title/chapter/est_minutes/level` | `.ch-head` | 「第 N 章 · 20 分鐘 · 入門」 |
| frontmatter `punchline` | `.punchline`（章首引言塊） | 也出現在回顧第一句，不重複渲染成兩塊 |
| frontmatter `confidence: low` | `.callout.warning` 章首 | 文字固定：「本章素材不足，結論待驗證」 |
| `## 這章要解決的問題` | `.section.problem` | 最後一個問句加粗 |
| `## 路線圖` | `.section.roadmap` + 有序清單 | 每項可點擊跳到內文對應 h3（若標題可對應） |
| `## 內文` `###` | `.section.body` h3 錨點 | 目錄不展開 h3（保持書脊乾淨），但 h3 有 id |
| `> [!ASK] …` | `.callout.ask` | 標題預設「你可能會想說」 |
| `> [!TIP] …` | `.callout.tip` | 標題預設「白話」 |
| `> [!MYTH] …` | `.callout.myth` | 標題預設「大家通常會以為」 |
| `> [!TRY] …` | `.callout.try` | 標題預設「動手做」；內含 code 用 `--font-mono` |
| `> [!NOTE]` / `> [!WARNING]` | `.callout.note` / `.callout.warning` | |
| `## 常見誤解` | `.section.myths` | |
| `## 動手做` | `.section.practice` | |
| `## 重點回顧` | `.section.recap` 卡片 | 清單改成三張小卡；第一張加 punchline 標記 |
| `## 下一章` | `.section.next` + 下一章按鈕 | 文字保留，按鈕連到下一章 |
| 表格 | `.table-wrap > table` | 橫向可捲動 |
| fenced code | `pre > code` | 語言標籤顯示在右上 |
| 一般 blockquote | `blockquote` | |
| `sources` | 章末「本章依據」摺疊清單 | 路徑原樣顯示，不改寫 |

## 風格

風格系統獨立成 `references/styles.md`：六種預設（library／felt／neon／shonen／manga／console），
每種一個 `assets/styles/{name}.css`，由 `book.yaml style:` 或 `--style` 選擇，`_manifest.json` 登錄即可擴充。
所有風格都完整供應 ark-html-report token 契約，圖書館網站可在外層覆寫 `:root` 統一主題。

視覺母題規則：每種風格只在一個地方大膽（見 styles.md 的「母題」欄），其餘元件只吃 token。
書脊色由 `book.yaml cover.spine_color` 決定全書主色；章節色依 `type`：preface 棕、chapter 依序循環、appendix 黃銅。

## 戳記

每章 `</main>` 前寫入：

```html
<!-- content-src: 03-give-it-a-soul.md sha256:1a2b3c4d5e6f7a8b -->
```

書層級寫入：

```html
<!-- book-src: book.yaml sha256:… chapters:7 built:2026-09-17T10:20:00+08:00 -->
```

`book_build.py --check` 讀這些戳記比對現況：任一章 MD 雜湊不符 → `STALE`（exit 1）；缺 site → `NO-SITE`；缺戳記 → `NO-STAMP`。
與 ark-html-report 的 `report_pair.py scan` 可並列掛在 CI。
