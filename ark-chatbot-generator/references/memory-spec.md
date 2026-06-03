# 三層記憶架構規範 + 跨 Session 記憶搜尋

Phase 2 的記憶系統由三個獨立元件組成，各自負責不同面向的記憶管理。
三者協同運作，在 `[9] Memory System` 層統一觸發。

**v0.5.0 新增**：FTS5 跨 Session 全文搜尋 + UserProfiler 自動使用者建模。

## 架構總覽

```
對話輪次（Turn）
       ↓
┌──────────────────────────────────────────────────────────┐
│                     Memory System                         │
│                                                          │
│  ┌─────────────────┐  ┌──────────────────┐              │
│  │  EntityMemory    │  │ HierarchicalMemory│              │
│  │  實體 → Wiki     │  │ L1/L2/L3 壓縮    │              │
│  │  （背景執行）     │  │ （同步壓縮）      │              │
│  └─────────────────┘  └──────────────────┘              │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │  MemorySearch（FTS5 跨 Session 全文搜尋）          │   │
│  │  conversation_history → FTS5 索引 → context 注入   │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │  UserProfiler（自動使用者建模）                     │   │
│  │  每 10 輪 → LLM 萃取偏好 → 更新 memory.md         │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────┐               │
│  │     memory.md（檔案式記憶）           │               │
│  │  data/memory/memory_{user_id}.md     │               │
│  └──────────────────────────────────────┘               │
└──────────────────────────────────────────────────────────┘
```

---

## NEW: MemorySearch — FTS5 跨 Session 全文搜尋

### 設計目標

使用者問「上次我問過什麼」或提到先前對話的關鍵字時，Bot 能從歷史中找到並回答。

### 資料庫結構

```sql
-- 儲存所有對話（含群組記錄）
CREATE TABLE conversation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL,          -- 'user' | 'assistant'
    content TEXT NOT NULL,
    timestamp REAL NOT NULL,
    session_id TEXT NOT NULL DEFAULT ''
);

-- FTS5 全文搜尋虛擬表
CREATE VIRTUAL TABLE conversation_fts
USING fts5(content, content_rowid='id', tokenize='unicode61');
```

### 寫入時機

| 場景 | 寫入 |
|------|------|
| 群組訊息（不論是否 @mention） | ✅ 記錄到 conversation_history + FTS5 |
| 私訊（使用者輸入） | ✅ 記錄 |
| 助理回覆 | ✅ 記錄（限前 500 字） |

### 查詢時機

在 `_llm_answer()` 中，LLM 生成前呼叫：

```python
recall_ctx = _memory_search.get_context_for_query(text, user_id)
# 回傳格式：
# [歷史回憶]
# - (user) 之前問過的內容...
# - (assistant) 當時的回答...
```

注入 system prompt，讓 LLM 能參考歷史對話回答。

---

## NEW: UserProfiler — 自動使用者建模

### 設計目標

每 N 輪對話結束後自動萃取使用者偏好，不需手動設定。

### 觸發邏輯

```python
PROFILE_INTERVAL = 10

def should_profile(user_id, session) -> bool:
    return len(session.turns) - last_profiled_count >= PROFILE_INTERVAL
```

### 萃取 Prompt

```
分析以下對話，萃取使用者的偏好和習慣。
只回傳 key: value 格式，可用的 key 有：
偏好語言、常用指令、關注主題、工作風格、回覆格式、時區、暱稱、
常用 Skill、專案背景、技術棧、備註
只輸出有把握的偏好（至少出現 2 次以上的模式），不要猜測。
```

### 結果

萃取的偏好自動寫入 `data/memory/memory_{user_id}.md`，
後續 Planner 和 LLM 回答都能讀取並注入 context。

---

---

## A. EntityMemory — 實體關聯記憶

從對話中自動提取實體（遊戲名、廠商、數值指標），並更新到 Wiki 知識庫。

### 資料結構

```python
@dataclass
class Entity:
    """從對話中提取的實體。"""
    name: str                   # 實體名稱（如 "Gates of Hades"）
    entity_type: str            # 實體類型（"game" | "provider" | "metric" | "mechanic"）
    attributes: dict            # 附加屬性（如 {"rtp": 96.5, "provider": "Pragmatic Play"}）
    source_turn_id: str         # 來源對話輪次 ID
```

### 介面

