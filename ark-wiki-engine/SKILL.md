---
author: paddyyang
name: ark-wiki-engine
description: |
  產出 Wiki 知識庫引擎，以 Markdown 為基礎的知識管理系統。
  支援 ingest（匯入）、query（查詢）、lint（格式檢查）、schema（驗證）、
  graph（知識圖譜）、hybrid_search（混合搜尋）、rag_bridge（RAG 橋接）、template（模板）。
  含 Web UI Wiki 分頁（暗黑科技風格）與 Chat 整合（Wiki context 注入）。
  使用此 Skill 當使用者提及 Wiki、知識庫、knowledge base、知識圖譜、
  RAG、文件搜尋、知識管理、wiki Q&A、或任何需要建立 Markdown 知識庫系統的場景。
---

# ark-wiki-engine

產出 Wiki 知識庫引擎（8 個 Runtime Skills + Web UI + Chat 整合），以 Markdown 為基礎，可獨立運作。

## 觸發條件

- 「Wiki」、「知識庫」、「knowledge base」
- 「知識圖譜」、「RAG」、「文件搜尋」
- 「知識管理」、「wiki ingest」、「wiki Q&A」

---

## 產出檔案

```
knowledge/{project-name}/          # Wiki 知識庫（多專案支援）
├── raw/                           # 唯讀原始資料
├── wiki/                          # 結構化知識頁面
│   ├── overview.md                # 專案總覽（必要）
│   └── {category}/               # 分類目錄
├── schema.md                      # Schema 規則（v3.0）
├── index.md                       # 索引目錄
└── log.md                         # 操作日誌（append-only）

src/skills/wiki_skills/            # 8 個 Runtime Skills
├── __init__.py
├── wiki_query.py
├── wiki_ingest.py
├── wiki_lint.py
├── wiki_schema.py
├── wiki_graph.py
├── wiki_hybrid_search.py
├── wiki_rag_bridge.py
└── wiki_template.py

src/server/api/
├── files.py                       # 檔案列表 API（/api/files）
└── wiki.py                        # Wiki API 端點（/api/v1/wiki/*）

src/server/templates/index.html    # Wiki Tab（整合到主頁面）
src/server/static/js/app.js        # Wiki 樹 + Markdown 渲染
src/server/static/css/style.css    # Wiki 分頁樣式
```

---

## 產出指引

### 步驟 1：Wiki 知識庫目錄（schema.md v3.0）

三層模式（Andrej Karpathy LLM Wiki）：

```
knowledge/{project-name}/
├── raw/          → 唯讀原始資料（LLM 只讀不改）
├── wiki/         → 結構化知識（LLM 維護）
│   ├── overview.md
│   └── {category}/
│       └── {page}.md
├── schema.md     → 規則定義
├── index.md      → 索引目錄
└── log.md        → 操作日誌（append-only）
```

**多專案支援**：每個獨立專案/產品擁有自己的知識庫目錄，跨專案引用使用 `../other-project/index.md`。

**頁面 Frontmatter（v3.0）**：

```yaml
---
title: "頁面標題"
type: concept | entity | source | synthesis | comparison | overview | system
tags: [tag1, tag2]
sources: [raw/來源檔案]
related: [相關頁面檔名]
created: YYYY-MM-DD
updated: YYYY-MM-DD
status: seedling | developing | mature
---
```

| 欄位 | 必要 | 說明 |
|------|------|------|
| title | ✅ | 頁面標題（繁體中文） |
| type | ✅ | 頁面類型 |
| tags | ✅ | 分類標籤 |
| sources | 建議 | 來源 raw 檔案 |
| related | 建議 | 相關頁面（用於圖譜） |
| created | ✅ | 建立日期 |
| updated | ✅ | 最後更新日期 |
| status | 建議 | 頁面成熟度 |

**雙向連結**：`[[頁面檔名]]`（不含 .md、不含路徑）

### 步驟 2：8 個 Wiki Runtime Skills

