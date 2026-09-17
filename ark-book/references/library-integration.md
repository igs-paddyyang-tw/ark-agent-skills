# 圖書館整合契約

本 skill 產出「一本書」。圖書館（多本書的書架網站）是另一個 skill / 套件預設網站的工作。
兩者之間只靠一個檔案溝通：`library/catalog.json`。契約穩定，圖書館不需要解析任何一本書的內文。

## 目錄結構

```
library/
├── catalog.json        # 機器讀；book_register.py 維護；圖書館網站唯一輸入
├── catalog.md          # 人讀；由 catalog.json 重建，不手改
└── log.md              # append-only：date | slug | version | status | chapters | action
books/
└── {slug}/…            # 每本書自己的目錄（見 book-contract.md）
```

`library/` 與 `books/` 預設在 repo 根目錄；`book_register.py --library <path>` 可改。

## catalog.json 契約（v1）

```json
{
  "catalog_version": 1,
  "updated": "2026-09-17T10:20:00+08:00",
  "shelves": ["agent-basics", "skill-chain", "case-studies", "ops"],
  "books": [
    {
      "slug": "first-personal-agent",
      "title": "用 ark-agent-skills 建立你的第一位個人助理",
      "subtitle": "從一個模糊目標到一位會自我驗收的 Agent",
      "author": "paddyyang",
      "version": 1,
      "status": "published",
      "language": "zh-Hant",
      "level": "beginner",
      "audience": "研七新成員，會用 ChatGPT，沒建過 Agent",
      "outcomes": ["…", "…"],
      "prerequisites": [],
      "tags": ["agent-team", "onboarding"],
      "shelf": "agent-basics",
      "style": "library",
      "cover": { "spine_color": "green", "emoji": "📗" },
      "est_minutes_total": 95,
      "chapters": [
        { "n": 0, "slug": "preface", "title": "序：為什麼有這本書", "type": "preface", "est_minutes": 5, "status": "published" },
        { "n": 1, "slug": "say-the-goal", "title": "…", "type": "chapter", "est_minutes": 15, "status": "published" }
      ],
      "paths": {
        "book_dir": "books/first-personal-agent",
        "site": "books/first-personal-agent/site/index.html",
        "book_yaml": "books/first-personal-agent/book.yaml"
      },
      "lint": { "status": "PASS", "checked": "2026-09-17T10:19:40+08:00" },
      "pair": { "status": "OK", "checked": "2026-09-17T10:19:58+08:00" },
      "created": "2026-09-17",
      "updated": "2026-09-17"
    }
  ]
}
```

### 規則

- `slug` 唯一；重複登錄同 slug 是**更新**該筆，不新增
- `shelves` 是受控清單：新書的 `shelf` 不在清單內 → register 回 WARN 並仍登錄，但圖書館網站會把它放到「未分類」；要新增書架，人工改 `shelves` 後重跑 register
- `lint.status` 與 `pair.status` 由 register 當場跑 `book_lint.py` 與 `book_build.py --check` 填入，不是自報；圖書館網站可據此顯示「可借閱 / 整理中」
- `status: published` 但 `lint.status != PASS` 或 `pair.status != OK` → register 拒絕登錄（exit 1）；draft/review 允許帶 WARN 登錄
- 圖書館網站只讀 `books[]`，用 `paths.site` 開書、用 `shelf` 分架、用 `level`/`est_minutes_total`/`tags` 篩選、用 `style`/`cover.spine_color` 畫書脊

## 圖書館網站怎麼用（給未來 ark-library 或套件預設網站）

最小實作：一頁 HTML 讀 `catalog.json`，每個 shelf 一排書架，每本書一條書脊（`cover.spine_color` + `title`），
點擊開 `paths.site`。書的 HTML 已用 ark-html-report token 契約，圖書館只要在外層 `:root` 覆寫變數就能統一主題。

進一步：借閱紀錄（誰讀到第幾章）屬圖書館範圍，可用 `slug + chapter.n` 作 key；本 skill 保證這兩個值穩定。

## 與 wiki 的關係

- 章節 MD 是 ark-wiki-engine 的 ingest 素材：`wiki_ingest --source books/{slug}/{NN}-{chapter}.md`
- ingest 時保留 frontmatter `tags`（已是受控詞彙）、`trust`、`sources`；`trust: llm-distilled` 依 wiki 兩層信任模型強制 `seedling`
- 不要把整本 `site/index.html` 丟進 wiki；HTML 是給人的視圖，不是知識

## 與報告的關係

- 書可以引用報告當證據：章節 `sources` 填 `docs/reports/{type}/{date}-{slug}.md#F-3`
- 報告的 findings 若累積出教學價值（同一個坑三份報告都踩），就是開新章或新書的訊號；反過來不成立，書不會變成報告

## 版本

- `catalog_version` 變動只在欄位語意改變時；新增選用欄位不變版
- 圖書館網站遇到更高的 `catalog_version` 應顯示提示而非靜默解析