```python
class EntityMemory:
    """實體關聯記憶：從對話提取 Entity → 更新 Wiki。"""

    def __init__(self, llm: GeminiAdapter, wiki_base: Path):
        self.llm = llm
        self.wiki_base = wiki_base  # knowledge/ 根目錄

    async def extract_entities(self, turns: list[Turn]) -> list[Entity]:
        """使用 LLM 從對話中提取實體。

        提取策略：
        1. 將最近 N 輪對話組合為 prompt
        2. 要求 LLM 以 JSON 格式回傳實體清單
        3. 解析並建構 Entity 物件

        Returns:
            提取到的實體清單
        """
        ...

    async def merge_to_wiki(self, entities: list[Entity]) -> None:
        """將新實體合併到 knowledge/ 對應頁面。

        合併策略：
        1. 根據 entity_type 決定目標路徑
           - game → knowledge/raw/slots/{provider}/{name}.md
           - provider → knowledge/wiki/providers/{name}.md
        2. 若頁面已存在 → 追加新資訊（不覆蓋既有內容）
        3. 若頁面不存在 → 建立新頁面（含 YAML frontmatter）
        4. 標記來源 turn_id 與時間戳記
        """
        ...
```

### 執行模式

- **背景執行**：使用 `asyncio.create_task()` 在背景執行，不阻塞使用者互動
- **靜默失敗**：實體提取或 Wiki 寫入過程發生例外 → 記錄 `logger.error()` → 不影響對話流程
- **觸發時機**：每輪對話結束後，在 `[9] Memory System` 層觸發

---

## B. HierarchicalMemory — 階層式摘要記憶

將對話分為三層，根據輪數自動分層壓縮，控制 Token 預算。

### 三層結構

| 層級 | 名稱 | 輪數範圍 | 處理方式 | Token 預算 |
|------|------|---------|---------|-----------|
| L1 | Recent | 最近 5-10 輪 | 原始保留 | ~2000 |
| L2 | Short-term | 前 11-50 輪 | 每 10 輪壓縮為 1 段摘要 | ~1000 |
| L3 | Long-term | 整體對話 | 壓縮為一段核心意圖摘要 | ~500 |

### 壓縮規則

```
對話輪數 ≤ 10：
  → 僅回傳 L1（原始對話），不進行壓縮

對話輪數 11-50：
  → L2（前 11-N 輪壓縮摘要）+ L1（最近 10 輪原始）

對話輪數 > 50：
  → L3（整體核心意圖摘要）+ L2（中間輪次壓縮摘要）+ L1（最近 10 輪原始）
```

### 介面

```python
class HierarchicalMemory:
    """階層式摘要：L1 近期 + L2 短期摘要 + L3 長期摘要。"""

    def __init__(self, llm: GeminiAdapter):
        self.llm = llm

    def compress(self, session: Session) -> str:
        """根據對話輪數自動分層壓縮。

        回傳格式：
        - ≤10 輪："{L1 原始對話}"
        - 11-50 輪："{L2 摘要}\n\n{L1 原始對話}"
        - >50 輪："{L3 摘要}\n\n{L2 摘要}\n\n{L1 原始對話}"

        L2 壓縮：每 10 輪對話壓縮為 1 段摘要（使用 LLM）
        L3 壓縮：整體對話壓縮為核心意圖摘要（使用 LLM）
        """
        turns = session.turns
        total = len(turns)

        if total <= 10:
            return self._format_l1(turns)

        l1_turns = turns[-10:]
        l1_text = self._format_l1(l1_turns)

        if total <= 50:
            l2_turns = turns[:-10]
            l2_text = self._compress_l2(l2_turns)
            return f"{l2_text}\n\n{l1_text}"

        # > 50 輪：全部三層
        l1_turns = turns[-10:]
        l2_turns = turns[10:-10]
        l3_turns = turns[:10] + turns[10:-10]  # 全部歷史

        l1_text = self._format_l1(l1_turns)
        l2_text = self._compress_l2(l2_turns)
        l3_text = self._compress_l3(l3_turns)

        return f"{l3_text}\n\n{l2_text}\n\n{l1_text}"

    def _format_l1(self, turns: list[Turn]) -> str:
        """格式化 L1 原始對話。"""
        ...

    def _compress_l2(self, turns: list[Turn]) -> str:
        """L2 壓縮：每 10 輪壓縮為 1 段摘要。"""
        ...

    def _compress_l3(self, turns: list[Turn]) -> str:
        """L3 壓縮：整體對話壓縮為核心意圖摘要。"""
        ...
```

### LLM 壓縮 Prompt

L2 壓縮 Prompt：
```
請將以下 {n} 輪對話壓縮為一段簡潔摘要（約 100 字），
保留關鍵資訊：使用者意圖、提及的遊戲/廠商、數值指標。
```

L3 壓縮 Prompt：
```
請將以下對話歷史壓縮為一段核心意圖摘要（約 50 字），
概括使用者的主要目標與關注重點。
```

---

## C. HybridMemoryRetrieval — 向量與關鍵字雙路檢索

結合 ChromaDB 語意向量檢索與 BM25 關鍵字檢索，使用 RRF 合併排序。

### 資料結構