| Skill | skill_id | 功能 |
|-------|----------|------|
| WikiQuerySkill | wiki_query | 讀 index.md 定位 → 全文搜尋 → 排序回傳 |
| WikiIngestSkill | wiki_ingest | raw/ 匯入 → 萃取 → 建立/更新頁面 → 更新 index + log |
| WikiLintSkill | wiki_lint | 檢查 frontmatter 必要欄位、孤立頁面、斷裂連結 |
| WikiSchemaSkill | wiki_schema | 依 schema.md 驗證 type/status 合法值 |
| WikiGraphSkill | wiki_graph | 分析 `[[wikilink]]` 知識圖譜（節點、邊、hub/orphan） |
| WikiHybridSearchSkill | wiki_hybrid_search | BM25 關鍵字 + 全文 + RRF 融合 |
| WikiRagBridgeSkill | wiki_rag_bridge | LLM 呼叫前自動注入相關 Wiki context |
| WikiTemplateSkill | wiki_template | 產生標準化頁面（entity/concept/source 模板） |

### 步驟 3：Wiki API 端點

```python
# src/server/api/files.py
GET /api/files              # 列出 ARTIFACTS_DIR 下所有 .md 檔案
GET /api/files/{path:path}  # 讀取指定檔案內容

# src/server/api/wiki.py
POST /api/v1/wiki/query     # Wiki 查詢
POST /api/v1/wiki/ingest    # Wiki 匯入
POST /api/v1/wiki/lint      # Wiki 健康檢查
```

### 步驟 4：Web UI Wiki 分頁

整合到主頁面 `index.html`，與 Chat 分頁並列：

```html
<!-- Tab 切換 -->
<div class="tab-bar">
  <button class="tab-btn active" data-tab="chat">💬 對話</button>
  <button class="tab-btn" data-tab="wiki">📚 Wiki</button>
</div>

<!-- Wiki 分頁 -->
<div class="tab-content" id="tab-wiki">
  <div class="wiki-layout">
    <aside class="wiki-sidebar">
      <input class="wiki-search__input" placeholder="搜尋 Wiki...">
      <nav class="wiki-tree"><!-- 動態載入 --></nav>
    </aside>
    <main class="wiki-content">
      <!-- Markdown 渲染 + highlight.js -->
    </main>
  </div>
</div>
```

**JS 功能**：
- `loadWikiTree()` — 從 `/api/files` 載入檔案列表，按資料夾分組
- `loadWikiPage(path)` — 從 `/api/files/{path}` 載入 Markdown 並渲染
- `renderMarkdown(md)` — 簡易 Markdown → HTML（標題、粗體、表格、程式碼）
- Wiki 搜尋過濾（前端即時篩選）

### 步驟 5：Chat 整合（Wiki Context 注入）

在 `chat.py` 中，一般訊息走 Gemini chat 時自動注入 Wiki context：

```python
async def _get_wiki_context(request, query: str) -> str:
    """從 wiki_query Skill 取得相關 context 注入 LLM。"""
    result = await registry.invoke("wiki_query", {"query": query, "top_k": 3})
    if result.success and result.data:
        snippets = [f"[{r['title']}] {r['summary']}" for r in result.data["results"][:3]]
        return "\n".join(snippets)
    return ""
```

### 步驟 6：操作路由規則

Chat 收到訊息後的 Wiki 操作判斷：

| 意圖 | 觸發詞 | 執行 |
|------|--------|------|
| Query | 一般提問 | wiki_query → 合成回答（附來源標記） |
| Ingest | 「ingest」、「匯入」、「加入這篇」 | wiki_ingest → 更新 index + log |
| Lint | 「lint」、「健康檢查」、「wiki 狀態」 | wiki_lint → 回報問題清單 |
| Update | 「存下來」、「記錄」、「更新 [頁面]」 | 讀取 → 整合 → 更新 updated |

**Query 回答格式**：
```
[回答內容]
---
📚 參考頁面：[[page1]]、[[page2]]
```

---

## 注意事項

- Wiki `raw/` 目錄為唯讀（LLM 只讀不改）
- 修改 wiki 頁面後必須同步 `index.md` + `log.md`
- `wiki_lint` 檢查 frontmatter 必要欄位（title、type、created、updated）
- `wiki_graph` 使用 `[[page_name]]` 雙向連結建構圖譜
- 矛盾標記：`> ⚠️ **矛盾**：來源 A 說 X，來源 B 說 Y，待釐清。`
- 不確定內容用 `(?)` 標記
- 禁止自行解決矛盾，只能標記
- 禁止刪除 `log.md` 舊記錄（append-only）

---

## 使用現有 Wiki（操作層）

> 當專案已有 knowledge/ 目錄和 FastAPI server 在跑時，用以下方式操作（不是建新系統）。

### 觸發條件（使用層）

- 「匯入知識」「ingest」「把 raw 匯入 wiki」
- 「查詢 Wiki」「搜尋知識庫」「Wiki 有沒有 XXX」
- 「檢查 Wiki」「Wiki 健康度」「lint」

### 操作方式

**確認 server 在跑**（port 8000）後，用終端執行：

#### Ingest（匯入 raw/ → wiki/）
```bash
curl -X POST http://localhost:8000/api/v1/wiki/ingest
```
✅ 回傳：`{"ingested": ["file1.md", "file2.md"], "count": 2}`

#### Query（查詢）
```bash
curl -X POST http://localhost:8000/api/v1/wiki/query \
  -H "Content-Type: application/json" \
  -d '{"q": "搜尋關鍵字"}'
```
✅ 回傳：`{"results": [...], "answer": "..."}`

#### Lint（健康檢查）
```bash
curl http://localhost:8000/api/v1/wiki/lint
```
✅ 回傳：`{"issues": [], "healthy": true}`

### 不跑 server 時的替代方式

```python
# 直接用 Python 執行
import asyncio
from src.wiki.engine import WikiEngine
engine = WikiEngine()

# Ingest
engine.ingest()

# Query
result = asyncio.run(engine.query("Ocean King", use_rag=True))
print(result)

# Lint
issues = engine.lint()
print(issues)
```

### 判斷規則

| 使用者說的 | 要做什麼 |
|-----------|---------|
| 「建立 Wiki 系統」「產出 Wiki 引擎」 | → 走上面的「產出指引」（建新系統） |
| 「匯入知識」「查 Wiki」「lint」 | → 走這段「使用層」（操作現有系統） |

### 三種執行模式（依環境選擇）

| 模式 | 條件 | 方式 |
|------|------|------|
| API 模式 | server 在跑（port 8000） | curl 呼叫 API |
| Python 模式 | 有 Python 環境 | 直接 import WikiEngine |
| LLM 模式 | 都沒有（純 IDE 操作） | 按 SOP 讀寫檔案 |

### LLM 模式 SOP（不需要 server 也不需要跑 Python）

#### Ingest SOP
1. 列出 `knowledge/raw/*.md` 所有檔案
2. 逐檔讀取，檢查是否有 frontmatter（`---` 開頭）
3. 沒有 frontmatter → 補上（title / type / tags / created / updated）
4. 寫入 `knowledge/wiki/{filename}`（保持同名）
5. 更新 `knowledge/index.md`（表格列出所有 wiki 頁面）
6. 追加 `knowledge/log.md`（格式：`- [日期時間] ingest: file1, file2`）

#### Query SOP
1. 讀 `knowledge/index.md` 找到可能相關的頁面
2. 讀對應 `knowledge/wiki/{page}.md`
3. 擷取包含關鍵字的段落
4. 組合回答，結尾附：`📚 參考：{page1}, {page2}`

#### Lint SOP
1. 列出 `knowledge/wiki/*.md` 所有頁面
2. 逐檔檢查 frontmatter 必要欄位（title / type / tags / created / updated）
3. 回報缺少欄位的頁面清單
4. 檢查孤立頁面（沒被 index.md 列出的）