```python
@dataclass
class MemoryHit:
    """檢索結果。"""
    content: str                # 記憶內容
    score: float                # 合併後分數
    source: str                 # "vector" | "bm25" | "hybrid"
    metadata: dict              # 附加資訊（turn_id、timestamp 等）
```

### 介面

```python
class HybridMemoryRetrieval:
    """向量 + 關鍵字雙路檢索。"""

    def __init__(self, collection_name: str = "conversation_memory"):
        self.collection_name = collection_name
        self._chroma_client = None   # 延遲初始化
        self._bm25_index = []        # BM25 文件索引
        self._bm25_docs = []         # 原始文件

    async def search(self, query: str, top_k: int = 5) -> list[MemoryHit]:
        """執行雙路檢索並回傳 RRF 合併排序結果。

        流程：
        1. ChromaDB 語意向量檢索 → top_k 結果
        2. BM25 關鍵字檢索 → top_k 結果
        3. RRF 合併排序
        4. 回傳前 top_k 個結果

        降級策略：
        - ChromaDB 不可用 → 僅 BM25
        - BM25 索引為空 → 僅 ChromaDB
        - 兩者皆不可用 → 回傳空清單
        """
        ...

    def ingest_turn(self, turn: Turn) -> None:
        """在每輪對話結束後同時寫入向量庫和 BM25 索引。

        寫入內容：
        - ChromaDB：turn.content 的向量嵌入 + metadata
        - BM25：turn.content 的分詞索引
        """
        ...
```

### RRF 合併演算法

```python
def _rrf_merge(
    self,
    vector_results: list[MemoryHit],
    bm25_results: list[MemoryHit],
    k: int = 60,
) -> list[MemoryHit]:
    """Reciprocal Rank Fusion 合併排序。

    公式：RRF_score(d) = Σ 1 / (k + rank_i(d))

    其中 k=60 為常數（標準 RRF 參數），rank_i(d) 為文件 d 在第 i 路檢索中的排名。

    規則：
    - 雙路命中的文件 → source="hybrid"，分數為兩路 RRF 分數之和
    - 單路命中的文件 → source="vector" 或 "bm25"
    - 雙路命中排名高於單路命中
    """
    scores: dict[str, float] = {}
    sources: dict[str, str] = {}
    meta: dict[str, dict] = {}

    for rank, hit in enumerate(vector_results):
        key = hit.content
        scores[key] = scores.get(key, 0) + 1 / (k + rank + 1)
        sources[key] = "vector"
        meta[key] = hit.metadata

    for rank, hit in enumerate(bm25_results):
        key = hit.content
        prev = scores.get(key, 0)
        scores[key] = prev + 1 / (k + rank + 1)
        if prev > 0:
            sources[key] = "hybrid"  # 雙路命中
        else:
            sources[key] = "bm25"
        meta[key] = hit.metadata

    # 依分數降序排列
    sorted_keys = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [
        MemoryHit(content=k, score=scores[k], source=sources[k], metadata=meta[k])
        for k in sorted_keys
    ]
```

### ChromaDB 設定

```python
# 初始化（延遲載入）
import chromadb

def _init_chroma(self) -> None:
    """延遲初始化 ChromaDB client。"""
    try:
        self._chroma_client = chromadb.Client()
        self._collection = self._chroma_client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
    except Exception as e:
        logger.error(f"ChromaDB 初始化失敗: {e}")
        self._chroma_client = None
```

### BM25 設定

使用簡易的 TF-IDF 風格 BM25 實作（或 `rank_bm25` 套件）：

```python
# 分詞策略：以空格 + 標點分詞（中文可用 jieba）
def _tokenize(self, text: str) -> list[str]:
    """簡易分詞。"""
    import re
    return re.findall(r'\w+', text.lower())
```

---

## memory.md — OpenClaw 風格檔案式記憶

每個使用者一個 Markdown 檔案，儲存偏好與常用參數。
路徑：`data/memory/memory_{user_id}.md`

### 格式

```markdown
---
user_id: "{user_id}"
updated: "{ISO 8601 timestamp}"
---

## 偏好設定
- 預設 source: slotcatalog
- 關注廠商: IGT, Aristocrat, Pragmatic Play
- 報表語言: 繁體中文
- 預設 RTP 天數: 7

## 最近關注
- {game_name}（{provider}）— {date}

## 對話摘要
- {date}：{摘要}
```

### 讀寫

由 `MemoryStore`（`src/conversation/memory.py` 中的既有類別或新增）負責：
- `load(user_id: str) -> dict` — 解析 YAML frontmatter + Markdown body
- `save(user_id: str, data: dict) -> None` — 寫入 Markdown 檔案
- `update_preferences(user_id: str, key: str, value: str) -> None` — 更新偏好
- `add_recent(user_id: str, item: str) -> None` — 新增最近關注

ConversationPlanner 在填充參數時優先參考此檔案，減少重複追問。
